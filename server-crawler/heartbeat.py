"""
Heartbeat monitoring service for distributed crawler system.
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

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class HeartbeatService:
    def __init__(self, node_id: str, node_type: NodeType, status_callback: Optional[Callable] = None):
        self.node_id = node_id
        self.node_type = node_type
        self.status_callback = status_callback
        self.active_nodes: Dict[str, Dict] = {}
        self.failed_nodes: Set[str] = set()
        self.running = False
        self.thread = None
        self.lock = threading.Lock()
        self.leader_id = config.PRIMARY_LEADER["id"]
        self.tasks_count = 0
        self.pending_tasks = 0
        self.completed_tasks = 0
        self.missed_heartbeats: Dict[str, int] = {}
        self.max_missed_heartbeats = 3

    def start(self):
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._heartbeat_loop)
        self.thread.daemon = True
        self.thread.start()
        logger.info(f"Heartbeat service started for {self.node_id} ({self.node_type})")

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=2)
            self.thread = None

    def update_task_stats(self, tasks_count: int, pending_tasks: int, completed_tasks: int):
        with self.lock:
            self.tasks_count = tasks_count
            self.pending_tasks = pending_tasks
            self.completed_tasks = completed_tasks

    def set_leader(self, leader_id: str):
        with self.lock:
            if self.leader_id != leader_id:
                logger.info(f"Heartbeat service updated leader: {leader_id}")
                self.leader_id = leader_id

    def _heartbeat_loop(self):
        while self.running:
            try:
                self._send_heartbeats()
                self._check_for_failures()
                jitter = 0.1 * (0.5 - random.random())
                time.sleep(config.HEARTBEAT_INTERVAL + jitter)
            except Exception as e:
                logger.error(f"Error in heartbeat loop: {str(e)}")
                time.sleep(config.HEARTBEAT_INTERVAL)

    def _send_heartbeats(self):
        message = HeartbeatMessage(
            node_id=self.node_id,
            node_type=self.node_type,
            status=NodeStatus.ONLINE,
            leader_id=self.leader_id,
            tasks_count=self.tasks_count,
            pending_tasks=self.pending_tasks,
            completed_tasks=self.completed_tasks
        )
        nodes_to_contact = []
        if self.node_type == NodeType.WORKER:
            leader_info = config.get_leader_by_id(self.leader_id)
            if leader_info:
                nodes_to_contact.append(leader_info)
        else:
            nodes_to_contact = config.get_all_nodes()
        sent_count = 0
        for node in nodes_to_contact:
            if node["id"] == self.node_id:
                continue
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
        current_time = time.time()
        with self.lock:
            for node_id in list(self.active_nodes.keys()):
                last_heartbeat = self.active_nodes[node_id]["timestamp"]
                if current_time - last_heartbeat > config.HEARTBEAT_TIMEOUT:
                    self.missed_heartbeats[node_id] = self.missed_heartbeats.get(node_id, 0) + 1
                    if self.missed_heartbeats[node_id] >= self.max_missed_heartbeats:
                        logger.warning(f"Node {node_id} considered failed - no heartbeat for {config.HEARTBEAT_TIMEOUT * self.max_missed_heartbeats}s")
                        self.active_nodes.pop(node_id)
                        self.failed_nodes.add(node_id)
                        self.missed_heartbeats.pop(node_id)
                        if self.status_callback:
                            self.status_callback(node_id, NodeStatus.OFFLINE)
                    else:
                        logger.debug(f"Node {node_id} missed heartbeat {self.missed_heartbeats[node_id]}/{self.max_missed_heartbeats}")
                else:
                    if node_id in self.missed_heartbeats and self.missed_heartbeats[node_id] > 0:
                        self.missed_heartbeats[node_id] = 0

    def receive_heartbeat(self, heartbeat: HeartbeatMessage):
        with self.lock:
            self.active_nodes[heartbeat.node_id] = {
                "heartbeat": heartbeat,
                "timestamp": time.time(),
                "type": heartbeat.node_type,
                "status": heartbeat.status
            }
            if heartbeat.node_id in self.missed_heartbeats:
                self.missed_heartbeats[heartbeat.node_id] = 0
            if heartbeat.node_id in self.failed_nodes:
                logger.info(f"Node {heartbeat.node_id} recovered")
                self.failed_nodes.remove(heartbeat.node_id)
                if self.status_callback:
                    self.status_callback(heartbeat.node_id, heartbeat.status)
            if heartbeat.node_type in (NodeType.PRIMARY_LEADER, NodeType.BACKUP_LEADER):
                if heartbeat.leader_id and heartbeat.leader_id != self.leader_id:
                    logger.info(f"Leader changed from {self.leader_id} to {heartbeat.leader_id}")
                    self.leader_id = heartbeat.leader_id

    def get_active_nodes(self) -> List[str]:
        with self.lock:
            return list(self.active_nodes.keys())

    def get_failed_nodes(self) -> List[str]:
        with self.lock:
            return list(self.failed_nodes)

    def is_node_active(self, node_id: str) -> bool:
        with self.lock:
            return node_id in self.active_nodes 