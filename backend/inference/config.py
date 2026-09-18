"""
DRISHTI Streaming Configuration
Configuration for real-time pipeline: Kafka, Redis, batch sizes, timeouts
"""

import os
from dataclasses import dataclass
from typing import Literal

@dataclass
class StreamingConfig:
    """Configuration for real-time streaming pipeline"""
    
    # Streaming backend: 'kafka', 'redis', or 'mock'
    backend: Literal['kafka', 'redis', 'mock'] = os.getenv('STREAMING_BACKEND', 'redis')
    
    # Kafka configuration
    kafka_brokers: list = None
    kafka_topic: str = os.getenv('KAFKA_TOPIC', 'ntes-train-updates')
    kafka_group_id: str = os.getenv('KAFKA_GROUP_ID', 'drishti-inference')
    kafka_timeout_ms: int = 5000
    
    # Redis configuration
    redis_host: str = os.getenv('REDIS_HOST', 'localhost')
    redis_port: int = int(os.getenv('REDIS_PORT', 6379))
    redis_stream_key: str = 'ntes:train:updates'
    redis_consumer_group: str = 'drishti-inference'
    redis_timeout_ms: int = 5000
    
    # Batch configuration
    batch_size: int = int(os.getenv('BATCH_SIZE', 100))  # Process 100 trains at a time
    batch_timeout_sec: int = int(os.getenv('BATCH_TIMEOUT', 60))  # Max wait for batch
    
    # Inference configuration
    max_workers: int = int(os.getenv('MAX_WORKERS', 4))  # Parallel inference threads
    inference_timeout_sec: float = 30.0
    
    # Alert configuration
    alert_enabled: bool = True
    audit_log_file: str = os.getenv('AUDIT_LOG_FILE', 'drishti_alerts.jsonl')
    
    # Output configuration
    results_queue_file: str = 'streaming_results.jsonl'  # Results queue for API server
    metrics_enabled: bool = True
    
    # Logging
    log_level: str = os.getenv('LOG_LEVEL', 'INFO')
    log_file: str = os.getenv('LOG_FILE', 'streaming.log')
    
    def __post_init__(self):
        """Validate configuration after initialization"""
        if self.kafka_brokers is None:
            self.kafka_brokers = os.getenv('KAFKA_BROKERS', 'localhost:9092').split(',')
        
        if self.backend not in ['kafka', 'redis', 'mock']:
            raise ValueError(f"Unsupported backend: {self.backend}")
        
        if self.batch_size <= 0:
            raise ValueError(f"Batch size must be > 0, got {self.batch_size}")
        
        if self.max_workers <= 0:
            raise ValueError(f"Max workers must be > 0, got {self.max_workers}")


@dataclass
class MetricsCollector:
    """Collect streaming pipeline metrics"""
    
    total_batches_processed: int = 0
    total_trains_processed: int = 0
    total_alerts_generated: int = 0
    alerts_by_severity: dict = None
    avg_batch_latency_ms: float = 0.0
    errors_encountered: int = 0
    
    def __post_init__(self):
        if self.alerts_by_severity is None:
            self.alerts_by_severity = {'CRITICAL': 0, 'HIGH': 0, 'MEDIUM': 0, 'LOW': 0}
    
    def record_batch(self, train_count: int, latency_ms: float, alerts: int):
        """Record metrics for a batch"""
        self.total_batches_processed += 1
        self.total_trains_processed += train_count
        self.total_alerts_generated += alerts
        
        # Update rolling average latency
        if self.avg_batch_latency_ms == 0:
            self.avg_batch_latency_ms = latency_ms
        else:
            self.avg_batch_latency_ms = (
                0.9 * self.avg_batch_latency_ms + 0.1 * latency_ms
            )
    
    def record_alert(self, severity: str):
        """Record alert by severity"""
        if severity in self.alerts_by_severity:
            self.alerts_by_severity[severity] += 1
    
    def record_error(self):
        """Record an error"""
        self.errors_encountered += 1
    
    def summary(self) -> dict:
        """Get metrics summary"""
        return {
            'total_batches': self.total_batches_processed,
            'total_trains': self.total_trains_processed,
            'total_alerts': self.total_alerts_generated,
            'alerts_breakdown': self.alerts_by_severity,
            'avg_batch_latency_ms': round(self.avg_batch_latency_ms, 2),
            'errors': self.errors_encountered,
        }
