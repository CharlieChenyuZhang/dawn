"""
Shared data models used throughout the distributed system.
"""
from enum import Enum
from typing import Dict, List, Optional
from pydantic import BaseModel
import time
import uuid

class NodeType(str, Enum):
    """Types of nodes in the system"""
    PRIMARY_LEADER = "primary_leader"
    BACKUP_LEADER = "backup_leader"
    WORKER = "worker"

class NodeStatus(str, Enum):
    """Possible status values for nodes"""
    ONLINE = "online"
    OFFLINE = "offline"
    STARTING = "starting"
    FAILING = "failing"
    RECOVERING = "recovering"

class TaskStatus(str, Enum):
    """Possible status values for tasks"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class SummaryTask(BaseModel):
    """Model representing a summarization task"""
    task_id: str
    text: str
    url: Optional[str] = None
    title: Optional[str] = None
    source: Optional[str] = None
    assigned_worker: Optional[str] = None
    status: TaskStatus = TaskStatus.PENDING
    created_at: float = time.time()
    updated_at: float = time.time()
    result: Optional[Dict] = None

class HeartbeatMessage(BaseModel):
    """Heartbeat message sent between nodes"""
    node_id: str
    node_type: NodeType
    status: NodeStatus
    timestamp: float = time.time()
    leader_id: Optional[str] = None
    tasks_count: int = 0
    pending_tasks: int = 0
    completed_tasks: int = 0

class SummaryRequest(BaseModel):
    """Model for incoming summary requests from crawler"""
    text: str
    url: Optional[str] = None
    title: Optional[str] = None
    source: Optional[str] = None

class SummaryResponse(BaseModel):
    """Response model for summary requests"""
    task_id: str
    status: str

class ElectionMessage(BaseModel):
    """Message for leader election"""
    candidate_id: str
    priority: int
    timestamp: float = time.time()

def generate_task_id() -> str:
    """Generate a unique task ID"""
    return str(uuid.uuid4())