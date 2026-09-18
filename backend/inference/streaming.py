"""
DRISHTI Real-Time Streaming Pipeline
Subscribes to NTES updates (Kafka/Redis), processes batches, generates alerts
"""

import json
import time
import logging
import threading
from abc import ABC, abstractmethod
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Callable

from backend.inference.engine import UnifiedInferenceEngine
from backend.alerts.engine import AlertGenerator, AuditLog, DrishtiAlert
from backend.inference.config import StreamingConfig, MetricsCollector

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DataSource(ABC):
    """Abstract base for data sources (Kafka, Redis, Mock NTES)"""
    
    @abstractmethod
    def connect(self):
        """Connect to data source"""
        pass
    
    @abstractmethod
    def get_next_batch(self, batch_size: int, timeout_sec: int) -> List[Dict]:
        """Get next batch of trains"""
        pass
    
    @abstractmethod
    def commit(self):
        """Commit offset (for Kafka) or acknowledge (for Redis)"""
        pass
    
    @abstractmethod
    def close(self):
        """Close connection"""
        pass


class MockNTESDataSource(DataSource):
    """Mock NTES publisher for testing without Kafka"""
    
    def __init__(self, config: StreamingConfig):
        self.config = config
        self.queue = deque()
        self.train_counter = 0
        self._running = False
    
    def connect(self):
        """Initialize mock data source"""
        self._running = True
        logger.info("[MOCK] NTES data source ready (no external connection needed)")
    
    def get_next_batch(self, batch_size: int, timeout_sec: int) -> List[Dict]:
        """Generate mock trains for testing"""
        import random
        
        # Generate batch_size mock trains
        batch = []
        for i in range(batch_size):
            self.train_counter += 1
            
            # 90% normal trains, 5% at-risk, 5% critical
            risk_level = random.choices(
                ['normal', 'at_risk', 'critical'],
                weights=[0.9, 0.08, 0.02]
            )[0]
            
            train = {
                'train_id': f'MOCK_{self.train_counter:05d}',
                'source': f'STA{random.randint(1, 100)}',
                'destination': f'STA{random.randint(1, 100)}',
                'current_position': random.randint(0, 500),
                'scheduled_arrival': (datetime.now() + timedelta(minutes=random.randint(10, 120))).isoformat(),
                'actual_delay_minutes': random.randint(-5, 120) if risk_level != 'normal' else random.randint(-5, 10),
                'track_condition': ['good', 'fair', 'poor'][['normal', 'at_risk', 'critical'].index(risk_level)],
                'signal_status': ['clear', 'caution', 'danger'][['normal', 'at_risk', 'critical'].index(risk_level)],
                'maintenance_recent': risk_level in ['at_risk', 'critical'],
                'weather_condition': random.choice(['clear', 'rain', 'fog']),
                'timestamp': datetime.now().isoformat(),
            }
            batch.append(train)
        
        return batch
    
    def commit(self):
        """No-op for mock"""
        pass
    
    def close(self):
        """Shutdown mock source"""
        self._running = False
        logger.info("[MOCK] Shutting down NTES mock source")


class RedisDataSource(DataSource):
    """Redis Streams data source for real-time training"""
    
    def __init__(self, config: StreamingConfig):
        self.config = config
        self.redis_client = None
        self.last_id = '0'
    
    def connect(self):
        """Connect to Redis"""
        try:
            import redis
        except ImportError:
            logger.error("Redis client not installed. Install with: pip install redis")
            raise
        
        try:
            self.redis_client = redis.Redis(
                host=self.config.redis_host,
                port=self.config.redis_port,
                decode_responses=True,
                socket_connect_timeout=5
            )
            self.redis_client.ping()
            logger.info(f"[REDIS] Connected to {self.config.redis_host}:{self.config.redis_port}")
            
            # Try to create consumer group
            try:
                self.redis_client.xgroup_create(
                    self.config.redis_stream_key,
                    self.config.redis_consumer_group,
                    id='0',
                    mkstream=True
                )
            except:
                pass  # Group already exists
            
        except Exception as e:
            logger.error(f"[REDIS] Connection failed: {e}")
            raise
    
    def get_next_batch(self, batch_size: int, timeout_sec: int) -> List[Dict]:
        """Read batch from Redis Stream"""
        try:
            # Read from consumer group
            messages = self.redis_client.xreadgroup(
                self.config.redis_consumer_group,
                'drishti-worker',
                {self.config.redis_stream_key: '>'},
                count=batch_size,
                block=timeout_sec * 1000
            )
            
            batch = []
            if messages:
                for stream_key, entries in messages:
                    for msg_id, data in entries:
                        # Parse train data
                        train = json.loads(data.get('train_data', '{}'))
                        train['redis_id'] = msg_id
                        batch.append(train)
            
            return batch
        
        except Exception as e:
            logger.error(f"[REDIS] Get batch failed: {e}")
            return []
    
    def commit(self):
        """Acknowledge messages (implicit in xreadgroup)"""
        pass
    
    def close(self):
        """Close Redis connection"""
        if self.redis_client:
            self.redis_client.close()
            logger.info("[REDIS] Connection closed")


