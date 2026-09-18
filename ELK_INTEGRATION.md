# ELK Stack Integration Guide

## Overview

This guide explains how to integrate the DRISHTI backend with the ELK (Elasticsearch, Logstash, Kibana) stack for centralized logging, monitoring, and observability.

## Quick Start

### 1. Start ELK Stack

```bash
# Create .env file with Elastic password
echo "ELASTIC_PASSWORD=YourSecurePasswordHere" > .env

# Start the ELK stack
docker-compose -f docker-compose.elk.yml up -d

# Verify all services are running
docker-compose -f docker-compose.elk.yml ps
```

### 2. Access Kibana Dashboard

```
http://localhost:5601

Username: elastic
Password: (from .env)
```

## Architecture

```
┌─────────────────────────────────────────────────────┐
│              DRISHTI Application                    │
│  (FastAPI, Background Tasks, WebSocket, etc.)      │
└────────────────┬────────────────────────────────────┘
                 │
        ┌────────▼────────┐
        │  JSON Logs      │
        │ (Python Logger) │
        └────────┬────────┘
                 │
        ┌────────▼──────────────────────┐
        │    Logstash (Port 5000)       │
        │  - Parse JSON logs            │
        │  - Extract fields             │
        │  - Add metadata               │
        └────────┬──────────────────────┘
                 │
        ┌────────▼──────────────────────┐
        │     Elasticsearch             │
        │  - Index logs                 │
        │  - drishti-logs-YYYY.MM.dd    │
        │  - drishti-errors-YYYY.MM.dd  │
        └────────┬──────────────────────┘
                 │
        ┌────────▼──────────────────────┐
        │       Kibana                  │
        │  - Visualize logs             │
        │  - Create dashboards          │
        │  - Set up alerts              │
        └───────────────────────────────┘
```

## Integration with FastAPI

### 1. Configure Python Logging

Update `backend/config.py`:

```python
import logging
import json
from pythonjsonlogger import jsonlogger

# JSON Formatter for ELK
def setup_logging():
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    
    # JSON handler for ELK
    elk_handler = logging.handlers.SysLogHandler(
        address=('localhost', 5000),
        facility=logging.handlers.SysLogHandler.LOG_LOCAL0
    )
    
    json_formatter = jsonlogger.JsonFormatter(
        '%(timestamp)s %(level)s %(name)s %(message)s'
    )
    elk_handler.setFormatter(json_formatter)
    logger.addHandler(elk_handler)
    
    # Console handler for debugging
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(
        logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    )
    logger.addHandler(console_handler)
    
    return logger
```

### 2. Use Structured Logging in Application

```python
import logging
from pythonjsonlogger import jsonlogger

logger = logging.getLogger(__name__)

# Structured logging
logger.info(
    "Cascade detected",
    extra={
        "cascade_id": cascade_id,
        "severity": "HIGH",
        "affected_stations": len(affected),
        "timestamp": datetime.now().isoformat(),
        "service": "cascade_engine"
    }
)
```

### 3. Add APM Instrumentation

```bash
pip install elastic-apm
```

In FastAPI app initialization:

```python
from elasticapm.contrib.starlette import make_apm_client, ElasticAPM

app = FastAPI()

apm_client = make_apm_client({
    'SERVICE_NAME': 'drishti-backend',
    'SERVER_URL': 'http://localhost:8200',
    'ENVIRONMENT': 'production',
    'DEBUG': False
})

app.add_middleware(ElasticAPM, client=apm_client)
```

## Kibana Dashboard Setup

### 1. Create Index Patterns

```
Management > Stack Management > Index Patterns > Create Index Pattern

Pattern: drishti-logs-*
Time field: @timestamp
```

### 2. Create Discover View

```
Kibana > Discover
Select: drishti-logs-* index
Filter by: severity = "ERROR"
Fields: @timestamp, level, host, message
```

### 3. Create Dashboard

```
Kibana > Dashboard > Create New Dashboard
Add visualizations:
- Error Count Over Time
- Log Volume by Service
- Top Error Messages
- Response Time Trends
```

### 4. Set Up Alerts

```
Kibana > Alerting > Create Alert
Condition: When error count > 10 in last 5 minutes
Action: Send to Slack webhook
```

## Log Levels and Indexing

