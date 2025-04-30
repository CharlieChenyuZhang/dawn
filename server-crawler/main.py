from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, HttpUrl
from enum import Enum
from typing import List, Optional, Dict, Any
import logging
from datetime import datetime
import os
from dotenv import load_dotenv
from firecrawl import FirecrawlApp, ScrapeOptions

# Load environment variables from .env file
load_dotenv()

app = FastAPI(title="Web Crawler API")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FirecrawlApp
firecrawl = FirecrawlApp(api_key=os.getenv("FIRECRAWL_API_KEY"))

# Enums for status
class CrawlerStatus(str, Enum):
    CRAWLING = "crawling"
    FAILED = "failed"
    IDLE = "idle"
    OFFLINE = "offline"
    ONLINE = "online"

# Models
class CrawlRequest(BaseModel):
    urls: List[HttpUrl]
    max_depth: Optional[int] = 2
    timeout: Optional[int] = 30
    formats: Optional[List[str]] = ["markdown", "html"]

class CrawlResponse(BaseModel):
    markdown: str
    url: str
    timestamp: str
    map: list[str]

class CrawlerStatusResponse(BaseModel):
    crawler_id: str
    status: CrawlerStatus
    last_updated: str
    urls_processed: int
    active_jobs: int

# Store active crawl jobs
active_jobs: Dict[str, Dict[str, Any]] = {}

@app.post("/crawl", response_model=CrawlResponse)
async def crawl_urls(request: CrawlRequest):
    """Start crawling the provided URLs"""
    try:
        # Get the page content
        page = firecrawl.scrape_url(str(request.urls[0]), formats=['markdown', 'html'])
        print(f"Page: {page}")
        page_content = page.markdown
        
        
        map_result = firecrawl.map_url(str(request.urls[0])).links
        return CrawlResponse(
            markdown=page_content,
            map=map_result,
            url=str(request.urls[0]),
            timestamp=datetime.utcnow().isoformat()
        )
        
        
    except Exception as e:
        logger.error(f"Error crawling website: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True) 