class KafkaDataSource(DataSource):
    """Kafka data source for production"""
    
    def __init__(self, config: StreamingConfig):
        self.config = config
        self.consumer = None
    
    def connect(self):
        """Connect to Kafka"""
        try:
            from kafka import KafkaConsumer
        except ImportError:
            logger.error("Kafka client not installed. Install with: pip install kafka-python")
            raise
        
        try:
            self.consumer = KafkaConsumer(
                self.config.kafka_topic,
                bootstrap_servers=self.config.kafka_brokers,
                group_id=self.config.kafka_group_id,
                auto_offset_reset='latest',
                value_deserializer=lambda m: json.loads(m.decode('utf-8')),
                session_timeout_ms=30000,
            )
            logger.info(f"[KAFKA] Connected to {self.config.kafka_brokers}, topic: {self.config.kafka_topic}")
        
        except Exception as e:
            logger.error(f"[KAFKA] Connection failed: {e}")
            raise
    
    def get_next_batch(self, batch_size: int, timeout_sec: int) -> List[Dict]:
        """Read batch from Kafka"""
        try:
            batch = []
            start_time = time.time()
            
            while len(batch) < batch_size:
                # Check timeout
                if time.time() - start_time > timeout_sec:
                    break
                
                # Poll with timeout
                messages = self.consumer.poll(timeout_ms=1000)
                
                for _, records in messages.items():
                    for record in records:
                        batch.append(record.value)
                        if len(batch) >= batch_size:
                            break
                    
                    if len(batch) >= batch_size:
                        break
            
            return batch
        
        except Exception as e:
            logger.error(f"[KAFKA] Get batch failed: {e}")
            return []
    
    def commit(self):
        """Commit offsets"""
        if self.consumer:
            try:
                self.consumer.commit()
            except Exception as e:
                logger.warning(f"[KAFKA] Commit failed: {e}")
    
    def close(self):
        """Close Kafka consumer"""
        if self.consumer:
            self.consumer.close()
            logger.info("[KAFKA] Connection closed")


