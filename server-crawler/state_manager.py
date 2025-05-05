"""
State manager for distributed crawler system.
Handles task management and state export/import for leader/backup syncing.
"""
import threading
import time
from typing import Dict, List, Optional
from shared_models import CrawlTask, TaskStatus, generate_task_id

class StateManager:
    def __init__(self, is_leader: bool = False):
        self.is_leader = is_leader
        self.tasks: Dict[str, CrawlTask] = {}
        self.lock = threading.Lock()

    def add_task(self, task: CrawlTask):
        with self.lock:
            self.tasks[task.task_id] = task

    def get_task(self, task_id: str) -> Optional[CrawlTask]:
        with self.lock:
            return self.tasks.get(task_id)

    def get_all_tasks(self) -> List[CrawlTask]:
        with self.lock:
            return list(self.tasks.values())

    def update_task(self, task_id: str, status: TaskStatus, result: Optional[Dict] = None):
        with self.lock:
            task = self.tasks.get(task_id)
            if task:
                task.status = status
                task.updated_at = time.time()
                if result is not None:
                    task.result = result

    def export_state(self) -> Dict:
        with self.lock:
            return {
                "tasks": [task.dict() for task in self.tasks.values()]
            }

    def import_state(self, state: Dict):
        with self.lock:
            self.tasks = {task["task_id"]: CrawlTask(**task) for task in state.get("tasks", [])} 