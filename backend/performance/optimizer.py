"""
DRISHTI Phase 4.5: Performance Optimization
Caching, connection pooling, and latency reduction for high-throughput scenarios
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple, Any
import hashlib
import time
from collections import OrderedDict


class CachePolicy(object):
    """Cache replacement policies"""
    LRU = "LRU"          # Least Recently Used
    LFU = "LFU"          # Least Frequently Used
    FIFO = "FIFO"        # First In First Out
    TTL = "TTL"          # Time To Live


@dataclass
class CacheEntry:
    """Single cache entry with metadata"""
    key: str
    value: Any
    created_time: datetime = field(default_factory=datetime.utcnow)
    last_accessed: datetime = field(default_factory=datetime.utcnow)
    access_count: int = 0
    ttl_seconds: Optional[int] = None
    
    def is_expired(self) -> bool:
        """Check if entry has expired (TTL)"""
        if self.ttl_seconds is None:
            return False
        age = (datetime.utcnow() - self.created_time).total_seconds()
        return age > self.ttl_seconds
    
    def touch(self):
        """Update access time and count"""
        self.last_accessed = datetime.utcnow()
        self.access_count += 1


class PerformanceCache:
    """
    Multi-policy in-memory cache for NTES queries and SCADA responses
    Supports LRU, LFU, FIFO, and TTL policies
    """
    
    def __init__(self, max_size: int = 10000, policy: str = CachePolicy.LRU):
        """
        Initialize cache
        Args:
            max_size: Maximum number of entries
            policy: Eviction policy (LRU, LFU, FIFO, TTL)
        """
        self.max_size = max_size
        self.policy = policy
        self.cache: Dict[str, CacheEntry] = {}
        self.access_order = OrderedDict()  # For LRU/FIFO
        self.stats = {
            'hits': 0,
            'misses': 0,
            'evictions': 0,
            'insertions': 0
        }
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        if key in self.cache:
            entry = self.cache[key]
            
            # Check if expired
            if entry.is_expired():
                del self.cache[key]
                self.stats['misses'] += 1
                return None
            
            # Touch entry and update stats
            entry.touch()
            self.stats['hits'] += 1
            
            # Update LRU order
            if self.policy == CachePolicy.LRU:
                self.access_order.move_to_end(key)
            
            return entry.value
        
        self.stats['misses'] += 1
        return None
    
    def put(self, key: str, value: Any, ttl_seconds: Optional[int] = None) -> None:
        """Put value into cache"""
        # If cache is full, evict
        if len(self.cache) >= self.max_size and key not in self.cache:
            self._evict_one()
        
        # Create/update entry
        entry = CacheEntry(key=key, value=value, ttl_seconds=ttl_seconds)
        self.cache[key] = entry
        self.access_order[key] = True
        self.stats['insertions'] += 1
    
    def _evict_one(self) -> None:
        """Evict one entry based on policy"""
        if not self.cache:
            return
        
        if self.policy == CachePolicy.LRU:
            # Remove least recently used (first in OrderedDict)
            key = next(iter(self.access_order))
            del self.cache[key]
            del self.access_order[key]
        
        elif self.policy == CachePolicy.LFU:
            # Remove least frequently used
            key = min(self.cache.keys(), 
                     key=lambda k: self.cache[k].access_count)
            del self.cache[key]
            if key in self.access_order:
                del self.access_order[key]
        
        elif self.policy == CachePolicy.FIFO:
            # Remove first entry (oldest)
            key = next(iter(self.access_order))
            del self.cache[key]
            del self.access_order[key]
        
        self.stats['evictions'] += 1
    
    def clear(self) -> None:
        """Clear entire cache"""
        self.cache.clear()
        self.access_order.clear()
    
    def size(self) -> int:
        """Get current cache size"""
        return len(self.cache)
    
    def get_stats(self) -> Dict:
        """Get cache statistics"""
        total_requests = self.stats['hits'] + self.stats['misses']
        hit_rate = (self.stats['hits'] / total_requests * 100) if total_requests > 0 else 0
        
        return {
            'policy': self.policy,
            'max_size': self.max_size,
            'current_size': len(self.cache),
            'hits': self.stats['hits'],
            'misses': self.stats['misses'],
            'hit_rate_percent': hit_rate,
            'evictions': self.stats['evictions'],
            'insertions': self.stats['insertions']
        }


class NTESCacheLayer:
    """
    Caching layer for NTES (National Train Enquiry System) queries
    Caches train location data to reduce latency and system load
    """
    
    def __init__(self, ttl_seconds: int = 5):  # 5 second cache for train location
        """
        Initialize NTES cache
        Args:
            ttl_seconds: Time to live for cached entries
        """
        self.cache = PerformanceCache(max_size=5000, policy=CachePolicy.LRU)
        self.ttl_seconds = ttl_seconds
        self.query_latency_tracker = []  # Track query times
    
    def cache_train_location(self, train_id: str, location_data: Dict) -> None:
        """Cache train location query result"""
        cache_key = f"train_loc:{train_id}"
        self.cache.put(cache_key, location_data, self.ttl_seconds)
    
    def get_train_location(self, train_id: str) -> Optional[Dict]:
        """Get cached train location"""
        cache_key = f"train_loc:{train_id}"
        return self.cache.get(cache_key)
    
    def cache_station_info(self, station_code: str, station_data: Dict) -> None:
        """Cache station information"""
        cache_key = f"station:{station_code}"
        self.cache.put(cache_key, station_data, ttl_seconds=300)  # 5 min for static data
    
    def get_station_info(self, station_code: str) -> Optional[Dict]:
        """Get cached station info"""
        cache_key = f"station:{station_code}"
        return self.cache.get(cache_key)
    
    def cache_route_segment(self, seg_id: str, segment_data: Dict) -> None:
        """Cache route segment data"""
        cache_key = f"segment:{seg_id}"
        self.cache.put(cache_key, segment_data, ttl_seconds=600)  # 10 min
    
    def get_route_segment(self, seg_id: str) -> Optional[Dict]:
        """Get cached route segment"""
        cache_key = f"segment:{seg_id}"
        return self.cache.get(cache_key)
    
    def get_cache_stats(self) -> Dict:
        """Get cache statistics"""
        return self.cache.get_stats()


class ConnectionPool:
    """
    Connection pool for SCADA connections
    Reuses connections to reduce handshake overhead
    """
    
    def __init__(self, pool_size: int = 10):
        """
        Initialize connection pool
        Args:
            pool_size: Maximum connections to maintain
        """
        self.pool_size = pool_size
        self.available_connections = []
        self.in_use_connections = set()
        self.connection_stats = {
            'total_created': 0,
            'total_released': 0,
            'peak_usage': 0,
            'avg_lifetime': 0
        }
    
    def acquire_connection(self) -> str:
        """Acquire connection from pool"""
        if self.available_connections:
            conn = self.available_connections.pop()
        else:
            if len(self.in_use_connections) < self.pool_size:
                # Create new connection
                conn = f"CONN_{time.time()}_{len(self.in_use_connections)}"
                self.connection_stats['total_created'] += 1
            else:
                # Wait for available connection (simplified)
                conn = self.available_connections.pop() if self.available_connections else None
        
        if conn:
            self.in_use_connections.add(conn)
            peak = len(self.in_use_connections)
            if peak > self.connection_stats['peak_usage']:
                self.connection_stats['peak_usage'] = peak
        
        return conn
    
    def release_connection(self, conn: str) -> None:
        """Release connection back to pool"""
        if conn in self.in_use_connections:
            self.in_use_connections.remove(conn)
            self.available_connections.append(conn)
            self.connection_stats['total_released'] += 1
    
    def get_stats(self) -> Dict:
        """Get pool statistics"""
        return {
            'pool_size': self.pool_size,
            'available': len(self.available_connections),
            'in_use': len(self.in_use_connections),
            'total_created': self.connection_stats['total_created'],
            'peak_usage': self.connection_stats['peak_usage'],
            'utilization_percent': (len(self.in_use_connections) / self.pool_size * 100)
        }


class CommandBatcher:
    """
    Batch multiple SCADA commands to reduce network overhead
    Sends multiple commands in single request when possible
    """
    
    def __init__(self, batch_size: int = 10, batch_timeout_ms: int = 100):
        """
        Initialize command batcher
        Args:
            batch_size: Maximum commands per batch
            batch_timeout_ms: Max time to wait before sending batch
        """
        self.batch_size = batch_size
        self.batch_timeout_ms = batch_timeout_ms
        self.pending_commands = []
        self.batch_created_time = None
        self.stats = {
            'total_batches': 0,
            'commands_batched': 0,
            'avg_batch_size': 0,
            'savings_percent': 0
        }
    
    def add_command(self, command: Dict) -> Optional[List[Dict]]:
        """Add command to batch, return batch if ready"""
        self.pending_commands.append(command)
        
        # Initialize batch timer
        if self.batch_created_time is None:
            self.batch_created_time = time.time()
        
        # Check if batch is ready
        if len(self.pending_commands) >= self.batch_size:
            return self._flush_batch()
        
        return None
    
    def flush_if_timeout(self) -> Optional[List[Dict]]:
        """Flush batch if timeout exceeded"""
        if not self.pending_commands:
            return None
        
        if self.batch_created_time is None:
            return None
        
        elapsed_ms = (time.time() - self.batch_created_time) * 1000
        if elapsed_ms >= self.batch_timeout_ms:
            return self._flush_batch()
        
        return None
    
    def _flush_batch(self) -> Optional[List[Dict]]:
        """Flush pending commands as batch"""
        if not self.pending_commands:
            return None
        
        batch = self.pending_commands.copy()
        self.pending_commands.clear()
        self.batch_created_time = None
        
        self.stats['total_batches'] += 1
        self.stats['commands_batched'] += len(batch)
        
        if self.stats['total_batches'] > 0:
            self.stats['avg_batch_size'] = (
                self.stats['commands_batched'] / self.stats['total_batches']
            )
        
        # Calculate savings: without batching would need len(batch) requests
        # With batching only need 1 request
        self.stats['savings_percent'] = ((len(batch) - 1) / len(batch) * 100) if len(batch) > 0 else 0
        
        return batch
    
    def get_stats(self) -> Dict:
        """Get batcher statistics"""
        return self.stats.copy()


class LatencyOptimizer:
    """
    Track and optimize command latency through analysis
    """
    
    def __init__(self, window_size: int = 100):
        """
        Initialize latency optimizer
        Args:
            window_size: Number of commands to track for analysis
        """
        self.window_size = window_size
        self.command_times: List[float] = []
        self.signal_times: List[float] = []
        self.train_query_times: List[float] = []
    
    def record_command_latency(self, latency_ms: float, command_type: str) -> None:
        """Record command execution latency"""
        self.command_times.append(latency_ms)
        if len(self.command_times) > self.window_size:
            self.command_times.pop(0)
        
        # Track by type
        if command_type == "signal":
            self.signal_times.append(latency_ms)
            if len(self.signal_times) > self.window_size:
                self.signal_times.pop(0)
        elif command_type == "train_query":
            self.train_query_times.append(latency_ms)
            if len(self.train_query_times) > self.window_size:
                self.train_query_times.pop(0)
    
    def get_latency_stats(self) -> Dict:
        """Get latency analysis"""
        def calc_stats(times_list):
            if not times_list:
                return {'min': 0, 'max': 0, 'avg': 0, 'p95': 0, 'p99': 0}
            
            sorted_times = sorted(times_list)
            n = len(sorted_times)
            
            return {
                'min': sorted_times[0],
                'max': sorted_times[-1],
                'avg': sum(sorted_times) / n,
                'p95': sorted_times[int(n * 0.95)] if n > 0 else 0,
                'p99': sorted_times[int(n * 0.99)] if n > 0 else 0,
                'count': n
            }
        
        return {
            'all_commands': calc_stats(self.command_times),
            'signal_commands': calc_stats(self.signal_times),
            'train_queries': calc_stats(self.train_query_times)
        }


class OptimizedSCADAConnector:
    """
    Performance-optimized SCADA connector with caching, pooling, and batching
    """
    
    def __init__(self):
        """Initialize optimized SCADA connector"""
        self.connection_pool = ConnectionPool(pool_size=20)
        self.command_batcher = CommandBatcher(batch_size=10, batch_timeout_ms=50)
        self.latency_optimizer = LatencyOptimizer()
        self.response_cache = PerformanceCache(max_size=1000, policy=CachePolicy.LRU)
        self.command_history = []
        self.optimization_stats = {
            'cache_hits': 0,
            'cache_misses': 0,
            'connection_reuses': 0,
            'batches_sent': 0
        }
    
    def execute_signal_command_optimized(self, signal_id: str, state: str) -> Dict:
        """Execute signal command with optimizations"""
        start_time = time.time()
        
        # Check cache
        cache_key = f"signal:{signal_id}"
        cached = self.response_cache.get(cache_key)
        if cached and cached.get('state') == state:
            self.optimization_stats['cache_hits'] += 1
            latency_ms = (time.time() - start_time) * 1000
            self.latency_optimizer.record_command_latency(latency_ms, 'signal')
            return cached
        
        # Acquire connection
        conn = self.connection_pool.acquire_connection()
        self.optimization_stats['connection_reuses'] += 1
        
        try:
            # Build command
            command = {
                'type': 'signal',
                'signal_id': signal_id,
                'state': state,
                'connection': conn
            }
            
            # Try to batch
            batch = self.command_batcher.add_command(command)
            
            # Simulate SCADA execution
            response = {
                'status': 'success',
                'signal_id': signal_id,
                'state': state,
                'timestamp': datetime.utcnow().isoformat()
            }
            
            # Cache result
            self.response_cache.put(cache_key, response, ttl_seconds=10)
            
            # Record latency
            latency_ms = (time.time() - start_time) * 1000
            self.latency_optimizer.record_command_latency(latency_ms, 'signal')
            
            return response
        
        finally:
            self.connection_pool.release_connection(conn)
    
    def execute_train_query_optimized(self, train_id: str) -> Dict:
        """Execute train query with caching"""
        start_time = time.time()
        
        # Check cache first
        cache_key = f"train:{train_id}"
        cached = self.response_cache.get(cache_key)
        if cached:
            self.optimization_stats['cache_hits'] += 1
            latency_ms = (time.time() - start_time) * 1000
            self.latency_optimizer.record_command_latency(latency_ms, 'train_query')
            return cached
        
        # Acquire connection
        conn = self.connection_pool.acquire_connection()
        self.optimization_stats['connection_reuses'] += 1
        
        try:
            # Simulate NTES query
            response = {
                'status': 'success',
                'train_id': train_id,
                'location_km': 150.5,
                'speed_kmph': 80,
                'timestamp': datetime.utcnow().isoformat()
            }
            
            # Cache with shorter TTL
            self.response_cache.put(cache_key, response, ttl_seconds=5)
            
            # Record latency
            latency_ms = (time.time() - start_time) * 1000
            self.latency_optimizer.record_command_latency(latency_ms, 'train_query')
            
            return response
        
        finally:
            self.connection_pool.release_connection(conn)
    
    def get_performance_stats(self) -> Dict:
        """Get overall performance statistics"""
        return {
            'optimization_stats': self.optimization_stats,
            'cache_stats': self.response_cache.get_stats(),
            'pool_stats': self.connection_pool.get_stats(),
            'batcher_stats': self.command_batcher.get_stats(),
            'latency_stats': self.latency_optimizer.get_latency_stats()
        }


if __name__ == "__main__":
    # Test performance optimizations
    print("[TEST] Performance Cache")
    cache = PerformanceCache(max_size=100)
    cache.put("key1", "value1", ttl_seconds=30)
    result = cache.get("key1")
    print(f"[OK] Cache hit: {result}")
    print(f"[OK] Cache stats: {cache.get_stats()}")
    
    print("\n[TEST] NTES Cache Layer")
    ntes = NTESCacheLayer(ttl_seconds=5)
    ntes.cache_train_location("TRAIN_001", {"location": 150.5, "speed": 80})
    loc = ntes.get_train_location("TRAIN_001")
    print(f"[OK] Train location cached: {loc}")
    
    print("\n[TEST] Connection Pool")
    pool = ConnectionPool(pool_size=5)
    conn = pool.acquire_connection()
    print(f"[OK] Connection acquired: {conn}")
    pool.release_connection(conn)
    print(f"[OK] Connection pool stats: {pool.get_stats()}")
    
    print("\n[TEST] Command Batcher")
    batcher = CommandBatcher(batch_size=3)
    for i in range(5):
        batch = batcher.add_command({'cmd': f'command_{i}'})
        if batch:
            print(f"[OK] Batch ready: {len(batch)} commands")
    print(f"[OK] Batcher stats: {batcher.get_stats()}")
    
    print("\n[TEST] Optimized SCADA")
    scada = OptimizedSCADAConnector()
    
    # First call - cache miss
    result1 = scada.execute_signal_command_optimized('SIG_001', 'RED')
    print(f"[OK] Signal command (1st): {result1['status']}")
    
    # Second call - cache hit
    result2 = scada.execute_signal_command_optimized('SIG_001', 'RED')
    print(f"[OK] Signal command (2nd - cached): {result2['status']}")
    
    # Train query
    train = scada.execute_train_query_optimized('TRAIN_001')
    print(f"[OK] Train query: {train['location_km']} km @ {train['speed_kmph']} kmph")
    
    print(f"\n[OK] Performance stats:")
    stats = scada.get_performance_stats()
    print(f"    Cache hits: {stats['optimization_stats']['cache_hits']}")
    print(f"    Connection reuses: {stats['optimization_stats']['connection_reuses']}")
    print(f"    Signal latency (avg): {stats['latency_stats']['signal_commands']['avg']:.2f}ms")
