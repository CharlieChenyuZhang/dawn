"""
Shared data models used throughout the distributed crawler system.
"""
from enum import Enum
from typing import Dict, List, Optional
from pydantic import BaseModel
import time
import uuid

class NodeType(str, Enum):
    PRIMARY_LEADER = "primary_leader"
    BACKUP_LEADER = "backup_leader"
    WORKER = "worker"

class NodeStatus(str, Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    STARTING = "starting"
    FAILING = "failing"
    RECOVERING = "recovering"

class TaskStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class CrawlTask(BaseModel):
    task_id: str
    url: str
    max_depth: Optional[int] = 2
    timeout: Optional[int] = 30
    formats: Optional[List[str]] = ["markdown", "html"]
    assigned_worker: Optional[str] = None
    status: TaskStatus = TaskStatus.PENDING
    created_at: float = time.time()
    updated_at: float = time.time()
    result: Optional[Dict] = None

class HeartbeatMessage(BaseModel):
    node_id: str
    node_type: NodeType
    status: NodeStatus
    timestamp: float = time.time()
    leader_id: Optional[str] = None
    tasks_count: int = 0
    pending_tasks: int = 0
    completed_tasks: int = 0

class CrawlRequest(BaseModel):
    urls: List[str]
    max_depth: Optional[int] = 2
    timeout: Optional[int] = 30
    formats: Optional[List[str]] = ["markdown", "html"]

class CrawlResponse(BaseModel):
    markdown: str
    summary: Optional[str]
    url: str
    timestamp: str
    map: List[str]

class CrawlMultiResponse(BaseModel):
    results: List[CrawlResponse]
    timestamp: str

class ElectionMessage(BaseModel):
    candidate_id: str
    priority: int
    timestamp: float = time.time()

def generate_task_id() -> str:
    return str(uuid.uuid4()) 