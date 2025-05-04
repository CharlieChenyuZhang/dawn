"""
Configuration settings for the distributed summarizer system.
This defines network locations, ports, and other constants.
"""
import os
from typing import Dict, List

# Primary leader configuration
PRIMARY_LEADER = {
    "id": "leader-primary",
    "host": os.getenv("PRIMARY_LEADER_HOST", "localhost"),
    "port": int(os.getenv("PRIMARY_LEADER_PORT", "8100"))
}

# Backup leaders configuration
BACKUP_LEADERS = [
    {
        "id": "leader-backup-1",
        "host": os.getenv("BACKUP_LEADER_1_HOST", "localhost"),
        "port": int(os.getenv("BACKUP_LEADER_1_PORT", "8101"))
    },
    {
        "id": "leader-backup-2",
        "host": os.getenv("BACKUP_LEADER_2_HOST", "localhost"),
        "port": int(os.getenv("BACKUP_LEADER_2_PORT", "8102"))
    }
]

# Workers configuration
WORKERS = [
    {
        "id": "worker-1",
        "host": os.getenv("WORKER_1_HOST", "localhost"),
        "port": int(os.getenv("WORKER_1_PORT", "8201")),
        "focus_area": "new AI technologies and technical breakthroughs"
    },
    {
        "id": "worker-2",
        "host": os.getenv("WORKER_2_HOST", "localhost"),
        "port": int(os.getenv("WORKER_2_PORT", "8202")),
        "focus_area": "business applications and industry impact"
    },
    {
        "id": "worker-3",
        "host": os.getenv("WORKER_3_HOST", "localhost"),
        "port": int(os.getenv("WORKER_3_PORT", "8203")),
        "focus_area": "ethical considerations and social implications"
    }
]

# Public API endpoint that crawler communicates with
API_HOST = os.getenv("API_HOST", "localhost")
API_PORT = int(os.getenv("API_PORT", "8001"))

# Heartbeat settings
HEARTBEAT_INTERVAL = int(os.getenv("HEARTBEAT_INTERVAL", "5"))  # seconds
HEARTBEAT_TIMEOUT = int(os.getenv("HEARTBEAT_TIMEOUT", "30"))   # seconds (increased from 15 to 30)
ELECTION_TIMEOUT = int(os.getenv("ELECTION_TIMEOUT", "10"))     # seconds

def get_leader_by_id(leader_id: str) -> Dict:
    """Get leader configuration by ID"""
    if leader_id == PRIMARY_LEADER["id"]:
        return PRIMARY_LEADER
    
    for leader in BACKUP_LEADERS:
        if leader["id"] == leader_id:
            return leader
    
    return None

def get_worker_by_id(worker_id: str) -> Dict:
    """Get worker configuration by ID"""
    for worker in WORKERS:
        if worker["id"] == worker_id:
            return worker
    
    return None

def get_all_nodes() -> List[Dict]:
    """Get all node configurations (leaders and workers)"""
    return [PRIMARY_LEADER] + BACKUP_LEADERS + WORKERS