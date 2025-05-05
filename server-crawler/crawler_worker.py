"""
Worker node implementation for distributed crawler system.
Handles crawl task processing and communication with leader.
"""
import time
import threading
import logging
from typing import Dict, Optional
import requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from shared_models import NodeType, NodeStatus, CrawlTask, TaskStatus, HeartbeatMessage
from heartbeat import HeartbeatService
import config
from firecrawl import FirecrawlApp, ScrapeOptions
import os
import httpx

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

SUMMARIZER_URL = "http://localhost:8001/summarize"

class CrawlerWorkerNode:
    def __init__(self, worker_id: str, host: str, port: int, focus_area: str):
        self.worker_id = worker_id
        self.host = host
        self.port = port
        self.focus_area = focus_area
        self.app = FastAPI(title="Crawler Worker API")
        self.setup_routes()
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        self.heartbeat = HeartbeatService(
            node_id=self.worker_id,
            node_type=NodeType.WORKER
        )
        self.current_tasks: Dict[str, CrawlTask] = {}
        self.processing_count = 0
        self.completed_count = 0
        self.current_leader_id = config.PRIMARY_LEADER["id"]
        self.current_leader_host = config.PRIMARY_LEADER["host"]
        self.current_leader_port = config.PRIMARY_LEADER["port"]
        firecrawl_api_key = os.getenv("FIRECRAWL_API_KEY")
        if not firecrawl_api_key:
            logger.error("FIRECRAWL_API_KEY is not set in the environment variables.")
            raise ValueError("FIRECRAWL_API_KEY is required to initialize FirecrawlApp.")
        self.firecrawl = FirecrawlApp(api_key=firecrawl_api_key)

    def setup_routes(self):
        @self.app.post("/task")
        async def receive_task(task: CrawlTask):
            logger.info(f"Received crawl task {task.task_id}")
            self.current_tasks[task.task_id] = task
            self.processing_count += 1
            self.heartbeat.update_task_stats(
                len(self.current_tasks),
                self.processing_count,
                self.completed_count
            )
            threading.Thread(target=self.process_task, args=(task,)).start()
            return {"status": "accepted"}

        @self.app.post("/heartbeat")
        async def receive_heartbeat(heartbeat: HeartbeatMessage):
            self.heartbeat.receive_heartbeat(heartbeat)
            if heartbeat.node_type in (NodeType.PRIMARY_LEADER, NodeType.BACKUP_LEADER):
                if heartbeat.leader_id and self.current_leader_id != heartbeat.leader_id:
                    logger.info(f"Leader changed from {self.current_leader_id} to {heartbeat.leader_id}")
                    self.current_leader_id = heartbeat.leader_id
                    leader_info = config.get_leader_by_id(heartbeat.leader_id)
                    if leader_info:
                        self.current_leader_host = leader_info["host"]
                        self.current_leader_port = leader_info["port"]
            return {"status": "ok"}

        @self.app.post("/election/victory")
        async def election_victory(leader_id: str):
            logger.info(f"New leader elected: {leader_id}")
            self.current_leader_id = leader_id
            leader_info = config.get_leader_by_id(leader_id)
            if leader_info:
                self.current_leader_host = leader_info["host"]
                self.current_leader_port = leader_info["port"]
            return {"status": "acknowledged"}

        @self.app.get("/health")
        async def health_check():
            return {
                "status": "healthy",
                "worker_id": self.worker_id,
                "focus_area": self.focus_area,
                "tasks_processed": self.completed_count,
                "tasks_in_progress": self.processing_count,
                "current_leader": self.current_leader_id
            }

    def start(self):
        self.heartbeat.start()
        import uvicorn
        logger.info(f"Starting worker node {self.worker_id} on {self.host}:{self.port}")
        uvicorn.run(self.app, host=self.host, port=self.port)

    def process_task(self, task: CrawlTask):
        try:
            logger.info(f"Processing crawl task {task.task_id}")
            # Use Firecrawl to scrape the URL
            page = self.firecrawl.scrape_url(task.url, formats=task.formats)
            page_content = page.markdown
            map_result = self.firecrawl.map_url(task.url).links

            # Send markdown to summarizer
            summary = None
            try:
                response = httpx.post(
                    SUMMARIZER_URL,
                    json={"text": page_content, "url": task.url, "title": getattr(task, 'title', None)},
                    timeout=10
                )
                if response.status_code == 200:
                    summary_data = response.json()
                    summary = summary_data.get("summary")
                    logger.info(f"Summary: {summary}")
                else:
                    logger.warning(f"Failed to get summary: {response.status_code}")
            except Exception as e:
                logger.warning(f"Error calling summarizer service: {str(e)}")

            result = {
                "markdown": page_content,
                "summary": summary,
                "map": map_result,
                "url": task.url,
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            }
            self.send_result_to_leader(task.task_id, result)
            self.processing_count -= 1
            self.completed_count += 1
            self.heartbeat.update_task_stats(
                len(self.current_tasks),
                self.processing_count,
                self.completed_count
            )
            logger.info(f"Crawl task {task.task_id} completed successfully")
        except Exception as e:
            logger.error(f"Error processing crawl task {task.task_id}: {str(e)}")
            try:
                self.notify_task_failure(task.task_id, str(e))
            except Exception as notify_error:
                logger.error(f"Failed to notify leader of task failure: {str(notify_error)}")
            self.processing_count -= 1

    def send_result_to_leader(self, task_id: str, result: Dict):
        try:
            url = f"http://{self.current_leader_host}:{self.current_leader_port}/worker/task_completed"
            response = requests.post(url, json={"task_id": task_id, "result": result}, timeout=5)
            if response.status_code == 200:
                logger.info(f"Reported completion of task {task_id} to leader")
            else:
                logger.warning(f"Failed to report completion of task {task_id} to leader: {response.status_code}")
        except Exception as e:
            logger.error(f"Error reporting completion of task {task_id} to leader: {str(e)}")

    def notify_task_failure(self, task_id: str, error_message: str):
        try:
            url = f"http://{self.current_leader_host}:{self.current_leader_port}/worker/task_failed"
            response = requests.post(url, json={"task_id": task_id, "error": error_message}, timeout=5)
            if response.status_code == 200:
                logger.info(f"Reported failure of task {task_id} to leader")
            else:
                logger.warning(f"Failed to report failure of task {task_id} to leader: {response.status_code}")
        except Exception as e:
            logger.error(f"Error reporting failure of task {task_id} to leader: {str(e)}") 