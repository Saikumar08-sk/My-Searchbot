import os
import json
import requests
import urllib.parse
import re
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional

from bs4 import BeautifulSoup
from openai import OpenAI


# ============================ OPENAI CLIENT ============================
OPENAI_API_KEY = "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"
import os
from openai import OpenAI

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY is not set. Check Streamlit Secrets.")

client = OpenAI(api_key=OPENAI_API_KEY)


# ============================ LOGGER (Adapter to match your calls) ============================

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


# ============================ CHATBOT CLASS ============================

class ChatBot:
    """
    Chatbot class that interacts with OpenAI.
    Provides BOTH:
      - generate_response() -> full text (non-stream)
      - stream_answer() -> generator for real-time streaming in Streamlit
    """

    def __init__(self, model: str = "gpt-4o-mini") -> None:
        self.model = model
        self.history: List[Dict[str, str]] = [
            {"role": "system", "content": "You are a helpful assistant. Answer clearly and concisely."}
        ]
        app_logger.log_info("ChatBot instance initialized", level="INFO")

    def _build_messages(self, user_input: str, context: str = "") -> List[Dict[str, str]]:
        """
        Build message list for OpenAI.
        Context is inserted as an additional system message (so it guides the answer).
        """
        messages = list(self.history)

        ctx = (context or "").strip()
        if ctx:
            messages.append({
                "role": "system",
                "content": f"Use the following web context if it is relevant:\n\n{ctx}"
            })

        messages.append({"role": "user", "content": user_input})
        return messages

    def generate_response(self, user_input: str, context: str = "") -> str:
        """
        Non-stream response (returns full string).
        """
        try:
            app_logger.log_info("Generating non-stream response", level="INFO")

            messages = self._build_messages(user_input, context)

            resp = client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.4
            )

            text = resp.choices[0].message.content or ""
            text = text.strip()

            # Store in history
            self.history.append({"role": "user", "content": user_input})
            self.history.append({"role": "assistant", "content": text})

            return text if text else "I can help—please ask a more specific question."

        except Exception as e:
            app_logger.log_error(f"OpenAI generate_response error: {e}")
            return "I encountered an error while generating a response. Please try again."

    def stream_answer(self, user_input: str, context: str = ""):
        """
        True real-time streaming generator (use with st.write_stream()).
        Yields text chunks as the model produces them.
        """
        try:
            app_logger.log_info("Streaming response started", level="INFO")

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

            # Save final response to history (optional but useful)
            final_text = "".join(collected).strip()
            self.history.append({"role": "user", "content": user_input})
            self.history.append({"role": "assistant", "content": final_text})

        except Exception as e:
            app_logger.log_error(f"OpenAI stream_answer error: {e}")
            yield "I encountered an error while streaming the response. Please try again."


# ============================ DUCKDUCKGO NEWS SEARCH (SYNC) ============================

def invoke_duckduckgo_news_search(
    query: str,
    num: int = 5,
    location: str = "us-en",
    time_filter: str = "w"
) -> Dict[str, Any]:
    """
    Synchronous DuckDuckGo News search.
    Returns a dict:
      {"status": "success", "results": [...]}
      or {"status": "error", "message": "..."}
    """
    try:
        q = (query or "").strip()
        if not q:
            return {"status": "error", "message": "Empty query"}

        app_logger.log_info(f"Starting news search for: {q}", level="INFO")

        search_url = (
            f"https://duckduckgo.com/html/?q={urllib.parse.quote_plus(q)}"
            f"&kl={location}&df={time_filter}&ia=news"
        )

        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(search_url, headers=headers, timeout=15)

        if resp.status_code != 200:
            app_logger.log_error(f"Failed to fetch news results. HTTP {resp.status_code}")
            return {"status": "error", "message": "Failed to fetch news results"}

        soup = BeautifulSoup(resp.text, "html.parser")
        search_results = soup.find_all("div", class_="result__body")

        results = []
        for idx, result in enumerate(search_results[:num]):
            title_tag = result.find("a", class_="result__a")
            if not title_tag:
                continue

            title = title_tag.get_text(strip=True)
            raw_link = title_tag.get("href", "")

            # DuckDuckGo redirects often include "uddg="
            match = re.search(r"uddg=(https?%3A%2F%2F[^&]+)", raw_link)
            link = urllib.parse.unquote(match.group(1)) if match else raw_link

            snippet = result.find("a", class_="result__snippet")
            summary = snippet.get_text(strip=True) if snippet else "No summary available."

            results.append({
                "num": idx + 1,
                "title": title,
                "link": link,
                "summary": summary
            })

        if results:
            app_logger.log_info(f"News search completed: {len(results)} results", level="INFO")
            return {"status": "success", "results": results}

        return {"status": "error", "message": "No search results available."}

    except Exception as e:
        app_logger.log_error(f"DuckDuckGo news search error: {e}")
        return {"status": "error", "message": "No search results available."}


def format_news_results_html(search_payload: Dict[str, Any]) -> str:
    """
    Convert search results dict into HTML for Streamlit expander.
    """
    if not search_payload or search_payload.get("status") != "success":
        return ""

    items = search_payload.get("results", [])
    if not items:
        return ""

    html = ["<div>"]
    for item in items:
        title = item.get("title", "Untitled")
        link = item.get("link", "#")
        summary = item.get("summary", "")
        html.append(
            f"<p><b>{item.get('num', '')}. "
            f"<a href='{link}' target='_blank'>{title}</a></b><br/>"
            f"{summary}</p>"
        )
    html.append("</div>")
    return "\n".join(html)


# ============================ UTILITY FUNCTIONS ============================

def current_year() -> int:
    return datetime.now().year

def save_json(data: Dict[str, Any], filename: str) -> None:
    try:
        with open(filename, "w") as f:
            json.dump(data, f, indent=4)
        app_logger.log_info(f"Data successfully saved to {filename}")
    except Exception as e:
        app_logger.log_error(f"Error saving JSON file: {e}")

def load_json(filename: str) -> Optional[Dict[str, Any]]:
    try:
        with open(filename, "r") as f:
            data = json.load(f)
        app_logger.log_info(f"Data successfully loaded from {filename}")
        return data
    except FileNotFoundError:
        app_logger.log_warning(f"File {filename} not found.")
        return None
    except Exception as e:
        app_logger.log_error(f"Error loading JSON file: {e}")
        return None

def log_search_query(query: str) -> None:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = {"timestamp": timestamp, "query": query}
    save_json(log_entry, "search_logs.json")
    app_logger.log_info(f"Search query logged: {query}")
