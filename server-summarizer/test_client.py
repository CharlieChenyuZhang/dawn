#!/usr/bin/env python3
"""
Test client for the distributed summarizer system.
Simulates a crawler sending requests to the summarizer API and tests fault tolerance.
"""
import argparse
import json
import logging
import random
import requests
import sys
import time
from typing import Dict, List, Optional, Tuple

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Sample test articles (to simulate crawler output)
SAMPLE_ARTICLES = [
    {
        "title": "New AI Model Breaks Performance Records",
        "url": "https://example.com/ai-breakthrough",
        "source": "AI News",
        "text": """
        Researchers have developed a groundbreaking AI model that has shattered previous performance records
        across multiple benchmarks. The new model, named "SuperAI", achieves unprecedented accuracy in
        natural language processing, computer vision, and multi-modal tasks.
        
        "This represents a quantum leap in AI capabilities," said Dr. Jane Smith, lead researcher on the project.
        "SuperAI demonstrates emergent abilities we didn't explicitly design for."
        
        The model was trained on a diverse dataset using a novel architecture that combines transformer layers
        with memory-efficient attention mechanisms. Independent testing confirmed a 25% improvement over the
        previous state-of-the-art on the GLUE benchmark.
        """
    },
    {
        "title": "Tech Company Launches Revolutionary Quantum Computer",
        "url": "https://example.com/quantum-launch",
        "source": "Tech Today",
        "text": """
        QuantumTech Inc. has announced the commercial launch of its first quantum computer with 1,000 qubits,
        a milestone many experts believed was years away. The system, called Q-1000, demonstrates quantum
        supremacy by solving previously intractable problems in seconds.
        
        "This is a watershed moment for computing," said QuantumTech CEO Robert Johnson. "We've overcome
        the decoherence issues that have held quantum computing back for decades."
        """
    },
    {
        "title": "AI Ethics Board Proposes Global Regulations",
        "url": "https://example.com/ai-ethics-regulations",
        "source": "Policy Review",
        "text": """
        The International AI Ethics Board (IAEB) has proposed a comprehensive framework of regulations
        for artificial intelligence development and deployment. The proposal, which follows two years of
        multi-stakeholder consultations, aims to ensure AI technologies are developed safely and ethically.
        
        Key provisions in the framework include mandatory bias testing, algorithmic transparency requirements,
        and limitations on autonomous decision-making in high-risk domains like healthcare and criminal justice.
        """
    }
]

