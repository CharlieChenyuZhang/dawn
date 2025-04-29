from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from enum import Enum
from typing import List, Optional
from agents.crawler.models import CrawlerConfig
from agents.crawler.crawler import start_crawling
import logging

app = FastAPI(title="News Crawler API")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Enums for status
class AgentStatus(str, Enum):
    WORKING = "working"
    FAILED = "failed"
    RECOVERED = "recovered"
    OFFLINE = "offline"
    ONLINE = "online"

# Models
class CrawlerStatus(BaseModel):
    agent_id: str
    status: AgentStatus
    last_updated: str

class SummarizerStatus(BaseModel):
    agent_id: str
    status: AgentStatus
    last_updated: str

class NewsItem(BaseModel):
    id: str
    title: str
    content: str
    url: str
    timestamp: str
    is_summarized: bool

class NewsSummary(BaseModel):
    id: str
    title: str
    summary: str
    url: str
    timestamp: str

# In-memory storage for crawled results
crawled_items: List[NewsItem] = []

# Crawler endpoints
@app.post("/crawl/start")
async def start_crawler(config: CrawlerConfig):
    """Start crawler agents with the provided configuration"""
    try:
        results = await start_crawling(config)
        # Store results in memory
        for result in results:
            crawled_items.append(NewsItem(**result))
        return {"message": f"Crawler completed successfully. Processed {len(results)} URLs."}
    except Exception as e:
        logger.error(f"Error in crawler: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/crawl/status", response_model=List[CrawlerStatus])
async def get_crawler_status():
    """Get status of all crawler agents"""
    # TODO: Implement status checking logic
    return [
        CrawlerStatus(
            agent_id="crawler-1",
            status=AgentStatus.WORKING,
            last_updated="2024-03-19T10:00:00Z"
        )
    ]

# Summarizer endpoints
@app.post("/summarize/start")
async def start_summarizer():
    """Start summarizer agents manually"""
    # TODO: Implement summarizer start logic
    return {"message": "Summarizer agents started successfully"}

@app.get("/summarize/status", response_model=List[SummarizerStatus])
async def get_summarizer_status():
    """Get status of all summarizer agents"""
    # TODO: Implement summarizer status checking logic
    return [
        SummarizerStatus(
            agent_id="summarizer-1",
            status=AgentStatus.ONLINE,
            last_updated="2024-03-19T10:00:00Z"
        )
    ]

# News endpoints
@app.get("/news/live", response_model=List[NewsItem])
async def get_live_news():
    """Get crawled but not necessarily summarized news"""
    return crawled_items

@app.get("/news/summaries", response_model=List[NewsSummary])
async def get_news_summaries():
    """Get summarized and deduplicated news"""
    # TODO: Implement summarized news fetching logic
    return []

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 