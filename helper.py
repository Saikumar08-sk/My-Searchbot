import os
import json
import requests
import urllib.parse
import re
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional

from bs4 import BeautifulSoup

# ============================ OPENAI CLIENT (SAFE INIT) ============================

# Try Streamlit secrets first (Cloud), then environment variables (local)
try:
    import streamlit as st
    OPENAI_API_KEY = st.secrets.get("OPENAI_API_KEY", None)
except Exception:
    OPENAI_API_KEY = None

if not OPENAI_API_KEY:
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not OPENAI_API_KEY:
    raise RuntimeError(
        "OPENAI_API_KEY is not set. "
        "Add it in Streamlit Cloud → App → Settings → Secrets as:\n"
        "OPENAI_API_KEY = \"sk-...\""
    )

from openai import OpenAI
client = OpenAI(api_key=OPENAI_API_KEY)


# ============================ LOGGER (Adapter – keeps your API) ============================

_base_logger = logging.getLogger("my-searchbot")
if not _base_logger.handlers:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s"
    )

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


# ============================ CHATBOT CLASS (REAL-TIME STREAMING) ============================

class ChatBot:
    """
    ChatBot using OpenAI with:
    - generate_response(): normal full response
    - stream_answer(): TRUE real-time streaming (token-by-token)
    """

    def __init__(self, model: str = "gpt-4o-mini") -> None:
        self.model = model
        self.history: List[Dict[str, str]] = [
            {"role": "system", "content": "You are a helpful assistant. Answer clearly and concisely."}
        ]
        app_logger.log_info("ChatBot instance initialized")

    def _build_messages(self, user_input: str, context: str = "") -> List[Dict[str, str]]:
        messages = list(self.history)

        if context:
            messages.append({
                "role": "system",
                "content": f"Use the following web context if relevant:\n\n{context}"
            })

        messages.append({"role": "user", "content": user_input})
        return messages

    def generate_response(self, user_input: str, context: str = "") -> str:
        """Non-stream response (fallback)."""
        try:
            messages = self._build_messages(user_input, context)

            resp = client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.4
            )

            text = resp.choices[0].message.content or ""
            text = text.strip()

            self.history.append({"role": "user", "content": user_input})
            self.history.append({"role": "assistant", "content": text})

            return text if text else "I can help—please ask a more specific question."

        except Exception as e:
            app_logger.log_error(f"generate_response error: {e}")
            return "I encountered an error while generating a response."

    def stream_answer(self, user_input: str, context: str = ""):
        """
        TRUE real-time streaming generator.
        Use with: st.write_stream(ChatBot().stream_answer(...))
        """
        try:
            messages = self._build_messages(user_input, context)

            stream = client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.4,
                stream=True
            )

            collected = []

            for event in stream:
                delta = event.choices[0].delta
                if delta and delta.content:
                    chunk = delta.content
                    collected.append(chunk)
                    yield chunk

            final_text = "".join(collected).strip()
            self.history.append({"role": "user", "content": user_input})
            self.history.append({"role": "assistant", "content": final_text})

        except Exception as e:
            app_logger.log_error(f"stream_answer error: {e}")
            yield "I encountered an error while streaming the response."


# ============================ DUCKDUCKGO NEWS SEARCH ============================

def invoke_duckduckgo_news_search(
    query: str,
    num: int = 5,
    location: str = "us-en",
    time_filter: str = "w"
) -> Dict[str, Any]:
    """Synchronous DuckDuckGo News search."""
    try:
        q = (query or "").strip()
        if not q:
            return {"status": "error", "message": "Empty query"}

        search_url = (
            f"https://duckduckgo.com/html/?q={urllib.parse.quote_plus(q)}"
            f"&kl={location}&df={time_filter}&ia=news"
        )

        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(search_url, headers=headers, timeout=15)

        if resp.status_code != 200:
            return {"status": "error", "message": "Failed to fetch news results"}

        soup = BeautifulSoup(resp.text, "html.parser")
        blocks = soup.find_all("div", class_="result__body")

        results = []
        for idx, block in enumerate(blocks[:num]):
            title_tag = block.find("a", class_="result__a")
            if not title_tag:
                continue

            title = title_tag.get_text(strip=True)
            raw_link = title_tag.get("href", "")
            match = re.search(r"uddg=(https?%3A%2F%2F[^&]+)", raw_link)
            link = urllib.parse.unquote(match.group(1)) if match else raw_link

            snippet = block.find("a", class_="result__snippet")
            summary = snippet.get_text(strip=True) if snippet else "No summary available."

            results.append({
                "num": idx + 1,
                "title": title,
                "link": link,
                "summary": summary
            })

        if results:
            return {"status": "success", "results": results}

        return {"status": "error", "message": "No search results available."}

    except Exception as e:
        app_logger.log_error(f"DuckDuckGo error: {e}")
        return {"status": "error", "message": "No search results available."}


def format_news_results_html(payload: Dict[str, Any]) -> str:
    """Format news results as HTML for Streamlit."""
    if not payload or payload.get("status") != "success":
        return ""

    html = []
    for item in payload.get("results", []):
        html.append(
            f"<p><b>{item['num']}. "
            f"<a href='{item['link']}' target='_blank'>{item['title']}</a></b><br/>"
            f"{item['summary']}</p>"
        )
    return "\n".join(html)


# ============================ UTILITIES ============================

def current_year() -> int:
    return datetime.now().year

def save_json(data: Dict[str, Any], filename: str) -> None:
    try:
        with open(filename, "w") as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        app_logger.log_error(f"save_json error: {e}")

def load_json(filename: str) -> Optional[Dict[str, Any]]:
    try:
        with open(filename, "r") as f:
            return json.load(f)
    except Exception:
        return None
