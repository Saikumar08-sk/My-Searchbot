import json
import os
from datetime import datetime
from typing import Dict, List
import requests
from bs4 import BeautifulSoup
from urllib.parse import quote_plus
import random
from gtts import gTTS
from groq import Groq
from dotenv import load_dotenv
import time

load_dotenv()

class WebSearch:
    def __init__(self):
        # Rotate between different user agents to avoid detection
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0'
        ]

    def _get_random_headers(self):
        return {
            'User-Agent': random.choice(self.user_agents),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }

    def search(self, query: str, num_results: int = 10) -> Dict[str, any]:
        """
        Scrape DuckDuckGo search results
        """
        encoded_query = quote_plus(query)
        url = f"https://html.duckduckgo.com/html/?q={encoded_query}"
        
        try:
            response = requests.get(url, headers=self._get_random_headers())
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            results = []
            
            # Find all result containers
            for result in soup.select('.result')[:num_results]:
                title_elem = result.select_one('.result__title')
                link_elem = result.select_one('.result__url')
                snippet_elem = result.select_one('.result__snippet')
                
                if title_elem and link_elem:
                    results.append({
                        'title': title_elem.get_text(strip=True),
                        'link': link_elem.get('href', ''),
                        'snippet': snippet_elem.get_text(strip=True) if snippet_elem else ''
                    })
            
            return {"data": results}
            
        except Exception as e:
            print(f"An error occurred: {e}")
            return {"status": "error", "message": str(e)}

def current_year() -> int:
    now: datetime = datetime.now()
    return now.year

def save_to_audio(text: str) -> None:
    tts = gTTS(text=text, lang="en")
    tts.save("output.mp3")

class ChatBot:
    """
    Chatbot using Llama-3.3 through Groq's API with JSON response format
    """
    def __init__(self):
        self.client = Groq(
            api_key=os.environ["GROQ_API_KEY"],
        )
        self.history = [{"role": "system", "content": "You are a helpful assistant. IMPORTANT: Always format your responses as valid JSON with a 'response' field containing your message."}]
        self.search_engine = WebSearch()
    
    def search(self, query: str, num_results: int = 10) -> str:
        """
        Perform a search using DuckDuckGo and return JSON response
        """
        response = self.search_engine.search(query, num_results)
        return json.dumps(response)
    
    def generate_response(self, prompt: str) -> str:
        """
        Generate a response using Llama-3.3 through Groq with JSON format
        """
        
        self.history.append({"role": "user", "content": prompt})
        
        completion = self.client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=self.history,
            temperature=0.7,
            top_p=1,
            stream=False
            
        )
        
        response = completion.choices[0].message.content
        
        self.history.append({"role": "assistant", "content": response})
        
        return response