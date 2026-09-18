"""
Load testing suite for DRISHTI backend using Locust.

Usage:
    # Interactive web UI
    locust -f tests/load_test.py --host=http://localhost:8000
    
    # Headless mode
    locust -f tests/load_test.py --host=http://localhost:8000 \
        -u 100 -r 10 -t 300 --headless
    
    # With custom spawn rate
    locust -f tests/load_test.py --host=http://localhost:8000 \
        -u 200 -r 20 -t 600
"""

import json
import time
from locust import HttpUser, TaskSet, task, between, events
from locust.contrib.fasthttp import FastHttpUser
import logging

logger = logging.getLogger(__name__)


class DrishtiTasks(TaskSet):
    """Task set for DRISHTI API endpoints."""

    def on_start(self):
        """Initialize user session."""
        self.session_id = None
        self.cascade_id = None
        self.alert_id = None
        self.token = None

    @task(3)
    def get_health(self):
        """Check application health."""
        with self.client.get(
            "/health", 
            catch_response=True,
            timeout=5
        ) as response:
            if response.status_code == 200:
                response.success()
                logger.debug("Health check passed")
            else:
                response.failure(f"Health check failed: {response.status_code}")

    @task(2)
    def get_network_stats(self):
        """Get network statistics."""
        with self.client.get(
            "/api/v1/network/stats",
            catch_response=True,
            timeout=10
        ) as response:
            if response.status_code == 200:
                response.success()
                data = response.json()
                logger.debug(f"Network stats: {data.get('station_count', 0)} stations")
            else:
                response.failure(f"Network stats failed: {response.status_code}")

    @task(5)
    def get_cascades(self):
        """Retrieve cascades list."""
        with self.client.get(
            "/api/v1/cascades?limit=10&offset=0",
            catch_response=True,
            timeout=10
        ) as response:
            if response.status_code == 200:
                response.success()
                try:
                    data = response.json()
                    if data.get("cascades"):
                        self.cascade_id = data["cascades"][0]["id"]
                except ValueError:
                    logger.error("Failed to parse cascades response")
            else:
                response.failure(f"Cascades endpoint failed: {response.status_code}")

    @task(3)
    def get_cascade_detail(self):
        """Get cascade details."""
        if self.cascade_id:
            with self.client.get(
                f"/api/v1/cascades/{self.cascade_id}",
                catch_response=True,
                timeout=10
            ) as response:
                if response.status_code == 200:
                    response.success()
                    logger.debug(f"Retrieved cascade detail: {self.cascade_id}")
                else:
                    response.failure(f"Cascade detail failed: {response.status_code}")

    @task(4)
    def get_alerts(self):
        """Retrieve alerts list."""
        with self.client.get(
            "/api/v1/alerts?severity=HIGH&limit=10",
            catch_response=True,
            timeout=10
        ) as response:
            if response.status_code == 200:
                response.success()
                try:
                    data = response.json()
                    if data.get("alerts"):
                        self.alert_id = data["alerts"][0]["id"]
                except ValueError:
                    logger.error("Failed to parse alerts response")
            else:
                response.failure(f"Alerts endpoint failed: {response.status_code}")

    @task(2)
    def post_alert_acknowledge(self):
        """Acknowledge an alert."""
        if self.alert_id:
            payload = {"status": "acknowledged", "notes": "Acknowledged by load test"}
            with self.client.put(
                f"/api/v1/alerts/{self.alert_id}",
                json=payload,
                catch_response=True,
                timeout=10
            ) as response:
                if response.status_code in [200, 204]:
                    response.success()
                    logger.debug(f"Alert acknowledged: {self.alert_id}")
                else:
                    response.failure(f"Alert ack failed: {response.status_code}")

    @task(2)
    def get_metrics(self):
        """Get system metrics."""
        with self.client.get(
            "/api/v1/metrics/system",
            catch_response=True,
            timeout=10
        ) as response:
            if response.status_code == 200:
                response.success()
                logger.debug("Metrics retrieved")
            else:
                response.failure(f"Metrics endpoint failed: {response.status_code}")

    @task(1)
    def get_cascade_simulation(self):
        """Get cascade simulation data."""
        with self.client.get(
            "/api/v1/cascades/simulate?duration=300",
            catch_response=True,
            timeout=15
        ) as response:
            if response.status_code == 200:
                response.success()
                logger.debug("Simulation data retrieved")
            else:
                response.failure(f"Simulation endpoint failed: {response.status_code}")


class DrishtiUser(FastHttpUser):
    """Fast HTTP user for load testing."""
    
    tasks = [DrishtiTasks]
    wait_time = between(1, 5)  # Wait 1-5 seconds between tasks
    
    def on_start(self):
        """Initialize user."""
        super().on_start()
        logger.info(f"User {self.client_id} started")
    
    def on_stop(self):
        """Clean up user."""
        logger.info(f"User {self.client_id} stopped")


class DrishtiWebSocketUser(HttpUser):
    """WebSocket user for load testing real-time connections."""
    
    wait_time = between(2, 5)
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.ws = None
    
    def on_start(self):
        """Initialize WebSocket connection."""
        import websocket
        try:
            # Connect to WebSocket endpoint
            ws_url = self.host.replace("http://", "ws://").replace("https://", "wss://")
            self.ws = websocket.WebSocket()
            self.ws.connect(f"{ws_url}/ws/alerts")
            logger.info(f"WebSocket connected for user {self.client_id}")
        except Exception as e:
            logger.error(f"WebSocket connection failed: {e}")
    
    @task(1)
    def receive_message(self):
        """Receive WebSocket message."""
        if self.ws:
            try:
                msg = self.ws.recv()
                if msg:
                    logger.debug(f"Received WebSocket message: {msg[:50]}")
            except Exception as e:
                logger.error(f"WebSocket receive failed: {e}")
    
    def on_stop(self):
        """Close WebSocket connection."""
        if self.ws:
            try:
                self.ws.close()
                logger.info(f"WebSocket closed for user {self.client_id}")
            except Exception as e:
                logger.error(f"WebSocket close failed: {e}")


# Event handlers for reporting
@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Called when load test starts."""
    logger.info("=" * 60)
    logger.info("DRISHTI Load Test Started")
    logger.info(f"Target: {environment.host}")
    logger.info("=" * 60)


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Called when load test stops."""
    logger.info("=" * 60)
    logger.info("DRISHTI Load Test Completed")
    logger.info("=" * 60)


@events.quitting.add_listener
def on_quit(environment, **kwargs):
    """Called when test is quitting."""
    # Print test summary
    print("\n" + "=" * 60)
    print("LOAD TEST SUMMARY")
    print("=" * 60)
    
    stats = environment.stats
    
    total_requests = stats.total.num_requests
    total_failures = stats.total.num_failures
    total_response_time = stats.total.total_response_time
    
    if total_requests > 0:
        avg_response_time = total_response_time / total_requests
        failure_rate = (total_failures / total_requests) * 100
        
        print(f"Total Requests: {total_requests}")
        print(f"Total Failures: {total_failures}")
        print(f"Failure Rate: {failure_rate:.2f}%")
        print(f"Average Response Time: {avg_response_time:.2f}ms")
        print(f"Min Response Time: {stats.total.min_response_time:.2f}ms")
        print(f"Max Response Time: {stats.total.max_response_time:.2f}ms")
        
        print("\nResponse Time Distribution:")
        if hasattr(stats.total, 'percentiles'):
            for percentile_name, value in stats.total.percentiles().items():
                if value is not None:
                    print(f"  {percentile_name}: {value:.2f}ms")
    
    print("=" * 60 + "\n")