class TestClient:
    """Client to test the distributed summarizer system"""
    
    def __init__(self, primary_host: str = "localhost", primary_port: int = 8100):
        """Initialize test client"""
        self.primary_host = primary_host
        self.primary_port = primary_port
        self.current_leader_url = None
        self.known_urls = [
            f"http://{primary_host}:{primary_port}",
            f"http://{primary_host}:8101",
            f"http://{primary_host}:8102"
        ]
        # Discover current leader on init
        self.discover_leader()
        
    def discover_leader(self) -> bool:
        """Find the current active leader with improved reliability"""
        for url in self.known_urls:
            try:
                response = requests.get(f"{url}/health", timeout=3)
                if response.status_code == 200:
                    data = response.json()
                    if data.get("is_leader", False):
                        self.current_leader_url = url
                        logger.info(f"Found active leader at {url}")
                        return True
                    elif data.get("current_leader") and data.get("current_leader") != data.get("node_id"):
                        # This node knows who the leader is
                        leader_id = data.get("current_leader")
                        leader_info = None
                        
                        # Get leader info from config
                        if leader_id == "leader-primary":
                            leader_info = {"host": "localhost", "port": 8100}
                        elif leader_id == "leader-backup-1":
                            leader_info = {"host": "localhost", "port": 8101}
                        elif leader_id == "leader-backup-2":
                            leader_info = {"host": "localhost", "port": 8102}
                        
                        if leader_info:
                            leader_url = f"http://{leader_info['host']}:{leader_info['port']}"
                            # Try to contact this leader
                            try:
                                leader_response = requests.get(f"{leader_url}/health", timeout=2)
                                if leader_response.status_code == 200 and leader_response.json().get("is_leader", False):
                                    self.current_leader_url = leader_url
                                    logger.info(f"Found active leader at {leader_url} (via redirection)")
                                    return True
                            except Exception:
                                pass
            except Exception as e:
                continue
        
        logger.warning("No active leader found!")
        return False    
    
    def ensure_leader_connection(self) -> bool:
        """Ensure we have a connection to the current leader"""
        if self.current_leader_url:
            try:
                response = requests.get(f"{self.current_leader_url}/health", timeout=3)
                if response.status_code == 200 and response.json().get("is_leader", False):
                    return True
            except Exception:
                pass
        
        # If we get here, current leader is unavailable or unknown
        return self.discover_leader()
        
    def health_check(self, url: str = None) -> Dict:
        """Check health of a node"""
        try:
            check_url = url or self.current_leader_url
            if not check_url:
                self.discover_leader()
                check_url = self.current_leader_url
                if not check_url:
                    return {"status": "unknown", "error": "No leader available"}
            
            response = requests.get(f"{check_url}/health", timeout=5)
            if response.status_code == 200:
                return response.json()
            else:
                logger.warning(f"Health check failed with status {response.status_code}")
                return {"status": "unknown", "error": f"Status code: {response.status_code}"}
        except Exception as e:
            logger.error(f"Error during health check: {str(e)}")
            return {"status": "error", "error": str(e)}
    
    def check_all_nodes(self) -> Dict:
        """Check health of all nodes in the system"""
        results = {}
        
        # Check primary leader
        primary_url = f"http://localhost:8100"
        results["primary"] = self.health_check(primary_url)
        
        # Check backup leaders
        for i, port in enumerate([8101, 8102], 1):
            backup_url = f"http://localhost:{port}"
            results[f"backup-{i}"] = self.health_check(backup_url)
        
        # Check workers
        for i, port in enumerate([8201, 8202, 8203], 1):
            worker_url = f"http://localhost:{port}"
            results[f"worker-{i}"] = self.health_check(worker_url)
            
        return results
    
    def get_leader_info(self) -> Tuple[str, Dict]:
        """Find the current leader and get its information"""
        for node_name, node_info in self.check_all_nodes().items():
            if node_info.get("is_leader", False):
                return node_name, node_info
        return None, {}
    
    def submit_article(self, article: Dict) -> Dict:
        """Submit an article for summarization"""
        # Make sure we have the current leader
        if not self.ensure_leader_connection():
            return {"status": "error", "error": "No leader available"}
            
        try:
            url = f"{self.current_leader_url}/summarize"
            logger.info(f"Submitting article to {url}")
            response = requests.post(
                url,
                json={
                    "text": article["text"],
                    "url": article["url"],
                    "title": article["title"],
                    "source": article["source"]
                },
                timeout=10
            )
            
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 307:  # Redirect to new leader
                # Extract new leader URL from Location header
                new_leader_url = response.headers.get("Location")
                if new_leader_url:
                    logger.info(f"Redirected to new leader: {new_leader_url}")
                    self.current_leader_url = new_leader_url.rsplit('/summarize', 1)[0]
                    # Retry with new leader
                    return self.submit_article(article)
                
            logger.warning(f"Submission failed with status {response.status_code}")
            return {"status": "error", "error": f"Status code: {response.status_code}"}
        except Exception as e:
            logger.error(f"Error submitting article: {str(e)}")
            
            # Leader might have changed, try to rediscover
            if self.discover_leader():
                logger.info("Discovered new leader, retrying submission")
                return self.submit_article(article)
                
            return {"status": "error", "error": str(e)}
    
    def check_task_status(self, task_id: str) -> Dict:
        """Check the status of a task"""
        # Make sure we have the current leader
        if not self.ensure_leader_connection():
            return {"status": "error", "error": "No leader available"}
            
        try:
            url = f"{self.current_leader_url}/task/{task_id}"
            response = requests.get(url, timeout=5)
            
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 404:
                return {"status": "not_found", "error": "Task not found"}
            else:
                logger.warning(f"Task status check failed with status {response.status_code}")
                return {"status": "error", "error": f"Status code: {response.status_code}"}
        except Exception as e:
            logger.error(f"Error checking task status: {str(e)}")
            return {"status": "error", "error": str(e)}
    
    def run_test(self, num_articles: int = 3, delay: int = 2) -> None:
        """Run a test with multiple articles"""
        # Make sure we have the current leader
        if not self.ensure_leader_connection():
            logger.error("No active leader found. Test cannot proceed.")
            return
            
        # Select articles to use
        articles = random.sample(SAMPLE_ARTICLES, min(num_articles, len(SAMPLE_ARTICLES)))
        if num_articles > len(SAMPLE_ARTICLES):
            # Repeat articles if more requested than available
            extra = [random.choice(SAMPLE_ARTICLES) for _ in range(num_articles - len(SAMPLE_ARTICLES))]
            articles.extend(extra)
        
        task_ids = []
        
        # Submit articles
        for i, article in enumerate(articles):
            logger.info(f"Submitting article {i+1}/{num_articles}: {article['title']}")
            response = self.submit_article(article)
            
            if response.get("task_id"):
                task_ids.append(response["task_id"])
                logger.info(f"Task ID: {response['task_id']}, Status: {response.get('status', 'unknown')}")
            else:
                logger.error(f"Failed to submit article: {response.get('error', 'Unknown error')}")
            
            if i < num_articles - 1:  # Don't delay after the last article
                time.sleep(delay)
        
        # Check final status of all tasks
        logger.info("\nFinal task statuses:")
        for i, task_id in enumerate(task_ids):
            status = self.check_task_status(task_id)
            logger.info(f"Task {i+1}: {task_id} - Status: {status.get('status', 'unknown')}")
            
            if status.get('status') == 'completed':
                result = status.get('result', {})
                summary = result.get('summary', 'No summary available')
                logger.info(f"Summary: {summary[:100]}..." if len(summary) > 100 else summary)
    
    def test_failover(self) -> None:
        """Test leader failover by simulating a leader failure"""
        # First check the current system state
        leader_name, leader_info = self.get_leader_info()
        
        if not leader_name:
            logger.error("Could not determine current leader")
            return
            
        logger.info(f"Current leader is {leader_name} at {self.current_leader_url}")
        logger.info("Testing failover - this simulates a leader failure")
        
        # In a real test environment, you'd stop the leader process
        logger.info(f"Please manually stop the {leader_name} process now")
        input("Press Enter after stopping the leader to continue...")
        
        # Wait for failover
        logger.info("Waiting for failover to occur...")
        time.sleep(15)  # Allow time for failover
        
        # Discover new leader
        if self.discover_leader():
            new_leader_name, new_leader_info = self.get_leader_info()
            
            if new_leader_name and new_leader_name != leader_name:
                logger.info(f"Failover successful! New leader is {new_leader_name} at {self.current_leader_url}")
                
                # Test sending a request to the new leader
                logger.info("Testing request to new leader...")
                article = random.choice(SAMPLE_ARTICLES)
                response = self.submit_article(article)
                logger.info(f"Response from new leader: {response}")
            else:
                logger.error("Failover may have occurred but couldn't determine new leader")
        else:
            logger.error("Failover did not occur or no leader is available")


