"""
Script to start a crawler leader node.
Usage: python run_leader.py [primary|backup-1|backup-2]
"""
import sys
from crawler_leader import CrawlerLeader
import config

if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in ["primary", "backup-1", "backup-2"]:
        print("Usage: python run_leader.py [primary|backup-1|backup-2]")
        sys.exit(1)

    role = sys.argv[1]
    if role == "primary":
        node = config.PRIMARY_LEADER
        is_primary = True
    elif role == "backup-1":
        node = config.BACKUP_LEADERS[0]
        is_primary = False
    else:
        node = config.BACKUP_LEADERS[1]
        is_primary = False

    leader = CrawlerLeader(
        node_id=node["id"],
        host=node["host"],
        port=node["port"],
        is_primary=is_primary
    )
    leader.start() 