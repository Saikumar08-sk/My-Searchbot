import os
import logging
from typing import List, Dict, Optional

# ===================== LOAD OPENAI KEY =====================
try:
    import streamlit as st
    OPENAI_API_KEY = st.secrets.get("OPENAI_API_KEY")
except Exception:
    OPENAI_API_KEY = None

if not OPENAI_API_KEY:
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not OPENAI_API_KEY:
    raise RuntimeError(
        "OPENAI_API_KEY is not set. Add it in Streamlit Cloud → Settings → Secrets."
    )

from openai import OpenAI
client = OpenAI(api_key=OPENAI_API_KEY)

# ===================== LOGGER =====================
_base_logger = logging.getLogger("searchbot")
if not _base_logger.handlers:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s"
    )

class AppLoggerAdapter:
    def __init__(self, logger):
        self.logger = logger

    def log_info(self, msg):
        self.logger.info(msg)

    def log_error(self, msg):
        self.logger.error(msg)

app_logger = AppLoggerAdapter(_base_logger)

# ===================== UTILS =====================
def current_year() -> int:
    from datetime import datetime
    return datetime.now().year

# ===================== ANSWER MODES =====================
MODE_INSTRUCTIONS = {
    "Short": "Answer briefly in 2–3 sentences.",
    "Detailed": "Give a detailed explanation with examples.",
    "Bullet points": "Answer using clear bullet points.",
    "Explain like I'm 5": "Use very simple language and an analogy.",
    "Interview answer": "Answer like a confident interview response."
}

# ===================== CHATBOT =====================
class ChatBot:
    def __init__(self, model: str = "gpt-4o-mini"):
        self.model = model
        app_logger.log_info("ChatBot initialized")

    def _system_prompt(self, mode: str) -> str:
        return MODE_INSTRUCTIONS.get(mode, MODE_INSTRUCTIONS["Short"])

    def generate_response(
        self,
        user_input: str,
        history: Optional[List[Dict[str, str]]] = None,
        mode: str = "Short"
    ) -> str:
        try:
            messages = [
                {"role": "system", "content": self._system_prompt(mode)}
            ]

            if history:
                for msg in history:
                    if msg.get("role") in ("user", "assistant"):
                        messages.append({
                            "role": msg["role"],
                            "content": msg["content"]
                        })

            messages.append({"role": "user", "content": user_input})

            response = client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.4
            )

            answer = response.choices[0].message.content
            if answer:
                return answer.strip()

            raise RuntimeError("Empty response")

        except Exception as e:
            app_logger.log_error(f"OpenAI failed: {repr(e)}")
            return self._fallback_answer(user_input, mode)

    def _fallback_answer(self, question: str, mode: str) -> str:
        q = question.lower()

        if "overfitting" in q and "underfitting" in q:
            return (
                "Overfitting means the model memorizes training data and fails on new data. "
                "Underfitting means the model is too simple to learn patterns."
            )

        if "k-means" in q:
            return (
                "K-Means is an unsupervised algorithm that groups data into K clusters "
                "based on distance from cluster centers."
            )

        if "ridge" in q and "lasso" in q:
            return (
                "Ridge regression shrinks coefficients but keeps all features, "
                "while Lasso can reduce some coefficients to zero."
            )

        return (
            "I can help with this question. Please try rephrasing it or ask something more specific."
        )