def main():
    """Main entry point with argument parsing"""
    parser = argparse.ArgumentParser(description="Test client for distributed summarizer system")
    
    # Add arguments
    parser.add_argument("--host", default="localhost", help="Primary leader host")
    parser.add_argument("--port", type=int, default=8100, help="Primary leader port")
    
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # Health check command
    health_parser = subparsers.add_parser("health", help="Check system health")
    
    # Leader command
    leader_parser = subparsers.add_parser("leader", help="Get current leader")
    
    # Submit article command
    submit_parser = subparsers.add_parser("submit", help="Submit an article")
    submit_parser.add_argument("--article", type=int, default=0, 
                               help="Article index (0-2) or -1 for random")
    
    # Check task command
    task_parser = subparsers.add_parser("task", help="Check task status")
    task_parser.add_argument("task_id", help="Task ID to check")
    
    # Run test command
    test_parser = subparsers.add_parser("test", help="Run a full test")
    test_parser.add_argument("--articles", type=int, default=3, help="Number of articles to submit")
    test_parser.add_argument("--delay", type=int, default=2, help="Delay between submissions (seconds)")
    
    # Test failover command
    failover_parser = subparsers.add_parser("failover", help="Test leader failover")
    
    args = parser.parse_args()
    
    # Create client
    client = TestClient(args.host, args.port)
    
    # Execute command
    if args.command == "health":
        result = client.check_all_nodes()
        print(json.dumps(result, indent=2))
    
    elif args.command == "leader":
        leader_name, leader_info = client.get_leader_info()
        print(f"Current leader: {leader_name}")
        print(json.dumps(leader_info, indent=2))
        
    elif args.command == "submit":
        article_idx = args.article
        if article_idx == -1:
            article = random.choice(SAMPLE_ARTICLES)
        else:
            if 0 <= article_idx < len(SAMPLE_ARTICLES):
                article = SAMPLE_ARTICLES[article_idx]
            else:
                logger.error(f"Invalid article index: {article_idx}")
                return 1
                
        logger.info(f"Submitting article: {article['title']}")
        result = client.submit_article(article)
        print(json.dumps(result, indent=2))
        
    elif args.command == "task":
        result = client.check_task_status(args.task_id)
        print(json.dumps(result, indent=2))
        
    elif args.command == "test":
        client.run_test(args.articles, args.delay)
        
    elif args.command == "failover":
        client.test_failover()
        
    else:
        parser.print_help()
    
    return 0

if __name__ == "__main__":
    sys.exit(main())