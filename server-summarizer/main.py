from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from enum import Enum
from typing import List, Optional
import logging
from datetime import datetime

app = FastAPI(title="Text Summarizer API")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Enums for status
class AgentStatus(str, Enum):
    WORKING = "working"
    FAILED = "failed"
    IDLE = "idle"
    OFFLINE = "offline"
    ONLINE = "online"

# Models
class SummarizerConfig(BaseModel):
    max_length: Optional[int] = 150
    min_length: Optional[int] = 50

class SummaryRequest(BaseModel):
    text: str
    config: Optional[SummarizerConfig] = None

class SummaryResponse(BaseModel):
    original_length: int
    summary_length: int
    summary: str
    created_at: str

class AgentStatusResponse(BaseModel):
    agent_id: str
    status: AgentStatus
    last_updated: str
    processed_count: int

# Mock data for demonstration
MOCK_SUMMARY = """
This is a mock summary that would be returned by the summarization service.
It demonstrates the basic functionality without actual LLM integration.
"""

@app.post("/summarize", response_model=SummaryResponse)
async def summarize_text(request: SummaryRequest):
    """Summarize the provided markdown text"""
    try:
        # In a real implementation, this would call an LLM or other summarization service
        return SummaryResponse(
            original_length=len(request.text),
            summary_length=len(MOCK_SUMMARY),
            summary=MOCK_SUMMARY,
            created_at=datetime.utcnow().isoformat()
        )
    except Exception as e:
        logger.error(f"Error in summarizer: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/status", response_model=List[AgentStatusResponse])
async def get_summarizer_status():
    """Get status of all summarizer agents"""
    return [
        AgentStatusResponse(
            agent_id="summarizer-1",
            status=AgentStatus.ONLINE,
            last_updated=datetime.utcnow().isoformat(),
            processed_count=42
        )
    ]

@app.post("/config")
async def update_summarizer_config(config: SummarizerConfig):
    """Update the summarizer configuration"""
    return {"message": "Configuration updated successfully", "config": config}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)  # Note: Using 8001 to avoid conflict with crawler 