### Error Logs
- **Index**: `drishti-errors-YYYY.MM.dd`
- **Severity**: ERROR, CRITICAL
- **Example**: Database connection failures, API errors

### Warning Logs
- **Index**: `drishti-logs-YYYY.MM.dd` (tagged: warning)
- **Severity**: WARNING
- **Example**: Deprecated API usage, slow queries

### Info Logs
- **Index**: `drishti-logs-YYYY.MM.dd`
- **Severity**: INFO
- **Example**: Request start, task completed

### Debug Logs
- **Index**: `drishti-logs-YYYY.MM.dd` (only in development)
- **Severity**: DEBUG
- **Example**: Variable values, loop iterations

## Common Kibana Queries

### Find All Errors in Last Hour
```
severity: ERROR AND @timestamp: [now-1h TO now]
```

### Find Slow Requests
```
http.response_time > 1000 AND service.name: "drishti-backend"
```

### Find Cascade Engine Errors
```
service: "cascade_engine" AND level: "ERROR"
```

### Find Failed WebSocket Connections
```
message: "Connection failed" AND session.id: *
```

## Performance Optimization

### 1. Index Lifecycle Management (ILM)

```bash
# Create ILM policy
PUT _ilm/policy/drishti-logs-policy
{
  "policy": "drishti-logs-policy",
  "phases": {
    "hot": {
      "min_age": "0d",
      "actions": {
        "rollover": {
          "max_size": "50GB",
          "max_age": "1d"
        }
      }
    },
    "delete": {
      "min_age": "30d",
      "actions": {
        "delete": {}
      }
    }
  }
}
```

### 2. Logstash Performance Tuning

```conf
# Increase batch size for better throughput
output {
  elasticsearch {
    hosts => ["elasticsearch:9200"]
    bulk_max_size => 5000
    flush_interval => 5
  }
}
```

### 3. Elasticsearch Tuning

```yaml
# elasticsearch.yml
thread_pool.write.queue_size: 2000
indices.memory.index_buffer_size: 50%
```

## Troubleshooting

### 1. Logs Not Appearing in Kibana

```bash
# Check Logstash is receiving logs
docker logs drishti-logstash | tail -20

# Check index existence
curl -u elastic:password http://localhost:9200/_cat/indices

# Check if logs were indexed
curl -u elastic:password http://localhost:9200/drishti-logs-*/_count
```

### 2. High Elasticsearch CPU

```bash
# Reduce shard count
PUT /drishti-logs-*/_settings
{
  "index": {
    "refresh_interval": "30s"
  }
}
```

### 3. Kibana Performance Issues

```bash
# Clear saved objects cache
curl -X DELETE http://localhost:5601/api/saved_objects/index-pattern/*

# Increase Kibana memory
export NODE_OPTIONS="--max-old-space-size=2048"
```

## Monitoring ELK Stack Health

### 1. Check Elasticsearch Status

```bash
curl -u elastic:password http://localhost:9200/_cluster/health
```

### 2. Monitor Logstash Throughput

```bash
curl http://localhost:9600/_node/stats/pipelines
```

### 3. Check Kibana Status

```bash
curl http://localhost:5601/api/status
```

## Backup and Recovery

### 1. Create Elasticsearch Snapshot Repository

```bash
PUT /_snapshot/backup
{
  "type": "fs",
  "settings": {
    "location": "/mnt/backups/elasticsearch"
  }
}
```

### 2. Create Snapshots

```bash
PUT /_snapshot/backup/drishti-logs-backup-1
{
  "indices": "drishti-logs-*",
  "ignore_unavailable": true,
  "include_global_state": true
}
```

## Integration with Monitoring

### Grafana Integration

```
Data Source: Elasticsearch
URL: http://localhost:9200
Auth: elastic / password
Index: drishti-*
```

### Prometheus Integration

```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'elasticsearch'
    static_configs:
      - targets: ['localhost:9200']
  - job_name: 'kibana'
    static_configs:
      - targets: ['localhost:5601']
```

## Next Steps

1. ✅ Deploy ELK stack
2. ✅ Configure FastAPI logging
3. ✅ Create Kibana dashboards
4. ✅ Set up alerting
5. ⏳ Configure backup strategy
6. ⏳ Optimize index management
7. ⏳ Integrate with monitoring systems
