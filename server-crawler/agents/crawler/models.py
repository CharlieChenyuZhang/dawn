from pydantic import BaseModel, HttpUrl
from typing import List, Optional

class CrawlerConfig(BaseModel):
    websites: List[HttpUrl]
    max_depth: Optional[int] = 1
    llm_model: Optional[str] = "gpt-3.5-turbo" 