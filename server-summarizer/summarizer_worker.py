"""
Worker node implementation for distributed summarizer system.
Handles task processing and communication with leader.
"""
import time
import threading
import logging
from typing import Dict, Optional
import requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from shared_models import NodeType, NodeStatus, SummaryTask, TaskStatus, HeartbeatMessage
from heartbeat import HeartbeatService
from summarizer import SummarizerWorker
import config

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SummarizerWorkerNode:
    """Worker node for distributed summarizer system"""
    
    def __init__(self, worker_id: str, host: str, port: int, focus_area: str):
        """
        Initialize worker node
        
        Args:
            worker_id: Identifier for this worker
            host: Host address
            port: Port to listen on
            focus_area: Focus area for summarization
        """
        self.worker_id = worker_id
        self.host = host
        self.port = port
        self.focus_area = focus_area
        
        # Extract worker number from ID
        try:
            self.agent_id = int(worker_id.split("-")[1])
        except:
            self.agent_id = 1  # Default
        
        # Create FastAPI app
        self.app = FastAPI(title="Summarizer Worker API")
        self.setup_routes()
        
        # Add CORS middleware
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        # Initialize heartbeat service
        self.heartbeat = HeartbeatService(
            node_id=self.worker_id,
            node_type=NodeType.WORKER
        )
        
        # Initialize summarizer worker
        self.summarizer = SummarizerWorker(agent_id=self.agent_id)
        
        # Track tasks
        self.current_tasks: Dict[str, SummaryTask] = {}
        self.processing_count = 0
        self.completed_count = 0
        
        # Track current leader
        self.current_leader_id = config.PRIMARY_LEADER["id"]
        self.current_leader_host = config.PRIMARY_LEADER["host"]
        self.current_leader_port = config.PRIMARY_LEADER["port"]
    
    def setup_routes(self):
        """Setup FastAPI routes"""
        
        @self.app.post("/task")
        async def receive_task(task: SummaryTask):
            """Receive task from leader"""
            logger.info(f"Received task {task.task_id}")
            
            # Store task
            self.current_tasks[task.task_id] = task
            self.processing_count += 1
            
            # Update heartbeat stats
            self.heartbeat.update_task_stats(
                len(self.current_tasks),
                self.processing_count,
                self.completed_count
            )
            
            # Process in background
            threading.Thread(target=self.process_task, args=(task,)).start()
            
            return {"status": "accepted"}
        
        @self.app.post("/heartbeat")
        async def receive_heartbeat(heartbeat: HeartbeatMessage):
            """Receive heartbeat from another node"""
            self.heartbeat.receive_heartbeat(heartbeat)
            
            # Update leader info if from leader
            if heartbeat.node_type in (NodeType.PRIMARY_LEADER, NodeType.BACKUP_LEADER):
                if heartbeat.leader_id and self.current_leader_id != heartbeat.leader_id:
                    logger.info(f"Leader changed from {self.current_leader_id} to {heartbeat.leader_id}")
                    self.current_leader_id = heartbeat.leader_id
                    
                    # Update leader address
                    leader_info = config.get_leader_by_id(heartbeat.leader_id)
                    if leader_info:
                        self.current_leader_host = leader_info["host"]
                        self.current_leader_port = leader_info["port"]
            
            return {"status": "ok"}
        
        @self.app.post("/election/victory")
        async def election_victory(leader_id: str):
            """Handle leader victory announcement"""
            logger.info(f"New leader elected: {leader_id}")
            self.current_leader_id = leader_id
            
            # Update leader address
            leader_info = config.get_leader_by_id(leader_id)
            if leader_info:
                self.current_leader_host = leader_info["host"]
                self.current_leader_port = leader_info["port"]
            
            return {"status": "acknowledged"}
        
        @self.app.get("/health")
        async def health_check():
            """Health check endpoint"""
            return {
                "status": "healthy",
                "worker_id": self.worker_id,
                "focus_area": self.focus_area,
                "tasks_processed": self.completed_count,
                "tasks_in_progress": self.processing_count,
                "current_leader": self.current_leader_id
            }
    
    def start(self):
        """Start the worker node"""
        # Start heartbeat service
        self.heartbeat.start()
        
        # Import app for uvicorn
        import uvicorn
        
        # Start web server
        logger.info(f"Starting worker node {self.worker_id} on {self.host}:{self.port}")
        uvicorn.run(self.app, host=self.host, port=self.port)
    
    def process_task(self, task: SummaryTask):
        """Process a summarization task"""
        try:
            logger.info(f"Processing task {task.task_id}")
            
            # Prepare metadata
            metadata = {
                "title": task.title or "Untitled",
                "url": task.url,
                "source": task.source
            }
            
            # Process article with our summarizer
            result = self.summarizer.process_article(task.text, metadata)
            
            # Send result to leader
            self.send_result_to_leader(task.task_id, result)
            
            # Update counts
            self.processing_count -= 1
            self.completed_count += 1
            
            # Update heartbeat stats
            self.heartbeat.update_task_stats(
                len(self.current_tasks),
                self.processing_count,
                self.completed_count
            )
            
            logger.info(f"Task {task.task_id} completed successfully")
        except Exception as e:
            logger.error(f"Error processing task {task.task_id}: {str(e)}")
            
            # Try to notify leader
            try:
                self.notify_task_failure(task.task_id, str(e))
            except Exception as notify_error:
                logger.error(f"Failed to notify leader of task failure: {str(notify_error)}")
            
            # Update counts
            self.processing_count -= 1
            
            # Update heartbeat stats
            self.heartbeat.update_task_stats(
                len(self.current_tasks),
                self.processing_count,
                self.completed_count
            )
    
    def send_result_to_leader(self, task_id: str, result: Dict):
        """Send task result to current leader"""
        try:
            url = f"http://{self.current_leader_host}:{self.current_leader_port}/worker/task_completed"
            response = requests.post(
                url,
                json={"task_id": task_id, "result": result},
                timeout=5
            )
            
            if response.status_code != 200:
                logger.error(f"Failed to send result to leader: {response.status_code}")
                return False
            
            return True
        except Exception as e:
            logger.error(f"Error sending result to leader: {str(e)}")
            return False
    
    def notify_task_failure(self, task_id: str, error_message: str):
        """Notify leader of task failure"""
        try:
            url = f"http://{self.current_leader_host}:{self.current_leader_port}/worker/task_completed"
            response = requests.post(
                url,
                json={"task_id": task_id, "result": {"error": error_message, "status": "failed"}},
                timeout=5
            )
            
            if response.status_code != 200:
                logger.error(f"Failed to notify leader of task failure: {response.status_code}")
                return False
            
            return True
        except Exception as e:
            logger.error(f"Error notifying leader of task failure: {str(e)}")
            return False