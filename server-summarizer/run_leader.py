"""
Script to start a leader node (primary or backup).
"""
import os
import sys
import logging
from summarizer_leader import SummarizerLeader
import config

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def run_primary_leader():
    """Run primary leader"""
    leader = SummarizerLeader(
        node_id=config.PRIMARY_LEADER["id"],
        host=config.PRIMARY_LEADER["host"],
        port=config.PRIMARY_LEADER["port"],
        is_primary=True
    )
    leader.start()

def run_backup_leader(backup_id):
    """Run backup leader"""
    if backup_id not in [1, 2]:
        logger.error("Backup ID must be 1 or 2")
        sys.exit(1)
    
    backup_info = config.BACKUP_LEADERS[backup_id - 1]
    leader = SummarizerLeader(
        node_id=backup_info["id"],
        host=backup_info["host"],
        port=backup_info["port"],
        is_primary=False
    )
    leader.start()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python run_leader.py [primary|backup1|backup2]")
        sys.exit(1)
    
    mode = sys.argv[1].lower()
    
    if mode == "primary":
        run_primary_leader()
    elif mode == "backup1":
        run_backup_leader(1)
    elif mode == "backup2":
        run_backup_leader(2)
    else:
        print("Invalid mode. Use 'primary', 'backup1', or 'backup2'")
        sys.exit(1)