class StreamingPipeline:
    """Real-time streaming pipeline: consume NTES → infer → alert → audit"""
    
    def __init__(self, config: StreamingConfig = None):
        self.config = config or StreamingConfig()
        self.inference_engine = UnifiedInferenceEngine()
        self.alert_generator = AlertGenerator()
        self.audit_log = AuditLog(log_file=self.config.audit_log_file)
        self.data_source = self._create_data_source()
        self.metrics = MetricsCollector()
        self._running = False
        self.results_file = self.config.results_queue_file
    
    def _create_data_source(self) -> DataSource:
        """Create data source based on config"""
        logger.info(f"Creating data source: {self.config.backend}")
        
        if self.config.backend == 'kafka':
            return KafkaDataSource(self.config)
        elif self.config.backend == 'redis':
            return RedisDataSource(self.config)
        else:
            return MockNTESDataSource(self.config)
    
    def connect(self):
        """Connect to data source"""
        self.data_source.connect()
        logger.info(f"[STREAMING] Pipeline initialized ({self.config.backend} backend)")
    
    def process_batch(self, trains: List[Dict]) -> Dict:
        """Process a batch of trains in parallel"""
        start_time = time.time()
        
        if not trains:
            return {'trains': 0, 'alerts': 0, 'latency_ms': 0, 'alert_list': []}
        
        logger.info(f"Processing batch of {len(trains)} trains...")
        
        results = []
        alerts_generated = []
        
        # Use ThreadPoolExecutor for parallel inference
        with ThreadPoolExecutor(max_workers=self.config.max_workers) as executor:
            # Submit all trains for inference
            futures = {
                executor.submit(self._infer_and_alert_train, train): train
                for train in trains
            }
            
            # Collect results as they complete
            for future in as_completed(futures):
                try:
                    result = future.result(timeout=self.config.inference_timeout_sec)
                    results.append(result)
                    
                    if result.get('alert_fired'):
                        alerts_generated.append(result)
                        self.metrics.record_alert(result['alert'].severity)
                
                except Exception as e:
                    logger.error(f"Inference failed: {e}")
                    self.metrics.record_error()
        
        latency_ms = (time.time() - start_time) * 1000
        
        # Record metrics
        self.metrics.record_batch(len(trains), latency_ms, len(alerts_generated))
        
        logger.info(f"Batch complete: {len(trains)} trains, {len(alerts_generated)} alerts, {latency_ms:.1f}ms")
        
        return {
            'trains': len(trains),
            'alerts': len(alerts_generated),
            'latency_ms': round(latency_ms, 2),
            'alert_list': alerts_generated
        }
    
    def _infer_and_alert_train(self, train: Dict) -> Dict:
        """Single train: infer → alert"""
        try:
            # Extract train_id and prepare train_state
            train_id = train.get('train_id', 'UNKNOWN')
            train_state = {
                'station': train.get('current_position', 0),
                'delay': train.get('actual_delay_minutes', 0),
                'speed': 60,  # Default speed
                'route_id': train.get('source', 'UNKNOWN'),
                'maintenance_active': train.get('maintenance_recent', False),
                'lat': 0,
                'lon': 0,
                'time_of_day': 12,
            }
            
            # Run async inference in sync context
            import asyncio
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            inference_result = loop.run_until_complete(
                self.inference_engine.infer_train(train_id, train_state)
            )
            
            # Check if alert fires
            if inference_result and isinstance(inference_result, dict) and inference_result.get('alert_fired'):
                alert = inference_result['alert']
                
                # Record to audit log
                self.audit_log.record_alert(alert)
                
                return {
                    'train_id': train_id,
                    'alert_fired': True,
                    'alert': {
                        'id': str(alert.alert_id),
                        'severity': alert.severity,
                        'risk_score': alert.risk_score,
                        'methods_agreeing': alert.methods_agreeing,
                        'actions': alert.actions,
                    }
                }
            else:
                return {
                    'train_id': train_id,
                    'alert_fired': False
                }
        
        except Exception as e:
            logger.error(f"Train {train.get('train_id', 'UNKNOWN')} inference failed: {e}")
            return {
                'train_id': train.get('train_id', 'UNKNOWN'),
                'alert_fired': False,
                'error': str(e)
            }
    
    def queue_results(self, batch_result: Dict):
        """Queue results for API server to consume"""
        try:
            with open(self.results_file, 'a') as f:
                result_record = {
                    'timestamp': datetime.now().isoformat(),
                    'batch_summary': {
                        'trains': batch_result['trains'],
                        'alerts': batch_result['alerts'],
                        'latency_ms': batch_result['latency_ms']
                    },
                    'alerts': batch_result['alert_list']
                }
                f.write(json.dumps(result_record) + '\n')
        
        except Exception as e:
            logger.error(f"Failed to queue results: {e}")
    
    def run_continuous(self):
        """Run streaming pipeline continuously"""
        self._running = True
        logger.info("[STREAMING] Starting continuous pipeline...")
        
        try:
            while self._running:
                try:
                    # Get next batch
                    trains = self.data_source.get_next_batch(
                        self.config.batch_size,
                        self.config.batch_timeout_sec
                    )
                    
                    if not trains:
                        logger.debug("No trains in batch, waiting...")
                        time.sleep(1)
                        continue
                    
                    # Process batch
                    batch_result = self.process_batch(trains)
                    
                    # Queue results for API
                    self.queue_results(batch_result)
                    
                    # Commit offset
                    self.data_source.commit()
                
                except KeyboardInterrupt:
                    logger.info("Keyboard interrupt, stopping...")
                    break
                
                except Exception as e:
                    logger.error(f"Batch processing error: {e}")
                    self.metrics.record_error()
                    time.sleep(1)
        
        finally:
            self.stop()
    
    def run_single_batch(self):
        """Run pipeline for single batch (for testing)"""
        logger.info("[STREAMING] Processing single batch...")
        
        trains = self.data_source.get_next_batch(
            self.config.batch_size,
            self.config.batch_timeout_sec
        )
        
        if trains:
            batch_result = self.process_batch(trains)
            self.queue_results(batch_result)
            self.data_source.commit()
            return batch_result
        
        return None
    
    def stop(self):
        """Stop streaming pipeline"""
        self._running = False
        self.data_source.close()
        logger.info("[STREAMING] Pipeline stopped")
        logger.info(f"Metrics: {self.metrics.summary()}")
    
    def get_metrics(self) -> Dict:
        """Get pipeline metrics"""
        return self.metrics.summary()


if __name__ == '__main__':
    # Test with mock data
    config = StreamingConfig(backend='mock', batch_size=5)
    pipeline = StreamingPipeline(config)
    
    pipeline.connect()
    
    # Process a few batches
    for i in range(3):
        result = pipeline.run_single_batch()
        if result:
            print(f"Batch {i+1}: {result['trains']} trains, {result['alerts']} alerts")
        time.sleep(1)
    
    pipeline.stop()
