import os
import json
import asyncio
import requests
import urllib
import re
from datetime import datetime
from typing import Dict, List, Any, Optional
from bs4 import BeautifulSoup
import logging

# Base logger configuration
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

# This preserves your original API
app_logger = AppLoggerAdapter(_base_logger)

# ============================ CHATBOT CLASS ============================

class ChatBot:
    """
    Chatbot class that interacts with a local AI model.
    """
    def __init__(self) -> None:
        self.history: List[Dict[str, str]] = [{"role": "system", "content": "You are a helpful assistant."}]
        app_logger.log_info("ChatBot instance initialized", level="INFO")

    def generate_response(self, prompt: str) -> str:
        """
        Generate a response from the chatbot.
        """
        self.history.append({"role": "user", "content": prompt})
        app_logger.log_info("User prompt added to history", level="INFO")
        
        # Simulated AI response (replace with actual model call)
        response = f"AI Response to: {prompt}"
        self.history.append({"role": "assistant", "content": response})
        app_logger.log_info("Assistant response generated", level="INFO")
        return response

# ============================ NEWS SEARCH FUNCTION ============================

async def invoke_duckduckgo_news_search(query: str, num: int = 5, location: str = "us-en", time_filter: str = "w") -> Dict[str, Any]:
    """
    Perform a DuckDuckGo News search.
    """
    app_logger.log_info(f"Starting news search for: {query}", level="INFO")
    search_url = f"https://duckduckgo.com/html/?q={query.replace(' ', '+')}&kl={location}&df={time_filter}&ia=news"
    headers = {"User-Agent": "Mozilla/5.0"}
    
    response = requests.get(search_url, headers=headers)
    if response.status_code != 200:
        app_logger.log_error("Failed to fetch news results.")
        return {"status": "error", "message": "Failed to fetch news results"}
    
    soup = BeautifulSoup(response.text, "html.parser")
    search_results = soup.find_all("div", class_="result__body")
    
    async def process_article(result, index: int) -> Optional[Dict[str, Any]]:
        """Processes a single article."""
        try:
            title_tag = result.find("a", class_="result__a")
            if not title_tag:
                return None
            title = title_tag.text.strip()
            raw_link = title_tag["href"]
            match = re.search(r"uddg=(https?%3A%2F%2F[^&]+)", raw_link)
            link = urllib.parse.unquote(match.group(1)) if match else "Unknown Link"
            snippet = result.find("a", class_="result__snippet")
            summary = snippet.text.strip() if snippet else "No summary available."
            return {"num": index + 1, "link": link, "title": title, "summary": summary}
        except Exception as e:
            app_logger.log_error(f"Error processing article: {e}")
            return None
    
    tasks = [process_article(result, index) for index, result in enumerate(search_results[:num])]
    extracted_results = await asyncio.gather(*tasks)
    extracted_results = [res for res in extracted_results if res is not None]
    
    if extracted_results:
        app_logger.log_info(f"News search completed successfully with {len(extracted_results)} results", level="INFO")
        return {"status": "success", "results": extracted_results}
    else:
        app_logger.log_error("No valid news search results found")
        return {"status": "error", "message": "No valid news search results found"}

# ============================ UTILITY FUNCTIONS ============================

def current_year() -> int:
    """Returns the current year as an integer."""
    return datetime.now().year

def save_json(data: Dict[str, Any], filename: str) -> None:
    """Save a dictionary to a JSON file."""
    try:
        with open(filename, "w") as f:
            json.dump(data, f, indent=4)
        app_logger.log_info(f"Data successfully saved to {filename}")
    except Exception as e:
        app_logger.log_error(f"Error saving JSON file: {e}")

def load_json(filename: str) -> Optional[Dict[str, Any]]:
    """Load a dictionary from a JSON file."""
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
    """Log user search queries for analysis."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = {"timestamp": timestamp, "query": query}
    save_json(log_entry, "search_logs.json")
    app_logger.log_info(f"Search query logged: {query}")
