from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, HttpUrl
from enum import Enum
from typing import List, Optional, Dict, Any
import logging
from datetime import datetime
import os
from dotenv import load_dotenv
from firecrawl import FirecrawlApp, ScrapeOptions
import httpx

# Load environment variables from .env file
load_dotenv()

app = FastAPI(title="Web Crawler API")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # React app's default port
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FirecrawlApp
firecrawl = FirecrawlApp(api_key=os.getenv("FIRECRAWL_API_KEY"))

# Constants
SUMMARIZER_URL = "http://localhost:8001/summarize"

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
    summary: Optional[str]
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
        
        # Get the site map
        map_result = firecrawl.map_url(str(request.urls[0])).links
        
        # Call the summarizer service
        summary = None
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    SUMMARIZER_URL,
                    json={"text": page_content}
                )
                if response.status_code == 200:
                    summary_data = response.json()
                    summary = summary_data["summary"]
                else:
                    logger.warning(f"Failed to get summary: {response.status_code}")
        except Exception as e:
            logger.warning(f"Error calling summarizer service: {str(e)}")
        
        return CrawlResponse(
            markdown=page_content,
            summary=summary,
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