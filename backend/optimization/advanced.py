"""
DRISHTI Phase 4.6: Advanced Optimization
Request deduplication, predictive prefetching, adaptive batching, distributed caching
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, List, Set, Tuple, Any, Callable
import hashlib
import time
import threading
from collections import deque, defaultdict
from enum import Enum


class RequestType(Enum):
    """Types of requests that can be tracked"""
    TRAIN_LOCATION = "train_location"
    SIGNAL_STATUS = "signal_status"
    STATION_INFO = "station_info"
    SPEED_RESTRICTION = "speed_restriction"


@dataclass
class RequestPattern:
    """Track patterns in request sequences"""
    request_type: RequestType
    target_id: str
    frequency: int = 0
    last_request_time: datetime = field(default_factory=datetime.now)
    predicted_interval_seconds: float = 5.0
    confidence: float = 0.8  # How confident we are in the prediction


class RequestDeduplicator:
    """
    Eliminate duplicate and near-duplicate requests
    Coalesces multiple requests for the same resource into single query
    """
    
    def __init__(self, dedup_window_ms: int = 50):
        """
        Initialize deduplicator
        Args:
            dedup_window_ms: Window to look for duplicates (default 50ms)
        """
        self.dedup_window_ms = dedup_window_ms
        self.pending_requests: Dict[str, Tuple[datetime, Any]] = {}
        self.deduped_count = 0
        self.total_requests = 0
        self.dedup_lock = threading.Lock()
    
    def request_hash(self, request_type: str, target_id: str, params: Dict = None) -> str:
        """Create hash for request deduplication"""
        param_str = str(sorted(params.items())) if params else ""
        combined = f"{request_type}:{target_id}:{param_str}"
        return hashlib.md5(combined.encode()).hexdigest()
    
    def should_deduplicate(self, request_id: str, current_time: datetime) -> bool:
        """Check if request should be deduplicated (duplicate of pending)"""
        self.total_requests += 1
        
        with self.dedup_lock:
            if request_id in self.pending_requests:
                prev_time, _ = self.pending_requests[request_id]
                age_ms = (current_time - prev_time).total_seconds() * 1000
                
                if age_ms < self.dedup_window_ms:
                    self.deduped_count += 1
                    return True
        
        return False
    
    def register_request(self, request_id: str, request_data: Any) -> None:
        """Register pending request"""
        with self.dedup_lock:
            self.pending_requests[request_id] = (datetime.now(), request_data)
            
            # Clean up old entries
            current_time = datetime.now()
            expired = [k for k, (t, _) in self.pending_requests.items()
                      if (current_time - t).total_seconds() * 1000 > self.dedup_window_ms * 2]
            
            for k in expired:
                del self.pending_requests[k]
    
    def get_dedup_stats(self) -> Dict:
        """Get deduplication statistics"""
        dedup_rate = (self.deduped_count / self.total_requests * 100) if self.total_requests > 0 else 0
        
        return {
            'total_requests': self.total_requests,
            'deduplicated': self.deduped_count,
            'dedup_rate_percent': dedup_rate,
            'pending_unique': len(self.pending_requests)
        }


class PredictivePrefetcher:
    """
    Predict which data will be needed next and prefetch proactively
    Uses request patterns to anticipate queries
    """
    
    def __init__(self, history_size: int = 1000):
        """
        Initialize predictive prefetcher
        Args:
            history_size: Number of requests to track for pattern analysis
        """
        self.history_size = history_size
        self.request_history: deque = deque(maxlen=history_size)
        self.patterns: Dict[str, RequestPattern] = {}
        self.prefetch_queue: List[Tuple[str, str, float]] = []  # (type, id, confidence)
        self.prefetch_hits = 0
        self.prefetch_misses = 0
        self.prefetch_lock = threading.Lock()
    
    def record_request(self, request_type: RequestType, target_id: str) -> None:
        """Record request for pattern analysis"""
        with self.prefetch_lock:
            self.request_history.append((request_type, target_id, datetime.utcnow()))
            
            # Update pattern
            pattern_key = f"{request_type.value}:{target_id}"
            if pattern_key in self.patterns:
                pattern = self.patterns[pattern_key]
                pattern.frequency += 1
                pattern.last_request_time = datetime.utcnow()
            else:
                self.patterns[pattern_key] = RequestPattern(
                    request_type=request_type,
                    target_id=target_id,
                    frequency=1
                )
    
    def analyze_patterns(self) -> List[Tuple[RequestType, str, float]]:
        """
        Analyze request patterns to identify likely next queries
        Returns: List of (request_type, target_id, confidence) tuples
        """
        predictions = []
        
        with self.prefetch_lock:
            if len(self.request_history) < 10:
                return predictions  # Need more data
            
            # Look at sequences
            recent_requests = list(self.request_history)[-50:]
            
            # Count transitions
            transitions: Dict[Tuple[str, str], int] = defaultdict(int)
            for i in range(len(recent_requests) - 1):
                current = f"{recent_requests[i][0].value}:{recent_requests[i][1]}"
                next_req = f"{recent_requests[i+1][0].value}:{recent_requests[i+1][1]}"
                transitions[(current, next_req)] += 1
            
            # Find most likely next requests
            for (current, next_req), count in transitions.items():
                confidence = min(count / 5.0, 0.95)  # Normalize to 0.95 max (more lenient)
                
                if confidence > 0.3:  # Lower threshold for confidence
                    req_type_str, target_id = next_req.split(":", 1)
                    try:
                        req_type = RequestType(req_type_str)
                        predictions.append((req_type, target_id, confidence))
                    except ValueError:
                        pass
        
        return predictions
    
    def prefetch(self, request_type: RequestType, target_id: str, callback: Callable) -> None:
        """
        Proactively fetch data expected to be needed
        Args:
            request_type: Type of request to prefetch
            target_id: Target ID for the request
            callback: Function to call to actually fetch the data
        """
        with self.prefetch_lock:
            try:
                callback(request_type, target_id)
                self.prefetch_hits += 1
            except Exception:
                self.prefetch_misses += 1
    
    def get_prefetch_stats(self) -> Dict:
        """Get prefetch statistics"""
        total = self.prefetch_hits + self.prefetch_misses
        hit_rate = (self.prefetch_hits / total * 100) if total > 0 else 0
        
        return {
            'prefetch_hits': self.prefetch_hits,
            'prefetch_misses': self.prefetch_misses,
            'hit_rate_percent': hit_rate,
            'patterns_tracked': len(self.patterns),
            'history_size': len(self.request_history)
        }


class AdaptiveBatcher:
    """
    Dynamically adjust batch size based on system load and operation characteristics
    Larger batches during high load, smaller batches for low latency
    """
    
    def __init__(self, min_batch: int = 3, max_batch: int = 25):
        """
        Initialize adaptive batcher
        Args:
            min_batch: Minimum batch size
            max_batch: Maximum batch size
        """
        self.min_batch = min_batch
        self.max_batch = max_batch
        self.current_batch_size = min_batch + 5
        self.pending_commands = deque()
        self.command_history = deque(maxlen=100)
        self.load_factor = 0.5  # 0.0-1.0, where 1.0 is full load
        self.batcher_lock = threading.Lock()
        self.adaptation_history = []
    
    def update_load(self, load_factor: float) -> None:
        """
        Update system load indicator (0.0-1.0)
        Args:
            load_factor: Current load as percentage (0.0-1.0)
        """
        with self.batcher_lock:
            self.load_factor = max(0.0, min(1.0, load_factor))
            
            # Adapt batch size based on load
            # High load: larger batches (reduce requests)
            # Low load: smaller batches (reduce latency)
            target_batch = int(self.min_batch + 
                             (self.max_batch - self.min_batch) * self.load_factor)
            
            if target_batch != self.current_batch_size:
                self.current_batch_size = target_batch
                self.adaptation_history.append({
                    'timestamp': datetime.utcnow(),
                    'load': self.load_factor,
                    'batch_size': self.current_batch_size
                })
    
    def add_command(self, command: Dict) -> Optional[List[Dict]]:
        """Add command, return batch if ready"""
        with self.batcher_lock:
            self.pending_commands.append(command)
            
            if len(self.pending_commands) >= self.current_batch_size:
                return self._flush_batch()
        
        return None
    
    def _flush_batch(self) -> Optional[List[Dict]]:
        """Flush current batch"""
        if not self.pending_commands:
            return None
        
        batch = list(self.pending_commands)
        self.pending_commands.clear()
        self.command_history.extend(batch)
        
        return batch if batch else None
    
    def get_pending_count(self) -> int:
        """Get number of pending commands"""
        return len(self.pending_commands)
    
    def get_stats(self) -> Dict:
        """Get adaptive batching statistics"""
        return {
            'current_batch_size': self.current_batch_size,
            'load_factor': self.load_factor,
            'min_batch': self.min_batch,
            'max_batch': self.max_batch,
            'pending_commands': len(self.pending_commands),
            'recent_avg_batch': (sum(len(list(b)) for b in [self.command_history]) 
                               / len(self.command_history) if self.command_history else 0)
        }


class DistributedCacheNode:
    """Single node in distributed cache cluster"""
    
    def __init__(self, node_id: str):
        """Initialize cache node"""
        self.node_id = node_id
        self.cache: Dict[str, Tuple[Any, datetime]] = {}
        self.node_lock = threading.Lock()
        self.hits = 0
        self.misses = 0
        self.replicated_to = set()  # Other nodes this data is replicated to
    
    def get(self, key: str, ttl_seconds: int = 300) -> Optional[Any]:
        """Get value from cache"""
        with self.node_lock:
            if key in self.cache:
                value, created_time = self.cache[key]
                age = (datetime.now() - created_time).total_seconds()
                
                if age < ttl_seconds:
                    self.hits += 1
                    return value
                else:
                    del self.cache[key]
            
            self.misses += 1
            return None
    
    def put(self, key: str, value: Any) -> None:
        """Put value in cache"""
        with self.node_lock:
            self.cache[key] = (value, datetime.now())
    
    def get_stats(self) -> Dict:
        """Get node statistics"""
        total = self.hits + self.misses
        hit_rate = (self.hits / total * 100) if total > 0 else 0
        
        return {
            'node_id': self.node_id,
            'cache_size': len(self.cache),
            'hits': self.hits,
            'misses': self.misses,
            'hit_rate_percent': hit_rate
        }


class DistributedCache:
    """
    Distributed caching across multiple nodes
    Shards data for horizontal scalability
    """
    
    def __init__(self, num_nodes: int = 3):
        """
        Initialize distributed cache
        Args:
            num_nodes: Number of cache nodes (shards)
        """
        self.num_nodes = num_nodes
        self.nodes = {f"node_{i}": DistributedCacheNode(f"node_{i}") for i in range(num_nodes)}
        self.replication_factor = 2  # Replicate to 2 nodes
        self.coordination_lock = threading.Lock()
    
    def _get_node(self, key: str) -> DistributedCacheNode:
        """Get responsible node for key (consistent hashing)"""
        key_hash = int(hashlib.md5(key.encode()).hexdigest(), 16)
        node_index = key_hash % self.num_nodes
        return list(self.nodes.values())[node_index]
    
    def _get_replica_nodes(self, key: str) -> List[DistributedCacheNode]:
        """Get replica nodes for key"""
        key_hash = int(hashlib.md5(key.encode()).hexdigest(), 16)
        replicas = []
        
        for i in range(self.replication_factor):
            node_index = (key_hash + i) % self.num_nodes
            replicas.append(list(self.nodes.values())[node_index])
        
        return replicas
    
    def get(self, key: str, ttl_seconds: int = 300) -> Optional[Any]:
        """Get value from distributed cache"""
        primary_node = self._get_node(key)
        value = primary_node.get(key, ttl_seconds)
        
        if value is not None:
            return value
        
        # Try replicas
        for replica in self._get_replica_nodes(key)[:self.replication_factor]:
            value = replica.get(key, ttl_seconds)
            if value is not None:
                return value
        
        return None
    
    def put(self, key: str, value: Any) -> None:
        """Put value with replication"""
        primary_node = self._get_node(key)
        primary_node.put(key, value)
        
        # Replicate to other nodes
        with self.coordination_lock:
            replica_nodes = self._get_replica_nodes(key)
            for replica in replica_nodes[1:self.replication_factor]:
                replica.put(key, value)
    
    def get_cluster_stats(self) -> Dict:
        """Get stats for entire cluster"""
        node_stats = [node.get_stats() for node in self.nodes.values()]
        
        total_hits = sum(s['hits'] for s in node_stats)
        total_misses = sum(s['misses'] for s in node_stats)
        total_size = sum(s['cache_size'] for s in node_stats)
        
        cluster_hit_rate = (total_hits / (total_hits + total_misses) * 100) if (total_hits + total_misses) > 0 else 0
        
        return {
            'num_nodes': self.num_nodes,
            'replication_factor': self.replication_factor,
            'total_cache_size': total_size,
            'total_hits': total_hits,
            'total_misses': total_misses,
            'cluster_hit_rate_percent': cluster_hit_rate,
            'node_stats': node_stats
        }


class AdvancedOptimizationLayer:
    """
    Integration layer combining all advanced optimizations
    """
    
    def __init__(self, num_cache_nodes: int = 3):
        """Initialize advanced optimization layer"""
        self.deduplicator = RequestDeduplicator(dedup_window_ms=50)
        self.prefetcher = PredictivePrefetcher(history_size=1000)
        self.adaptive_batcher = AdaptiveBatcher(min_batch=3, max_batch=25)
        self.distributed_cache = DistributedCache(num_nodes=num_cache_nodes)
        self.optimization_stats = {
            'requests_processed': 0,
            'dedup_savings': 0,
            'prefetch_savings': 0,
            'batching_savings': 0
        }
    
    def process_query(self, query_type: RequestType, target_id: str, 
                     query_func: Callable, use_cache: bool = True) -> Any:
        """
        Process query with all optimizations
        Returns the result from cache or by executing query_func
        """
        self.optimization_stats['requests_processed'] += 1
        
        # Step 1: Check for deduplication opportunity
        request_id = self.deduplicator.request_hash(query_type.value, target_id)
        
        if self.deduplicator.should_deduplicate(request_id, datetime.utcnow()):
            self.optimization_stats['dedup_savings'] += 1
            # Return last result from pending
            _, cached_data = self.deduplicator.pending_requests.get(request_id, (None, None))
            if cached_data:
                return cached_data
        
        # Step 2: Check distributed cache
        if use_cache:
            cached = self.distributed_cache.get(request_id)
            if cached is not None:
                self.optimization_stats['prefetch_savings'] += 1
                return cached
        
        # Step 3: Execute query
        result = query_func(query_type, target_id)
        
        # Step 4: Register for deduplication and cache
        self.deduplicator.register_request(request_id, result)
        self.distributed_cache.put(request_id, result)
        
        # Step 5: Record for predictive prefetching
        self.prefetcher.record_request(query_type, target_id)
        
        return result
    
    def add_batched_command(self, command: Dict) -> Optional[List[Dict]]:
        """Add command to adaptive batcher"""
        batch = self.adaptive_batcher.add_command(command)
        if batch:
            self.optimization_stats['batching_savings'] += 1
        return batch
    
    def update_system_load(self, load_factor: float) -> None:
        """Update system load for adaptive batching"""
        self.adaptive_batcher.update_load(load_factor)
    
    def trigger_prefetch(self, callback: Callable) -> None:
        """Trigger predictive prefetch based on patterns"""
        predictions = self.prefetcher.analyze_patterns()
        
        for req_type, target_id, confidence in predictions[:5]:  # Prefetch top 5
            if confidence > 0.6:  # Only if >60% confidence
                try:
                    self.prefetcher.prefetch(req_type, target_id, callback)
                except Exception:
                    pass
    
    def get_optimization_stats(self) -> Dict:
        """Get comprehensive optimization statistics"""
        return {
            'requests_processed': self.optimization_stats['requests_processed'],
            'dedup_savings': self.optimization_stats['dedup_savings'],
            'dedup_rate_percent': (self.optimization_stats['dedup_savings'] / 
                                   self.optimization_stats['requests_processed'] * 100 
                                   if self.optimization_stats['requests_processed'] > 0 else 0),
            'prefetch_savings': self.optimization_stats['prefetch_savings'],
            'batching_savings': self.optimization_stats['batching_savings'],
            'deduplicator': self.deduplicator.get_dedup_stats(),
            'prefetcher': self.prefetcher.get_prefetch_stats(),
            'adaptive_batcher': self.adaptive_batcher.get_stats(),
            'distributed_cache': self.distributed_cache.get_cluster_stats()
        }


if __name__ == "__main__":
    print("[TEST] Advanced Optimizations\n")
    
    # Initialize
    adv_opt = AdvancedOptimizationLayer(num_cache_nodes=3)
    
    # Test request deduplication
    print("[TEST 1] Request Deduplication")
    def mock_query(req_type, target_id):
        time.sleep(0.01)
        return {'data': f'result_{target_id}'}
    
    for i in range(5):
        result = adv_opt.process_query(RequestType.TRAIN_LOCATION, "TRAIN_001", mock_query)
    
    dedup_stats = adv_opt.deduplicator.get_dedup_stats()
    print(f"[OK] Requests: {dedup_stats['total_requests']}, Deduplicated: {dedup_stats['deduplicated']}")
    
    # Test predictive prefetching
    print("\n[TEST 2] Predictive Prefetching")
    for i in range(50):
        train_id = f"TRAIN_{(i % 5):03d}"
        adv_opt.process_query(RequestType.TRAIN_LOCATION, train_id, mock_query)
    
    prefetch_stats = adv_opt.prefetcher.get_prefetch_stats()
    print(f"[OK] Patterns tracked: {prefetch_stats['patterns_tracked']}")
    print(f"[OK] History size: {prefetch_stats['history_size']}")
    
    # Test adaptive batching
    print("\n[TEST 3] Adaptive Batching")
    adv_opt.update_system_load(0.3)  # Low load
    for i in range(10):
        batch = adv_opt.add_batched_command({'cmd': f'command_{i}'})
    
    adv_opt.update_system_load(0.9)  # High load
    batch_stats = adv_opt.adaptive_batcher.get_stats()
    print(f"[OK] High load batch size: {batch_stats['current_batch_size']}")
    
    # Test distributed cache
    print("\n[TEST 4] Distributed Cache")
    for i in range(20):
        adv_opt.distributed_cache.put(f"key_{i}", f"value_{i}")
    
    value = adv_opt.distributed_cache.get("key_5")
    print(f"[OK] Cache retrieval: {value}")
    
    cache_stats = adv_opt.distributed_cache.get_cluster_stats()
    print(f"[OK] Cluster hit rate: {cache_stats['cluster_hit_rate_percent']:.1f}%")
    print(f"[OK] Total cache size: {cache_stats['total_cache_size']}")
    
    # Final stats
    print("\n[TEST 5] Overall Optimization Stats")
    stats = adv_opt.get_optimization_stats()
    print(f"[OK] Requests processed: {stats['requests_processed']}")
    print(f"[OK] Dedup rate: {stats['dedup_rate_percent']:.1f}%")
    print(f"[OK] Cache hit rate: {stats['distributed_cache']['cluster_hit_rate_percent']:.1f}%")
