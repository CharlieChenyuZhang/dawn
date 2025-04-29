import asyncio
import aiohttp
from openai import OpenAI
import logging
from bs4 import BeautifulSoup
from datetime import datetime
from typing import List, Dict, Any
from .models import CrawlerConfig
import os
from dotenv import load_dotenv
import uuid

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class WebCrawler:
    def __init__(self, config: CrawlerConfig):
        self.config = config
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable is not set")
        # Use regular OpenAI client with just the api_key
        self.client = OpenAI(api_key=api_key)
        self.results = []

    async def extract_content(self, url: str, session: aiohttp.ClientSession) -> Dict[str, Any]:
        try:
            timeout = aiohttp.ClientTimeout(total=30)  # 30 seconds timeout
            async with session.get(url, timeout=timeout, ssl=True) as response:
                if response.status == 200:
                    html = await response.text()
                    soup = BeautifulSoup(html, 'html.parser')
                    
                    # Remove script, style, and other non-content elements
                    for element in soup(["script", "style", "nav", "footer", "header", "aside"]):
                        element.decompose()
                    
                    # Get text content
                    text = soup.get_text(separator='\n', strip=True)
                    
                    # Use LLM to analyze and extract relevant information
                    analysis = await self._analyze_with_llm(text, url)
                    
                    return {
                        "id": str(uuid.uuid4()),
                        "url": url,
                        "title": analysis.get("title", ""),
                        "content": analysis.get("content", ""),
                        "timestamp": datetime.utcnow().isoformat(),
                        "is_summarized": False
                    }
                else:
                    logger.error(f"Failed to fetch {url}: Status {response.status}")
                    return None
        except asyncio.TimeoutError:
            logger.error(f"Timeout while fetching {url}")
            return None
        except aiohttp.ClientError as e:
            logger.error(f"Network error while fetching {url}: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error while crawling {url}: {str(e)}")
            return None

    async def _analyze_with_llm(self, text: str, url: str) -> Dict[str, str]:
        # Truncate text if too long (considering token limits)
        max_chars = 4000
        if len(text) > max_chars:
            text = text[:max_chars] + "..."

        try:
            # Use the synchronous client
            response = self.client.chat.completions.create(
                model=self.config.llm_model,
                messages=[
                    {
                        "role": "system",
                        "content": """You are a web content analyzer. Extract the main article content and title from the provided text.
                        Ignore navigation menus, footers, and other irrelevant content.
                        Format your response exactly as follows:
                        Title: [The main title of the article]
                        Content: [The main content of the article]"""
                    },
                    {
                        "role": "user",
                        "content": f"Analyze this content from {url} and extract the title and main content:\n\n{text}"
                    }
                ],
                temperature=0.3  # Lower temperature for more consistent output
            )
            
            # Parse the response
            result = response.choices[0].message.content
            try:
                # Split by 'Title:' and 'Content:' markers
                parts = result.split('\n', 1)
                title = parts[0].replace('Title:', '').strip()
                content = parts[1].replace('Content:', '').strip() if len(parts) > 1 else ''
                
                return {
                    "title": title or "Untitled",
                    "content": content or "No content extracted"
                }
            except Exception as e:
                logger.error(f"Error parsing LLM response: {str(e)}")
                return {"title": "Error in parsing", "content": result}
                
        except Exception as e:
            logger.error(f"Error in LLM analysis: {str(e)}")
            return {"title": "Error in analysis", "content": text[:1000]}

    async def crawl(self) -> List[Dict[str, Any]]:
        # Configure client session with default timeout and SSL context
        timeout = aiohttp.ClientTimeout(total=60)  # 60 seconds total timeout
        connector = aiohttp.TCPConnector(ssl=True)
        
        async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
            tasks = [self.extract_content(str(url), session) for url in self.config.websites]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Filter out None results and handle exceptions
            self.results = [
                r for r in results 
                if r is not None and not isinstance(r, Exception)
            ]
            
            return self.results

async def start_crawling(config: CrawlerConfig) -> List[Dict[str, Any]]:
    crawler = WebCrawler(config)
    return await crawler.crawl() 