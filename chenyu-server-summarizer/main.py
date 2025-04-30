from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from enum import Enum
from typing import List, Optional
import logging
from datetime import datetime
from openai import OpenAI
import os
from dotenv import load_dotenv

app = FastAPI(title="Text Summarizer API")

# Load environment variables from .env file
load_dotenv()

# Configure logging with more detail
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configure OpenAI client
client = OpenAI()  # Will automatically use OPENAI_API_KEY from environment

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
    temperature: Optional[float] = 0.7
    model: Optional[str] = "gpt-4.1"  # Updated to match available models

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

def get_openai_client():
    if client is None:
        logger.error("Attempted to use uninitialized OpenAI client")
        raise HTTPException(
            status_code=500,
            detail="OpenAI client not initialized. Please check your OPENAI_API_KEY."
        )
    return client

@app.post("/summarize", response_model=SummaryResponse)
async def summarize_text(request: SummaryRequest):
    """Summarize the provided text using OpenAI's GPT-4"""
    try:
        config = request.config or SummarizerConfig()
        
        # Call OpenAI API
        response = client.chat.completions.create(
            model=config.model,
            messages=[
                {"role": "system", "content": "You are a helpful assistant that creates concise and accurate summaries."},
                {"role": "user", "content": f"Please summarize the following text in {config.min_length} to {config.max_length} words:\n\n{request.text}"}
            ],
            temperature=config.temperature,
        )
        
        summary = response.choices[0].message.content.strip()
        
        return SummaryResponse(
            original_length=len(request.text),
            summary_length=len(summary),
            summary=summary,
            created_at=datetime.utcnow().isoformat()
        )
    except Exception as e:
        logger.error(f"Error in summarizer: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}

@app.get("/summarizer/status", response_model=List[AgentStatusResponse])
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001, reload=True)  # Note: Using 8001 to avoid conflict with crawler 