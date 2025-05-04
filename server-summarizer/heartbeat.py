"""
Heartbeat monitoring service for distributed summarizer system.
Manages sending and receiving heartbeats between nodes.
"""
import time
import threading
import logging
import requests
from typing import Dict, Set, Callable, Optional, List
import random

from shared_models import NodeType, NodeStatus, HeartbeatMessage
import config

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class HeartbeatService:
    """Service for monitoring node health through heartbeats"""
    
    def __init__(self, node_id: str, node_type: NodeType, status_callback: Optional[Callable] = None):
        """
        Initialize heartbeat service
        """
        self.node_id = node_id
        self.node_type = node_type
        self.status_callback = status_callback
        self.active_nodes: Dict[str, Dict] = {}  # Store more info about each node
        self.failed_nodes: Set[str] = set()
        self.running = False
        self.thread = None
        self.lock = threading.Lock()
        self.leader_id = config.PRIMARY_LEADER["id"]  # Default to primary leader
        
        # Task statistics
        self.tasks_count = 0
        self.pending_tasks = 0
        self.completed_tasks = 0
        
        # Add a counter for missed heartbeats to improve reliability
        self.missed_heartbeats: Dict[str, int] = {}
        self.max_missed_heartbeats = 3  # Allow up to 3 missed heartbeats before marking as failed
    
    def start(self):
        """Start the heartbeat service"""
        if self.running:
            return
            
        self.running = True
        self.thread = threading.Thread(target=self._heartbeat_loop)
        self.thread.daemon = True
        self.thread.start()
        logger.info(f"Heartbeat service started for {self.node_id} ({self.node_type})")
        
    def stop(self):
        """Stop the heartbeat service"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=2)
            self.thread = None
            
    def update_task_stats(self, tasks_count: int, pending_tasks: int, completed_tasks: int):
        """Update task statistics for heartbeat messages"""
        with self.lock:
            self.tasks_count = tasks_count
            self.pending_tasks = pending_tasks
            self.completed_tasks = completed_tasks
            
    def set_leader(self, leader_id: str):
        """Set the current leader ID"""
        with self.lock:
            if self.leader_id != leader_id:
                logger.info(f"Heartbeat service updated leader: {leader_id}")
                self.leader_id = leader_id
            
    def _heartbeat_loop(self):
        """Main heartbeat loop"""
        while self.running:
            try:
                self._send_heartbeats()
                self._check_for_failures()
                
                # Add a small random delay to avoid synchronized heartbeats
                jitter = 0.1 * (0.5 - random.random())  # ±0.05 seconds
                time.sleep(config.HEARTBEAT_INTERVAL + jitter)
            except Exception as e:
                logger.error(f"Error in heartbeat loop: {str(e)}")
                time.sleep(config.HEARTBEAT_INTERVAL)
            
    def _send_heartbeats(self):
        """Send heartbeat to all other nodes"""
        message = HeartbeatMessage(
            node_id=self.node_id,
            node_type=self.node_type,
            status=NodeStatus.ONLINE,
            leader_id=self.leader_id,
            tasks_count=self.tasks_count,
            pending_tasks=self.pending_tasks,
            completed_tasks=self.completed_tasks
        )
        
        # Get all nodes to send heartbeats to
        nodes_to_contact = []
        
        # If we're a worker, only send to the current leader
        if self.node_type == NodeType.WORKER:
            leader_info = config.get_leader_by_id(self.leader_id)
            if leader_info:
                nodes_to_contact.append(leader_info)
        else:
            # If we're a leader, send to all leaders and workers
            nodes_to_contact = config.get_all_nodes()
        
        # Send heartbeats with detailed logging
        sent_count = 0
        for node in nodes_to_contact:
            if node["id"] == self.node_id:
                continue  # Skip self
                
            try:
                url = f"http://{node['host']}:{node['port']}/heartbeat"
                response = requests.post(
                    url, 
                    json=message.dict(),
                    timeout=3
                )
                if response.status_code == 200:
                    sent_count += 1
                else:
                    logger.debug(f"Failed to send heartbeat to {node['id']}: {response.status_code}")
            except Exception as e:
                if "Connection refused" in str(e):
                    logger.debug(f"Node {node['id']} not available (connection refused)")
                else:
                    logger.debug(f"Failed to send heartbeat to {node['id']}: {str(e)}")
        
        if sent_count > 0:
            logger.debug(f"Sent heartbeats to {sent_count}/{len(nodes_to_contact)-1} nodes")
                
    def _check_for_failures(self):
        """Check for nodes that haven't sent heartbeats recently with improved reliability"""
        current_time = time.time()
        
        with self.lock:
            # Check each active node
            for node_id in list(self.active_nodes.keys()):
                last_heartbeat = self.active_nodes[node_id]["timestamp"]
                
                # If node hasn't sent heartbeat in timeout period
                if current_time - last_heartbeat > config.HEARTBEAT_TIMEOUT:
                    # Increment missed heartbeats counter
                    self.missed_heartbeats[node_id] = self.missed_heartbeats.get(node_id, 0) + 1
                    
                    # Only mark as failed if missed multiple consecutive heartbeats
                    if self.missed_heartbeats[node_id] >= self.max_missed_heartbeats:
                        logger.warning(f"Node {node_id} considered failed - no heartbeat for {config.HEARTBEAT_TIMEOUT * self.max_missed_heartbeats}s")
                        self.active_nodes.pop(node_id)
                        self.failed_nodes.add(node_id)
                        self.missed_heartbeats.pop(node_id)
                        
                        # Notify callback if provided
                        if self.status_callback:
                            self.status_callback(node_id, NodeStatus.OFFLINE)
                    else:
                        logger.debug(f"Node {node_id} missed heartbeat {self.missed_heartbeats[node_id]}/{self.max_missed_heartbeats}")
                else:
                    # Reset missed heartbeats counter if heartbeat received
                    if node_id in self.missed_heartbeats and self.missed_heartbeats[node_id] > 0:
                        self.missed_heartbeats[node_id] = 0
                        
    def receive_heartbeat(self, heartbeat: HeartbeatMessage):
        """Process received heartbeat from another node"""
        with self.lock:
            # Update active nodes with more information
            self.active_nodes[heartbeat.node_id] = {
                "heartbeat": heartbeat,
                "timestamp": time.time(),
                "type": heartbeat.node_type,
                "status": heartbeat.status
            }
            
            # Reset missed heartbeats counter
            if heartbeat.node_id in self.missed_heartbeats:
                self.missed_heartbeats[heartbeat.node_id] = 0
            
            # If node was previously failed, remove from failed list
            if heartbeat.node_id in self.failed_nodes:
                logger.info(f"Node {heartbeat.node_id} recovered")
                self.failed_nodes.remove(heartbeat.node_id)
                
                # Notify callback if provided
                if self.status_callback:
                    self.status_callback(heartbeat.node_id, heartbeat.status)
            
            # Update leader ID if received from a leader node
            if heartbeat.node_type in (NodeType.PRIMARY_LEADER, NodeType.BACKUP_LEADER):
                if heartbeat.leader_id and heartbeat.leader_id != self.leader_id:
                    logger.info(f"Leader changed from {self.leader_id} to {heartbeat.leader_id}")
                    self.leader_id = heartbeat.leader_id
                
    def get_active_nodes(self) -> List[str]:
        """Get IDs of all active nodes"""
        with self.lock:
            return list(self.active_nodes.keys())
            
    def get_failed_nodes(self) -> List[str]:
        """Get IDs of all failed nodes"""
        with self.lock:
            return list(self.failed_nodes)
            
    def is_node_active(self, node_id: str) -> bool:
        """Check if node is active"""
        with self.lock:
            return node_id in self.active_nodes and node_id not in self.failed_nodes