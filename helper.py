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
    Stable response generator.
    Uses OpenAI when available.
    Falls back to rule-based answers if OpenAI fails.
    """
    try:
        messages: List[Dict[str, str]] = [{"role": "system", "content": self._system_prompt(mode)}]

        if extra_context:
            messages.append({"role": "system", "content": f"Additional context:\n{extra_context}"})

        if history:
            for m in history:
                if m.get("role") in ("user", "assistant"):
                    messages.append({"role": m["role"], "content": m["content"]})

        messages.append({"role": "user", "content": user_input})

        resp = client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0.4,
        )

        text = (resp.choices[0].message.content or "").strip()
        if text:
            return text

        raise RuntimeError("Empty model response")

    except Exception as e:
        # ---- HARD FALLBACK (PROJECT-SAFE) ----
        app_logger.log_error(f"OpenAI failed, using fallback. Reason: {repr(e)}")
        return self._fallback_answer(user_input, mode)
        
def _fallback_answer(self, question: str, mode: str) -> str:
    q = question.lower()

    if "overfitting" in q and "underfitting" in q:
        if mode == "Short":
            return (
                "Overfitting happens when a model learns noise and performs well on training data "
                "but poorly on new data. Underfitting happens when a model is too simple to capture patterns."
            )
        return (
            "• Overfitting: Model is too complex and memorizes training data.\n"
            "• Underfitting: Model is too simple and misses important patterns.\n\n"
            "Good models balance bias and variance."
        )

    if "k-means" in q:
        return (
            "K-Means is an unsupervised algorithm that groups data into K clusters by minimizing "
            "the distance between points and their cluster center."
        )

    if "ridge" in q and "lasso" in q:
        return (
            "Ridge regression shrinks coefficients but keeps all features, while Lasso can shrink "
            "some coefficients to zero, effectively performing feature selection."
        )

    # Generic fallback
    return (
        "I can help with this question. Please try rephrasing it or ask something more specific."
    )
