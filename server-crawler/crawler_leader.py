"""
Leader node implementation for distributed crawler system.
Handles task distribution, worker management, and leader election.
"""
import time
import threading
import logging
import random
from typing import Dict, List, Optional
import requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from shared_models import (
    NodeType, NodeStatus, CrawlTask, TaskStatus,
    HeartbeatMessage, CrawlRequest, CrawlResponse, generate_task_id, CrawlMultiResponse
)
from heartbeat import HeartbeatService
from state_manager import StateManager
import config

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class CrawlerLeader:
    def __init__(self, node_id: str, host: str, port: int, is_primary: bool = False):
        self.node_id = node_id
        self.host = host
        self.port = port
        self.is_primary = is_primary
        self.is_active_leader = is_primary
        self.app = FastAPI(title="Crawler Leader API")
        self.setup_routes()
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        self.state = StateManager(is_leader=self.is_active_leader)
        self.heartbeat = HeartbeatService(
            node_id=self.node_id,
            node_type=NodeType.PRIMARY_LEADER if is_primary else NodeType.BACKUP_LEADER,
            status_callback=self.handle_node_status_change
        )
        self.worker_status: Dict[str, NodeStatus] = {}
        self.worker_assignments: Dict[str, List[str]] = {}
        for worker in config.WORKERS:
            self.worker_status[worker["id"]] = NodeStatus.OFFLINE
            self.worker_assignments[worker["id"]] = []
        self.current_leader_id = config.PRIMARY_LEADER["id"] if is_primary else None
        self.primary_leader_failed = False
        self.leader_selection_in_progress = False
        self.leader_selection_time = 0
        self.leader_selection_cooldown = 60
        self.backup_leader_status = {}
        self.task_monitor_thread = None
        self.state_sync_thread = None

    def setup_routes(self):
        @self.app.post("/crawl", response_model=CrawlMultiResponse)
        async def crawl_urls(request: CrawlRequest):
            if not self.is_active_leader:
                if self.current_leader_id:
                    leader_info = config.get_leader_by_id(self.current_leader_id)
                    if leader_info:
                        redirect_url = f"http://{leader_info['host']}:{leader_info['port']}/crawl"
                        logger.info(f"Redirecting request to active leader: {redirect_url}")
                        raise HTTPException(
                            status_code=307,
                            detail=f"Redirecting to active leader",
                            headers={"Location": redirect_url}
                        )
                raise HTTPException(status_code=503, detail="This node is not the active leader")
            # Create a crawl task for each URL
            task_ids = []
            for url in request.urls:
                task_id = generate_task_id()
                task = CrawlTask(
                    task_id=task_id,
                    url=url,
                    max_depth=request.max_depth,
                    timeout=request.timeout,
                    formats=request.formats
                )
                self.state.add_task(task)
                logger.info(f"Created crawl task {task_id} for URL: {url}")
                self.assign_task_to_worker(task)
                task_ids.append(task_id)
            # Wait for all tasks to finish or timeout (e.g., 60 seconds)
            results = await self.wait_for_tasks(task_ids, timeout=60)
            crawl_results = []
            for tid in task_ids:
                info = results.get(tid, {})
                result = info.get("result", {}) or {}
                crawl_results.append(CrawlResponse(
                    markdown=result.get("markdown", ""),
                    summary=result.get("summary"),
                    url=result.get("url", request.urls[task_ids.index(tid)]),
                    timestamp=result.get("timestamp", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())),
                    map=result.get("map", [])
                ))
            return CrawlMultiResponse(
                results=crawl_results,
                timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            )

        @self.app.post("/heartbeat")
        async def receive_heartbeat(heartbeat: HeartbeatMessage):
            self.heartbeat.receive_heartbeat(heartbeat)
            if heartbeat.node_id.startswith("worker"):
                self.worker_status[heartbeat.node_id] = heartbeat.status
            if heartbeat.node_id.startswith("leader-backup"):
                self.backup_leader_status[heartbeat.node_id] = {
                    "status": heartbeat.status,
                    "last_seen": time.time()
                }
            return {"status": "ok"}

        @self.app.get("/state")
        async def get_state():
            if not self.is_active_leader:
                raise HTTPException(status_code=403, detail="Only active leader can share state")
            return self.state.export_state()

        @self.app.post("/worker/task_completed")
        async def task_completed(task_result: Dict):
            task_id = task_result.get("task_id")
            result = task_result.get("result")
            if not task_id:
                raise HTTPException(status_code=400, detail="Missing task_id field")
            task = self.state.get_task(task_id)
            if not task:
                raise HTTPException(status_code=404, detail="Task not found")
            self.state.update_task(task_id, TaskStatus.COMPLETED, result)
            if task.assigned_worker:
                if task_id in self.worker_assignments.get(task.assigned_worker, []):
                    self.worker_assignments[task.assigned_worker].remove(task_id)
            logger.info(f"Crawl task {task_id} completed by {task.assigned_worker}")
            return {"status": "acknowledged"}

        @self.app.post("/worker/task_failed")
        async def task_failed(task_result: Dict):
            task_id = task_result.get("task_id")
            error = task_result.get("error")
            if not task_id:
                raise HTTPException(status_code=400, detail="Missing task_id field")
            task = self.state.get_task(task_id)
            if not task:
                raise HTTPException(status_code=404, detail="Task not found")
            self.state.update_task(task_id, TaskStatus.FAILED, {"error": error})
            if task.assigned_worker:
                if task_id in self.worker_assignments.get(task.assigned_worker, []):
                    self.worker_assignments[task.assigned_worker].remove(task_id)
            logger.info(f"Crawl task {task_id} failed by {task.assigned_worker}")
            return {"status": "acknowledged"}

        @self.app.get("/health")
        async def health_check():
            return {
                "status": "healthy",
                "node_id": self.node_id,
                "is_leader": self.is_active_leader,
                "current_leader": self.current_leader_id
            }

    def assign_task_to_worker(self, task: CrawlTask):
        available_worker = self._find_available_worker()
        if not available_worker:
            logger.warning("No available worker to assign task.")
            return
        try:
            worker_info = config.get_worker_by_id(available_worker)
            url = f"http://{worker_info['host']}:{worker_info['port']}/task"
            response = requests.post(url, json=task.dict(), timeout=5)
            if response.status_code == 200:
                logger.info(f"Assigned task {task.task_id} to worker {available_worker}")
                task.assigned_worker = available_worker
                self.worker_assignments[available_worker].append(task.task_id)
            else:
                logger.warning(f"Failed to assign task {task.task_id} to worker {available_worker}: {response.status_code}")
        except Exception as e:
            logger.error(f"Error assigning task {task.task_id} to worker {available_worker}: {str(e)}")

    def _find_available_worker(self) -> Optional[str]:
        # Simple round-robin or random selection
        online_workers = [wid for wid, status in self.worker_status.items() if status == NodeStatus.ONLINE]
        if not online_workers:
            return None
        return random.choice(online_workers)

    def handle_node_status_change(self, node_id: str, status: NodeStatus):
        logger.info(f"Node {node_id} status changed to {status}")
        if node_id.startswith("worker"):
            self.worker_status[node_id] = status

    def start(self):
        self.heartbeat.start()
        import uvicorn
        logger.info(f"Starting leader node {self.node_id} on {self.host}:{self.port}")
        uvicorn.run(self.app, host=self.host, port=self.port)

    async def wait_for_tasks(self, task_ids, timeout=60):
        """
        Wait for all tasks in task_ids to be completed or failed, or until timeout (seconds).
        Returns a dict of task_id -> result/status.
        """
        import asyncio
        start_time = time.time()
        while True:
            all_done = True
            results = {}
            for task_id in task_ids:
                task = self.state.get_task(task_id)
                if not task:
                    results[task_id] = {"status": "not_found"}
                    continue
                if task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED]:
                    results[task_id] = {
                        "status": task.status,
                        "result": getattr(task, "result", None)
                    }
                else:
                    all_done = False
            if all_done or (time.time() - start_time) > timeout:
                return results
            await asyncio.sleep(1) 