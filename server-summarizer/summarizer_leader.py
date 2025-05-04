"""
Leader node implementation for distributed summarizer system.
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
    NodeType, NodeStatus, SummaryTask, TaskStatus,
    HeartbeatMessage, SummaryRequest, SummaryResponse, generate_task_id
)
from heartbeat import HeartbeatService
from state_manager import StateManager
import config

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Add a missing import for random
import random

class SummarizerLeader:
    """Leader node for distributed summarizer system"""
    
    def __init__(self, node_id: str, host: str, port: int, is_primary: bool = False):
        """
        Initialize leader node
        """
        self.node_id = node_id
        self.host = host
        self.port = port
        self.is_primary = is_primary
        self.is_active_leader = is_primary  # Initially only primary is leader
        
        # Create FastAPI app
        self.app = FastAPI(title="Summarizer Leader API")
        self.setup_routes()
        
        # Add CORS middleware
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        # Initialize state manager
        self.state = StateManager(is_leader=self.is_active_leader)
        
        # Initialize heartbeat service
        self.heartbeat = HeartbeatService(
            node_id=self.node_id,
            node_type=NodeType.PRIMARY_LEADER if is_primary else NodeType.BACKUP_LEADER,
            status_callback=self.handle_node_status_change
        )
        
        # Worker status tracking
        self.worker_status: Dict[str, NodeStatus] = {}
        self.worker_assignments: Dict[str, List[str]] = {}
        
        # Initialize worker tracking
        for worker in config.WORKERS:
            self.worker_status[worker["id"]] = NodeStatus.OFFLINE
            self.worker_assignments[worker["id"]] = []
        
        # Leader tracking
        self.current_leader_id = config.PRIMARY_LEADER["id"] if is_primary else None
        self.primary_leader_failed = False
        self.leader_selection_in_progress = False
        self.leader_selection_time = 0
        self.leader_selection_cooldown = 60  # 60 seconds cooldown between leader selections
        
        # Health tracking for other backup leaders
        self.backup_leader_status = {}
        
        # Background tasks
        self.task_monitor_thread = None
        self.state_sync_thread = None
        
    def setup_routes(self):
        """Setup FastAPI routes"""
        
        # Public API routes - only active for current leader
        @self.app.post("/summarize", response_model=SummaryResponse)
        async def summarize_text(request: SummaryRequest):
            """Endpoint to receive summary requests from crawler"""
            # Check if we're the active leader
            if not self.is_active_leader:
                # Redirect to current leader
                if self.current_leader_id:
                    leader_info = config.get_leader_by_id(self.current_leader_id)
                    if leader_info:
                        redirect_url = f"http://{leader_info['host']}:{leader_info['port']}/summarize"
                        logger.info(f"Redirecting request to active leader: {redirect_url}")
                        raise HTTPException(
                            status_code=307,
                            detail=f"Redirecting to active leader",
                            headers={"Location": redirect_url}
                        )
                raise HTTPException(status_code=503, detail="This node is not the active leader")
            
            # Create task from request
            task_id = generate_task_id()
            task = SummaryTask(
                task_id=task_id,
                text=request.text,
                url=request.url,
                title=request.title,
                source=request.source
            )
            
            # Add to state manager
            self.state.add_task(task)
            logger.info(f"Created task {task_id} for URL: {request.url}")
            
            # Process queue in background
            threading.Thread(target=self.process_task_queue).start()
            
            return SummaryResponse(task_id=task_id, status="processing")
        
        @self.app.get("/task/{task_id}")
        async def get_task(task_id: str):
            """Get task status and result"""
            task = self.state.get_task(task_id)
            if not task:
                raise HTTPException(status_code=404, detail="Task not found")
                
            return {
                "task_id": task.task_id,
                "status": task.status,
                "result": task.result if task.status == TaskStatus.COMPLETED else None,
                "url": task.url,
                "created_at": task.created_at,
                "updated_at": task.updated_at
            }
        
        @self.app.get("/tasks")
        async def get_all_tasks():
            """Get all tasks (admin endpoint)"""
            tasks = [task.dict() for task in self.state.get_all_tasks()]
            return {"tasks": tasks}
        
        # Internal API routes
        @self.app.post("/heartbeat")
        async def receive_heartbeat(heartbeat: HeartbeatMessage):
            """Receive heartbeat from another node"""
            self.heartbeat.receive_heartbeat(heartbeat)
            
            # Update worker status
            if heartbeat.node_id.startswith("worker"):
                self.worker_status[heartbeat.node_id] = heartbeat.status
            
            # Track backup leaders' status
            if heartbeat.node_id.startswith("leader-backup"):
                self.backup_leader_status[heartbeat.node_id] = {
                    "status": heartbeat.status,
                    "last_seen": time.time()
                }
            
            return {"status": "ok"}
        
        @self.app.get("/state")
        async def get_state():
            """Get current state (for backup leader syncing)"""
            if not self.is_active_leader:
                raise HTTPException(status_code=403, detail="Only active leader can share state")
                
            return self.state.export_state()
        
        @self.app.post("/worker/task_completed")
        async def task_completed(task_result: Dict):
            """Receive completed task from worker"""
            task_id = task_result.get("task_id")
            result = task_result.get("result")
            
            if not task_id:
                raise HTTPException(status_code=400, detail="Missing task_id field")
                
            task = self.state.get_task(task_id)
            if not task:
                raise HTTPException(status_code=404, detail="Task not found")
            
            # Update task
            self.state.update_task(task_id, TaskStatus.COMPLETED, result)
            
            # Remove from worker assignments
            if task.assigned_worker:
                if task_id in self.worker_assignments.get(task.assigned_worker, []):
                    self.worker_assignments[task.assigned_worker].remove(task_id)
            
            logger.info(f"Task {task_id} completed by {task.assigned_worker}")
            
            return {"status": "ok"}
        
        @self.app.post("/leader-change")
        async def leader_change(new_leader_data: Dict):
            """Handle leader change notification"""
            new_leader_id = new_leader_data.get("leader_id")
            if not new_leader_id:
                raise HTTPException(status_code=400, detail="Missing leader_id field")
                
            logger.info(f"Received leader change notification: new leader is {new_leader_id}")
            
            # Update leader status
            old_leader = self.current_leader_id
            self.current_leader_id = new_leader_id
            
            # Check if we're the new leader
            if new_leader_id == self.node_id:
                self.become_leader()
            else:
                self.become_follower()
                
            # Update heartbeat service
            self.heartbeat.set_leader(new_leader_id)
                
            return {"status": "acknowledged", "previous_leader": old_leader}
        
        @self.app.get("/health")
        async def health_check():
            """Health check endpoint"""
            stats = self.state.get_stats()
            active_nodes = self.heartbeat.get_active_nodes()
            failed_nodes = self.heartbeat.get_failed_nodes()
            
            return {
                "status": "healthy",
                "node_id": self.node_id,
                "is_leader": self.is_active_leader,
                "current_leader": self.current_leader_id,
                "worker_status": self.worker_status,
                "task_stats": stats,
                "active_nodes": active_nodes,
                "failed_nodes": failed_nodes
            }
    
    def start(self):
        """Start the leader node"""
        # Start heartbeat service
        self.heartbeat.start()
        
        # Start task monitor if active leader
        if self.is_active_leader:
            self._start_task_monitor()
        else:
            # Start state sync if backup
            self._start_state_sync()
        
        # Import app for uvicorn
        import uvicorn
        
        # Start web server
        logger.info(f"Starting leader node {self.node_id} on {self.host}:{self.port}")
        uvicorn.run(self.app, host=self.host, port=self.port)
    
    def handle_node_status_change(self, node_id: str, status: NodeStatus):
        """Handle node status changes"""
        # Handle worker status changes
        if node_id.startswith("worker"):
            logger.info(f"Worker {node_id} status changed to {status}")
            self.worker_status[node_id] = status
            
            # If worker went offline, reassign its tasks
            if status == NodeStatus.OFFLINE and self.is_active_leader:
                self._reassign_worker_tasks(node_id)
        
        # Handle primary leader failure
        elif node_id == config.PRIMARY_LEADER["id"] and node_id != self.node_id:
            if status == NodeStatus.OFFLINE and not self.primary_leader_failed:
                logger.warning(f"Primary leader {node_id} is offline")
                self.primary_leader_failed = True
                
                # If we're a backup leader and not in selection cooldown, consider becoming leader
                current_time = time.time()
                if (not self.is_active_leader and 
                    not self.leader_selection_in_progress and 
                    current_time - self.leader_selection_time > self.leader_selection_cooldown):
                    
                    logger.info(f"Starting leader selection process due to primary leader failure")
                    self.leader_selection_in_progress = True
                    self.leader_selection_time = current_time
                    
                    # Wait random time to avoid race conditions
                    selection_delay = random.uniform(5.0, 10.0)
                    logger.info(f"Will attempt leader selection in {selection_delay:.1f} seconds")
                    selection_timer = threading.Timer(selection_delay, self._select_new_leader)
                    selection_timer.daemon = True
                    selection_timer.start()
            
            elif status == NodeStatus.ONLINE and self.primary_leader_failed:
                logger.info(f"Primary leader {node_id} is back online")
                self.primary_leader_failed = False
                self.leader_selection_in_progress = False
    
    def _select_new_leader(self):
        """Select new leader when primary leader fails - simplified logic"""
        try:
            # Don't proceed if conditions have changed
            if not self.primary_leader_failed or self.is_active_leader:
                self.leader_selection_in_progress = False
                return
            
            logger.info("Starting leader selection due to primary leader failure")
            
            # Check again if primary is still failed (could have recovered during the delay)
            if self.heartbeat.is_node_active(config.PRIMARY_LEADER["id"]):
                logger.info("Primary leader has recovered, canceling leader selection")
                self.primary_leader_failed = False
                self.leader_selection_in_progress = False
                return
                
            # Check if we're the only available backup
            active_backups = []
            for leader_id in [b["id"] for b in config.BACKUP_LEADERS]:
                if leader_id != self.node_id and self.heartbeat.is_node_active(leader_id):
                    active_backups.append(leader_id)
            
            # Make selection
            should_become_leader = False
            
            if not active_backups:
                # No other backups available, become leader
                logger.info("No other backup leaders available, becoming leader")
                should_become_leader = True
            else:
                # First backup leader takes over if it's us, otherwise the second one waits
                if self.node_id == config.BACKUP_LEADERS[0]["id"]:
                    logger.info("This node is the first backup, becoming leader")
                    should_become_leader = True
                else:
                    # We're backup 2, only become leader if backup 1 is not available
                    backup1_id = config.BACKUP_LEADERS[0]["id"]
                    if not self.heartbeat.is_node_active(backup1_id):
                        logger.info(f"Backup 1 ({backup1_id}) is not available, becoming leader")
                        should_become_leader = True
                    else:
                        logger.info(f"Backup 1 ({backup1_id}) is available, waiting for it to take over")
            
            if should_become_leader:
                self.become_leader()
                self._announce_leadership()
        except Exception as e:
            logger.error(f"Error in leader selection: {str(e)}")
        finally:
            self.leader_selection_in_progress = False
    
    def _announce_leadership(self):
        """Announce new leadership to all nodes"""
        logger.info(f"Announcing leadership as {self.node_id}")
        # Send to all leaders and workers
        all_nodes = config.get_all_nodes()
        
        for node in all_nodes:
            # Skip self
            if node["id"] == self.node_id:
                continue
            
            try:
                url = f"http://{node['host']}:{node['port']}/leader-change"
                response = requests.post(
                    url,
                    json={"leader_id": self.node_id},
                    timeout=3
                )
                if response.status_code == 200:
                    logger.info(f"Successfully announced leadership to {node['id']}")
                else:
                    logger.warning(f"Failed to announce leadership to {node['id']}: {response.status_code}")
            except Exception as e:
                logger.warning(f"Failed to announce leadership to {node['id']}: {str(e)}")
    
    def become_leader(self):
        """Take on leader role"""
        if not self.is_active_leader:
            logger.info(f"Node {self.node_id} becoming active leader")
            self.is_active_leader = True
            self.current_leader_id = self.node_id
            self.state.become_leader()
            
            # Start task monitor
            self._start_task_monitor()
            
            # Stop state sync if running
            self._stop_state_sync()
            
            # Update heartbeat service
            self.heartbeat.set_leader(self.node_id)
    
    def become_follower(self):
        """Take on follower role"""
        if self.is_active_leader:
            logger.info(f"Node {self.node_id} becoming follower")
            self.is_active_leader = False
            self.state.become_follower()
            
            # Stop task monitor if running
            self._stop_task_monitor()
            
            # Start state sync
            self._start_state_sync()
    
    def process_task_queue(self):
        """Process tasks in queue and assign to workers"""
        if not self.is_active_leader:
            return
        
        # Get next task
        task = self.state.get_next_task()
        if not task:
            return  # No tasks to process
        
        # Find available worker
        worker_id = self._find_available_worker()
        if not worker_id:
            # Put task back in queue
            logger.info("No available workers, returning task to queue")
            task.status = TaskStatus.PENDING
            self.state.add_task(task)
            return
        
        # Assign task to worker
        self.state.assign_task(task.task_id, worker_id)
        self.worker_assignments[worker_id].append(task.task_id)
        
        # Send task to worker
        self._send_task_to_worker(task, worker_id)
    
    def _find_available_worker(self) -> Optional[str]:
        """Find an available worker with fewest assignments"""
        available_workers = []
        
        for worker_id, status in self.worker_status.items():
            if status == NodeStatus.ONLINE:
                assignments = len(self.worker_assignments[worker_id])
                available_workers.append((worker_id, assignments))
        
        if not available_workers:
            return None
        
        # Sort by number of assignments (ascending)
        available_workers.sort(key=lambda x: x[1])
        
        return available_workers[0][0]
    
    def _send_task_to_worker(self, task: SummaryTask, worker_id: str):
        """Send task to worker"""
        worker = config.get_worker_by_id(worker_id)
        if not worker:
            logger.error(f"Worker {worker_id} not found in configuration")
            return
        
        try:
            url = f"http://{worker['host']}:{worker['port']}/task"
            response = requests.post(
                url,
                json=task.dict(),
                timeout=5
            )
            
            if response.status_code != 200:
                logger.error(f"Failed to send task to worker: {response.status_code}")
                self._handle_task_failure(task, worker_id)
        except Exception as e:
            logger.error(f"Error sending task to worker: {str(e)}")
            self._handle_task_failure(task, worker_id)
    
    def _handle_task_failure(self, task: SummaryTask, worker_id: str):
        """Handle task assignment failure"""
        # Update task status
        task.status = TaskStatus.PENDING
        task.assigned_worker = None
        self.state.add_task(task)  # Re-add to queue
        
        # Remove from worker assignments
        if task.task_id in self.worker_assignments[worker_id]:
            self.worker_assignments[worker_id].remove(task.task_id)
    
    def _reassign_worker_tasks(self, worker_id: str):
        """Reassign tasks from failed worker"""
        if not self.is_active_leader:
            return
        
        assignments = self.worker_assignments.get(worker_id, [])
        if not assignments:
            return
        
        logger.info(f"Reassigning {len(assignments)} tasks from failed worker {worker_id}")
        
        # Copy list to avoid modification during iteration
        for task_id in list(assignments):
            task = self.state.get_task(task_id)
            if task and task.status == TaskStatus.PROCESSING:
                # Reset task
                task.status = TaskStatus.PENDING
                task.assigned_worker = None
                self.state.add_task(task)  # Re-add to queue
                
                # Remove from assignments
                assignments.remove(task_id)
        
        # Clear assignments
        self.worker_assignments[worker_id] = []
    
    def _start_task_monitor(self):
        """Start background task monitor"""
        if self.task_monitor_thread and self.task_monitor_thread.is_alive():
            return
        
        self.task_monitor_thread = threading.Thread(target=self._task_monitor_loop)
        self.task_monitor_thread.daemon = True
        self.task_monitor_thread.start()
    
    def _stop_task_monitor(self):
        """Stop task monitor thread"""
        if self.task_monitor_thread:
            self.task_monitor_thread = None
    
    def _task_monitor_loop(self):
        """Task monitoring loop"""
        while self.is_active_leader:
            try:
                # Process queue
                self.process_task_queue()
                
                # Check for stalled tasks
                self._check_stalled_tasks()
                
                # Update heartbeat stats
                stats = self.state.get_stats()
                self.heartbeat.update_task_stats(
                    stats["total"],
                    stats["pending"] + stats["processing"],
                    stats["completed"]
                )
                
                # Small delay
                time.sleep(1)
            except Exception as e:
                logger.error(f"Error in task monitor: {str(e)}")
                time.sleep(5)  # Longer delay on error
    
    def _check_stalled_tasks(self):
        """Check for stalled tasks (processing too long)"""
        if not self.is_active_leader:
            return
        
        stall_threshold = 60  # 1 minute
        current_time = time.time()
        
        for task in self.state.get_all_tasks():
            # Skip non-processing tasks
            if task.status != TaskStatus.PROCESSING:
                continue
                
            # Check if stalled
            if current_time - task.updated_at > stall_threshold:
                logger.warning(f"Task {task.task_id} stalled, reassigning")
                
                # Reset task
                task.status = TaskStatus.PENDING
                worker_id = task.assigned_worker
                task.assigned_worker = None
                self.state.add_task(task)  # Re-add to queue
                
                # Remove from worker assignments
                if worker_id and task.task_id in self.worker_assignments.get(worker_id, []):
                    self.worker_assignments[worker_id].remove(task.task_id)
    
    def _start_state_sync(self):
        """Start background state sync"""
        if self.state_sync_thread and self.state_sync_thread.is_alive():
            return
        
        self.state_sync_thread = threading.Thread(target=self._state_sync_loop)
        self.state_sync_thread.daemon = True
        self.state_sync_thread.start()
    
    def _stop_state_sync(self):
        """Stop state sync thread"""
        if self.state_sync_thread:
            self.state_sync_thread = None
    
    def _state_sync_loop(self):
        """State synchronization loop"""
        sync_interval = 5  # 5 seconds
        
        while not self.is_active_leader and self.current_leader_id:
            try:
                # Get leader info
                leader_info = config.get_leader_by_id(self.current_leader_id)
                if not leader_info:
                    time.sleep(sync_interval)
                    continue
                
                # Sync state
                self.state.sync_with_leader(leader_info["host"], leader_info["port"])
                
                # Update heartbeat stats
                stats = self.state.get_stats()
                self.heartbeat.update_task_stats(
                    stats["total"],
                    stats["pending"] + stats["processing"],
                    stats["completed"]
                )
                
                time.sleep(sync_interval)
            except Exception as e:
                logger.error(f"Error in state sync: {str(e)}")
                time.sleep(sync_interval * 2)  # Longer delay on error