import os
import json
import logging
import redis

logger = logging.getLogger(__name__)

class RedisStateGrid:
    """
    DRISHTI distributed caching and pub/sub bus.
    Allows 50+ Web Workers to stream the exact same cascade math,
    syncing via Redis instead of isolated per-worker Python memory.
    """
    def __init__(self):
        self.host = os.getenv("REDIS_HOST", "localhost")
        self.port = int(os.getenv("REDIS_PORT", 6379))
        self.redis_client = None
        self.pubsub = None
        self.connected = False
        
        self.connect()

    def connect(self):
        try:
            self.redis_client = redis.Redis(host=self.host, port=self.port, decode_responses=True)
            self.redis_client.ping()
            self.pubsub = self.redis_client.pubsub()
            self.connected = True
            logger.info(f"[DEV-OPS] Connected to Redis Grid at {self.host}:{self.port}")
        except Exception as e:
            logger.warning(f"[DEV-OPS] Redis unavailable. Falling back to local memory isolation. ({e})")
            self.connected = False

    def publish_pulse(self, payload: dict):
        """Broadcasts the entire network operations payload to the cluster."""
        if self.connected:
            try:
                self.redis_client.publish('drishti_alerts_stream', json.dumps(payload))
            except Exception as e:
                logger.error(f"Redis publish failed: {e}")

    def cache_network_state(self, cascade_state: dict):
        """Persists the live graph state so new connections immediately see it."""
        if self.connected:
            self.redis_client.setex('latest_network_pulse', 300, json.dumps(cascade_state))

    def fetch_latest_state(self) -> dict:
        if self.connected:
            data = self.redis_client.get('latest_network_pulse')
            return json.loads(data) if data else None
        return None

# Singleton exported for the workers
grid = RedisStateGrid()
