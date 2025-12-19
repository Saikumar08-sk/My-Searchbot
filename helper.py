import os
import logging
from typing import List, Dict, Optional

# --- Load OpenAI key safely (Streamlit Cloud + local) ---
try:
    import streamlit as st
    OPENAI_API_KEY = st.secrets.get("OPENAI_API_KEY", None)
except Exception:
    OPENAI_API_KEY = None

if not OPENAI_API_KEY:
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not OPENAI_API_KEY:
    raise RuntimeError(
        "OPENAI_API_KEY is not set. Add it in Streamlit Cloud → Settings → Secrets as:\n"
        "OPENAI_API_KEY = \"sk-...\""
    )

from openai import OpenAI
client = OpenAI(api_key=OPENAI_API_KEY)

# --- Logger (keeps your previous API shape) ---
_base_logger = logging.getLogger("my-searchbot")
if not _base_logger.handlers:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")

class AppLoggerAdapter:
    def __init__(self, logger):
        self._logger = logger

    def log_info(self, msg, level="INFO"):
        self._logger.info(msg)

    def log_error(self, msg, level="ERROR"):
        self._logger.error(msg)

    def log_warning(self, msg, level="WARNING"):
        self._logger.warning(msg)

    def log_debug(self, msg, level="DEBUG"):
        self._logger.debug(msg)

app_logger = AppLoggerAdapter(_base_logger)

def current_year() -> int:
    from datetime import datetime
    return datetime.now().year

# ----------------------------
# Answer modes
# ----------------------------
MODE_INSTRUCTIONS = {
    "Short": "Answer in 2–3 sentences. Be direct.",
    "Detailed": "Give a detailed explanation with clear structure and helpful examples.",
    "Bullet points": "Answer using bullet points. Keep them crisp and actionable.",
    "Explain like I'm 5": "Use very simple words and a friendly analogy. Keep it short.",
    "Interview answer": "Answer like a strong interview response: structured, confident, and practical."
}

class ChatBot:
    """
    ChatBot that supports:
    - Conversation memory (caller passes chat history)
    - Answer modes (caller passes mode)
    """

    def __init__(self, model: str = "gpt-4o-mini"):
        self.model = model
        app_logger.log_info("ChatBot initialized")

    def _system_prompt(self, mode: str) -> str:
        mode_inst = MODE_INSTRUCTIONS.get(mode, MODE_INSTRUCTIONS["Short"])
        return (
            "You are a helpful assistant.\n"
            f"{mode_inst}\n"
            "If the user’s question is unclear, ask one short clarifying question."
        )

    def generate_response(
        self,
        user_input: str,
        history: Optional[List[Dict[str, str]]] = None,
        mode: str = "Short",
        extra_context: str = ""
    ) -> str:
        """
        Generate a normal (non-streaming) response.

        history: list of {"role": "user"/"assistant", "content": "..."} from app session
        mode: one of MODE_INSTRUCTIONS keys
        extra_context: optional extra info (e.g., search snippets) as plain text
        """
        try:
            messages: List[Dict[str, str]] = [{"role": "system", "content": self._system_prompt(mode)}]

            # Add extra context as a system message (optional)
            if extra_context:
                messages.append({"role": "system", "content": f"Additional context:\n{extra_context}"})

            # Add conversation history (optional)
            if history:
                for m in history:
                    r = m.get("role")
                    c = m.get("content", "")
                    if r in ("user", "assistant") and c:
                        messages.append({"role": r, "content": c})

            # Add current user message
            messages.append({"role": "user", "content": user_input})

            resp = client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.4,
            )

            text = (resp.choices[0].message.content or "").strip()
            return text if text else "I can help—please ask a more specific question."

        except Exception as e:
            app_logger.log_error(f"generate_response error: {repr(e)}")
            return "I encountered an error while generating the answer. Please try again."
