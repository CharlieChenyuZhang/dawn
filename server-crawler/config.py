"""
Configuration settings for the distributed crawler system.
This defines network locations, ports, and other constants.
"""
import os
from typing import Dict, List

# Primary leader configuration
PRIMARY_LEADER = {
    "id": "leader-primary",
    "host": os.getenv("CRAWLER_PRIMARY_LEADER_HOST", "localhost"),
    "port": int(os.getenv("CRAWLER_PRIMARY_LEADER_PORT", "8300"))
}

# Backup leaders configuration
BACKUP_LEADERS = [
    {
        "id": "leader-backup-1",
        "host": os.getenv("CRAWLER_BACKUP_LEADER_1_HOST", "localhost"),
        "port": int(os.getenv("CRAWLER_BACKUP_LEADER_1_PORT", "8301"))
    },
    {
        "id": "leader-backup-2",
        "host": os.getenv("CRAWLER_BACKUP_LEADER_2_HOST", "localhost"),
        "port": int(os.getenv("CRAWLER_BACKUP_LEADER_2_PORT", "8302"))
    }
]

# Workers configuration
WORKERS = [
    {
        "id": "worker-1",
        "host": os.getenv("CRAWLER_WORKER_1_HOST", "localhost"),
        "port": int(os.getenv("CRAWLER_WORKER_1_PORT", "8401")),
        "focus_area": "general crawling"
    },
    {
        "id": "worker-2",
        "host": os.getenv("CRAWLER_WORKER_2_HOST", "localhost"),
        "port": int(os.getenv("CRAWLER_WORKER_2_PORT", "8402")),
        "focus_area": "media crawling"
    },
    {
        "id": "worker-3",
        "host": os.getenv("CRAWLER_WORKER_3_HOST", "localhost"),
        "port": int(os.getenv("CRAWLER_WORKER_3_PORT", "8403")),
        "focus_area": "news crawling"
    }
]

# Public API endpoint that client communicates with
API_HOST = os.getenv("CRAWLER_API_HOST", "localhost")
API_PORT = int(os.getenv("CRAWLER_API_PORT", "8300"))

# Heartbeat settings
HEARTBEAT_INTERVAL = int(os.getenv("CRAWLER_HEARTBEAT_INTERVAL", "5"))  # seconds
HEARTBEAT_TIMEOUT = int(os.getenv("CRAWLER_HEARTBEAT_TIMEOUT", "30"))   # seconds
ELECTION_TIMEOUT = int(os.getenv("CRAWLER_ELECTION_TIMEOUT", "10"))     # seconds

def get_leader_by_id(leader_id: str) -> Dict:
    if leader_id == PRIMARY_LEADER["id"]:
        return PRIMARY_LEADER
    for leader in BACKUP_LEADERS:
        if leader["id"] == leader_id:
            return leader
    return None

def get_worker_by_id(worker_id: str) -> Dict:
    for worker in WORKERS:
        if worker["id"] == worker_id:
            return worker
    return None

def get_all_nodes() -> List[Dict]:
    return [PRIMARY_LEADER] + BACKUP_LEADERS + WORKERS 