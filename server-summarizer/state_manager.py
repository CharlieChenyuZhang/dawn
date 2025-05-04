"""
State manager for tasks in the distributed summarizer system.
Keeps track of task state and assignments.
"""
import time
import threading
import logging
from typing import Dict, List, Optional, Set
from queue import Queue, Empty
import json
import requests

from shared_models import SummaryTask, TaskStatus, generate_task_id
import config

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class StateManager:
    """Manages task state and task queue"""
    
    def __init__(self, is_leader: bool = False):
        """
        Initialize state manager
        
        Args:
            is_leader: Whether this instance is the leader
        """
        self.is_leader = is_leader
        self.tasks: Dict[str, SummaryTask] = {}
        self.completed_urls: Set[str] = set()
        self.task_queue = Queue()
        self.lock = threading.Lock()
        
        # For leader election and state synchronization
        self.state_version = 0
        self.last_sync_time = 0
        
    def add_task(self, task: SummaryTask) -> str:
        """
        Add a new task to the state
        
        Args:
            task: The task to add
            
        Returns:
            The task ID
        """
        with self.lock:
            # Check if URL already processed
            if task.url and task.url in self.completed_urls:
                logger.info(f"URL {task.url} already processed, skipping")
                for existing_task_id, existing_task in self.tasks.items():
                    if existing_task.url == task.url and existing_task.status == TaskStatus.COMPLETED:
                        return existing_task_id
            
            # Store task
            self.tasks[task.task_id] = task
            
            # Add to queue if we're the leader
            if self.is_leader:
                self.task_queue.put(task.task_id)
                logger.info(f"Added task {task.task_id} to queue")
            
            # Update state version
            self.state_version += 1
            
            return task.task_id
    
    def get_next_task(self) -> Optional[SummaryTask]:
        """
        Get the next task from the queue
        
        Returns:
            The next task or None if queue is empty
        """
        if not self.is_leader:
            logger.warning("Non-leader tried to get next task")
            return None
        
        try:
            task_id = self.task_queue.get(block=False)
            with self.lock:
                task = self.tasks.get(task_id)
                if task:
                    task.status = TaskStatus.PROCESSING
                    task.updated_at = time.time()
                    self.state_version += 1
                    return task
                else:
                    logger.error(f"Task {task_id} in queue but not found in tasks dictionary")
                    return None
        except Empty:
            return None
    
    def update_task(self, task_id: str, status: TaskStatus, result: Optional[Dict] = None) -> bool:
        """
        Update a task's status and result
        
        Args:
            task_id: The task ID
            status: New status
            result: Optional result data
            
        Returns:
            True if successful, False otherwise
        """
        with self.lock:
            task = self.tasks.get(task_id)
            if not task:
                logger.warning(f"Tried to update non-existent task {task_id}")
                return False
            
            task.status = status
            task.updated_at = time.time()
            
            if result:
                task.result = result
            
            # Mark URL as completed if task completed
            if status == TaskStatus.COMPLETED and task.url:
                self.completed_urls.add(task.url)
            
            # Update state version
            self.state_version += 1
            
            return True
    
    def assign_task(self, task_id: str, worker_id: str) -> bool:
        """
        Assign a task to a worker
        
        Args:
            task_id: The task ID
            worker_id: The worker ID
            
        Returns:
            True if successful, False otherwise
        """
        with self.lock:
            task = self.tasks.get(task_id)
            if not task:
                logger.warning(f"Tried to assign non-existent task {task_id}")
                return False
            
            task.assigned_worker = worker_id
            task.status = TaskStatus.PROCESSING
            task.updated_at = time.time()
            
            # Update state version
            self.state_version += 1
            
            return True
    
    def get_task(self, task_id: str) -> Optional[SummaryTask]:
        """Get a task by ID"""
        with self.lock:
            return self.tasks.get(task_id)
    
    def get_all_tasks(self) -> List[SummaryTask]:
        """Get all tasks"""
        with self.lock:
            return list(self.tasks.values())
    
    def get_stats(self) -> Dict:
        """Get task statistics"""
        with self.lock:
            total = len(self.tasks)
            pending = sum(1 for t in self.tasks.values() if t.status == TaskStatus.PENDING)
            processing = sum(1 for t in self.tasks.values() if t.status == TaskStatus.PROCESSING)
            completed = sum(1 for t in self.tasks.values() if t.status == TaskStatus.COMPLETED)
            failed = sum(1 for t in self.tasks.values() if t.status == TaskStatus.FAILED)
            
            return {
                "total": total,
                "pending": pending,
                "processing": processing,
                "completed": completed,
                "failed": failed
            }
    
    def export_state(self) -> Dict:
        """
        Export current state for synchronization
        
        Returns:
            State as dictionary
        """
        with self.lock:
            return {
                "version": self.state_version,
                "timestamp": time.time(),
                "tasks": {task_id: task.dict() for task_id, task in self.tasks.items()},
                "completed_urls": list(self.completed_urls)
            }
    
    def import_state(self, state: Dict) -> bool:
        """
        Import state from another node
        
        Args:
            state: State dictionary
            
        Returns:
            True if successful, False otherwise
        """
        # Skip if state version is older than our current version
        if state["version"] <= self.state_version:
            logger.info(f"Ignoring older state version {state['version']} (current: {self.state_version})")
            return False
        
        with self.lock:
            # Update state version
            self.state_version = state["version"]
            
            # Clear and rebuild tasks
            self.tasks = {}
            for task_id, task_data in state["tasks"].items():
                self.tasks[task_id] = SummaryTask(**task_data)
            
            # Clear and rebuild completed URLs
            self.completed_urls = set(state["completed_urls"])
            
            # Rebuild task queue if leader
            if self.is_leader:
                # Clear existing queue
                with self.task_queue.mutex:
                    self.task_queue.queue.clear()
                
                # Add pending tasks to queue
                for task_id, task in self.tasks.items():
                    if task.status == TaskStatus.PENDING:
                        self.task_queue.put(task_id)
            
            self.last_sync_time = time.time()
            logger.info(f"Imported state version {state['version']} with {len(self.tasks)} tasks")
            
            return True
    
    def sync_with_leader(self, leader_host: str, leader_port: int) -> bool:
        """
        Synchronize state with current leader
        
        Args:
            leader_host: Leader host
            leader_port: Leader port
            
        Returns:
            True if successful, False otherwise
        """
        try:
            url = f"http://{leader_host}:{leader_port}/state"
            response = requests.get(url, timeout=5)
            
            if response.status_code == 200:
                state = response.json()
                return self.import_state(state)
            else:
                logger.error(f"Failed to sync with leader: {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"Error syncing with leader: {str(e)}")
            return False

    def become_leader(self):
        """Convert this instance to leader role"""
        with self.lock:
            if not self.is_leader:
                self.is_leader = True
                logger.info("State manager now operating as leader")
                
                # Rebuild task queue
                with self.task_queue.mutex:
                    self.task_queue.queue.clear()
                
                for task_id, task in self.tasks.items():
                    if task.status == TaskStatus.PENDING:
                        self.task_queue.put(task_id)

    def become_follower(self):
        """Convert this instance to follower role"""
        with self.lock:
            if self.is_leader:
                self.is_leader = False
                logger.info("State manager now operating as follower")