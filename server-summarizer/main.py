from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from enum import Enum
from typing import List, Optional, Dict
import logging
from datetime import datetime
import os
from dotenv import load_dotenv

from summarizer import SummarizerWorker

# Load environment variables from .env file
load_dotenv()

app = FastAPI(title="Text Summarizer API")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create summarizer workers
summarizers = {
    1: SummarizerWorker(agent_id=1),
    2: SummarizerWorker(agent_id=2),
    3: SummarizerWorker(agent_id=3)
}

# Enums for status
class AgentStatus(str, Enum):
    WORKING = "working"
    FAILED = "failed"
    IDLE = "idle"
    OFFLINE = "offline"
    ONLINE = "online"

# Models
class SummarizerConfig(BaseModel):
    max_words: Optional[int] = 100
    agent_id: Optional[int] = None  # If None, will use all agents

class SummaryRequest(BaseModel):
    text: str
    title: Optional[str] = "Untitled Article"
    url: Optional[str] = None
    source: Optional[str] = None
    config: Optional[SummarizerConfig] = None

class SummaryResponse(BaseModel):
    original_length: int
    summary_length: int
    summary: str
    focus_area: Optional[str] = None
    agent_id: Optional[int] = None
    created_at: str

class AgentStatusResponse(BaseModel):
    agent_id: str
    status: AgentStatus
    last_updated: str
    processed_count: int
    focus_area: str

@app.post("/summarize", response_model=SummaryResponse)
async def summarize_text(request: SummaryRequest):
    """Summarize the provided markdown text"""
    try:
        config = request.config or SummarizerConfig()
        
        # Prepare metadata
        metadata = {
            "title": request.title,
            "url": request.url,
            "source": request.source
        }
        
        # If specific agent is requested, use only that agent
        if config.agent_id and config.agent_id in summarizers:
            agent = summarizers[config.agent_id]
            result = agent.process_article(
                request.text, 
                metadata, 
                max_words=config.max_words
            )
            
            return SummaryResponse(
                original_length=len(request.text),
                summary_length=len(result["summary"]),
                summary=result["summary"],
                focus_area=result["focus_area"],
                agent_id=result["agent_id"],
                created_at=datetime.utcnow().isoformat()
            )
        
        # If no specific agent, use the first one (technologically focused)
        # You could implement logic to use all agents and combine their summaries
        agent = summarizers[1]
        result = agent.process_article(
            request.text, 
            metadata, 
            max_words=config.max_words
        )
        
        return SummaryResponse(
            original_length=len(request.text),
            summary_length=len(result["summary"]),
            summary=result["summary"],
            focus_area=result["focus_area"],
            agent_id=result["agent_id"],
            created_at=datetime.utcnow().isoformat()
        )
    except Exception as e:
        logger.error(f"Error in summarizer: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/summarize_all", response_model=List[SummaryResponse])
async def summarize_text_all_agents(request: SummaryRequest):
    """Summarize the provided markdown text using all available agents"""
    try:
        config = request.config or SummarizerConfig()
        
        # Prepare metadata
        metadata = {
            "title": request.title,
            "url": request.url,
            "source": request.source
        }
        
        results = []
        for agent_id, agent in summarizers.items():
            try:
                result = agent.process_article(
                    request.text, 
                    metadata, 
                    max_words=config.max_words
                )
                
                results.append(SummaryResponse(
                    original_length=len(request.text),
                    summary_length=len(result["summary"]),
                    summary=result["summary"],
                    focus_area=result["focus_area"],
                    agent_id=result["agent_id"],
                    created_at=datetime.utcnow().isoformat()
                ))
            except Exception as e:
                logger.error(f"Error with agent {agent_id}: {str(e)}")
                # Continue with other agents even if one fails
        
        if not results:
            raise HTTPException(status_code=500, detail="All summarization agents failed")
            
        return results
    except Exception as e:
        logger.error(f"Error in summarizer: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/summarizer/status", response_model=List[AgentStatusResponse])
async def get_summarizer_status():
    """Get status of all summarizer agents"""
    results = []
    
    for agent_id, agent in summarizers.items():
        results.append(
            AgentStatusResponse(
                agent_id=f"summarizer-{agent_id}",
                status=AgentStatus.ONLINE,
                last_updated=datetime.utcnow().isoformat(),
                processed_count=agent.processed_count,
                focus_area=agent.focus_areas[agent_id]
            )
        )
    
    return results

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=True)  # Using 8001 to avoid conflict with crawler