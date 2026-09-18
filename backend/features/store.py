"""
Feature Store: Redis-backed cache
"""

from __future__ import annotations

import json
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class FeatureStore:
    """Redis feature cache for ML inference (with fallback)"""

    def __init__(self, redis_url: str = "redis://localhost:6379/0"):
        self.redis = None
        self._fallback_cache: Dict[str, str] = {}
        try:
            import redis
            self.redis = redis.from_url(redis_url, decode_responses=True)
            self.redis.ping()
            logger.info("FeatureStore connected to Redis")
        except Exception as e:
            logger.warning(f"Redis unavailable: {e}. Using in-memory fallback.")

    def cache_features(self, train_id: str, features: Dict, ttl_hours: int = 24) -> bool:
        """Write features to cache"""
        try:
            key = f"features:train:{train_id}"
            data = json.dumps(features)

            if self.redis:
                ttl_seconds = ttl_hours * 3600
                self.redis.setex(key, ttl_seconds, data)
            else:
                self._fallback_cache[key] = data

            logger.debug(f"Cached features for {train_id}")
            return True
        except Exception as e:
            logger.warning(f"Failed to cache features: {e}")
            return False

    def get_features(self, train_id: str) -> Optional[Dict]:
        """Fetch cached features"""
        try:
            key = f"features:train:{train_id}"

            if self.redis:
                data = self.redis.get(key)
            else:
                data = self._fallback_cache.get(key)

            return json.loads(data) if data else None
        except Exception as e:
            logger.warning(f"Failed to retrieve features: {e}")
            return None

    def delete_features(self, train_id: str) -> bool:
        """Delete cached features"""
        try:
            key = f"features:train:{train_id}"

            if self.redis:
                self.redis.delete(key)
            else:
                self._fallback_cache.pop(key, None)

            return True
        except Exception as e:
            logger.warning(f"Failed to delete features: {e}")
            return False

    def cache_all_accidents(self, accidents: list, ttl_hours: int = 168) -> bool:
        """Cache entire accident corpus"""
        try:
            key = "corpus:all_accidents"
            data = json.dumps([
                {
                    "date": a.date,
                    "station_code": a.station_code,
                    "deaths": a.deaths,
                    "injuries": a.injuries,
                }
                for a in accidents
            ])

            if self.redis:
                ttl_seconds = ttl_hours * 3600
                self.redis.setex(key, ttl_seconds, data)
            else:
                self._fallback_cache[key] = data

            logger.info(f"Cached {len(accidents)} accidents")
            return True
        except Exception as e:
            logger.warning(f"Failed to cache accidents: {e}")
            return False

    def get_all_accidents(self) -> Optional[list]:
        """Fetch cached accidents"""
        try:
            key = "corpus:all_accidents"

            if self.redis:
                data = self.redis.get(key)
            else:
                data = self._fallback_cache.get(key)

            return json.loads(data) if data else None
        except Exception as e:
            logger.warning(f"Failed to retrieve accidents: {e}")
            return None


# Global feature store
feature_store = FeatureStore()
