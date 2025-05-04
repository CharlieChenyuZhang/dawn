"""
Script to start a worker node.
"""
import os
import sys
import logging
from summarizer_worker import SummarizerWorkerNode
import config

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def run_worker(worker_id):
    """Run worker with specified ID"""
    if worker_id not in [1, 2, 3]:
        logger.error("Worker ID must be 1, 2, or 3")
        sys.exit(1)
    
    worker_info = config.WORKERS[worker_id - 1]
    worker = SummarizerWorkerNode(
        worker_id=worker_info["id"],
        host=worker_info["host"],
        port=worker_info["port"],
        focus_area=worker_info["focus_area"]
    )
    worker.start()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python run_worker.py [1|2|3]")
        sys.exit(1)
    
    try:
        worker_id = int(sys.argv[1])
        run_worker(worker_id)
    except ValueError:
        print("Worker ID must be a number: 1, 2, or 3")
        sys.exit(1)