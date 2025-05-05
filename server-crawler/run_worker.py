"""
Script to start a crawler worker node.
Usage: python run_worker.py [1|2|3]
"""
import sys
from crawler_worker import CrawlerWorkerNode
import config
from dotenv import load_dotenv
import os

# Load environment variables from .env file in the current directory
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '.env'))

if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in ["1", "2", "3"]:
        print("Usage: python run_worker.py [1|2|3]")
        sys.exit(1)

    worker_idx = int(sys.argv[1]) - 1
    if worker_idx < 0 or worker_idx >= len(config.WORKERS):
        print("Worker ID must be 1, 2, or 3")
        sys.exit(1)

    worker_info = config.WORKERS[worker_idx]
    worker = CrawlerWorkerNode(
        worker_id=worker_info["id"],
        host=worker_info["host"],
        port=worker_info["port"],
        focus_area=worker_info["focus_area"]
    )
    worker.start() 