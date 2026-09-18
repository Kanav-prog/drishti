# DRISHTI Load Testing Guide

## Overview

Load testing validates that the DRISHTI backend can handle expected traffic volumes and maintains performance under stress. This guide provides setup, execution, and analysis procedures.

## Prerequisites

### Install Locust

```bash
pip install locust websocket-client
```

### Verify Installation

```bash
locust --version
```

## Test Scenarios

### Scenario 1: Baseline Performance (Light Load)
- **Users**: 10
- **Spawn Rate**: 1 user/second
- **Duration**: 5 minutes
- **Purpose**: Establish baseline response times
- **Success Criteria**: P95 < 500ms, failure rate < 1%

### Scenario 2: Normal Load
- **Users**: 50
- **Spawn Rate**: 5 users/second
- **Duration**: 10 minutes
- **Purpose**: Validate steady-state performance
- **Success Criteria**: P95 < 1000ms, failure rate < 2%

### Scenario 3: Peak Load
- **Users**: 200
- **Spawn Rate**: 10 users/second
- **Duration**: 15 minutes
- **Purpose**: Test peak capacity
- **Success Criteria**: P95 < 2000ms, failure rate < 5%

### Scenario 4: Stress Test
- **Users**: 500
- **Spawn Rate**: 25 users/second
- **Duration**: 20 minutes
- **Purpose**: Find breaking point
- **Success Criteria**: System recovers after spike

### Scenario 5: WebSocket Load
- **Users**: 100 WebSocket connections
- **Duration**: 10 minutes
- **Purpose**: Test real-time functionality
- **Success Criteria**: All connections stable, < 5% disconnects

## Running Tests

### 1. Interactive Web UI

```bash
# Start Locust with web UI (default http://localhost:8089)
locust -f tests/load_test.py --host=http://localhost:8000

# Then:
# 1. Go to http://localhost:8089
# 2. Enter number of users (start with 10)
# 3. Enter spawn rate (1 user/sec)
# 4. Click "Start"
```

### 2. Headless Mode (Baseline)

```bash
locust -f tests/load_test.py \
    --host=http://localhost:8000 \
    -u 10 \
    -r 1 \
    -t 300 \
    --headless \
    --csv=baseline_test
```

### 3. Headless Mode (Normal Load)

```bash
locust -f tests/load_test.py \
    --host=http://localhost:8000 \
    -u 50 \
    -r 5 \
    -t 600 \
    --headless \
    --csv=normal_load_test
```

### 4. Headless Mode (Peak Load)

```bash
locust -f tests/load_test.py \
    --host=http://localhost:8000 \
    -u 200 \
    -r 10 \
    -t 900 \
    --headless \
    --csv=peak_load_test
```

### 5. Headless Mode (Stress Test)

```bash
locust -f tests/load_test.py \
    --host=http://localhost:8000 \
    -u 500 \
    -r 25 \
    -t 1200 \
    --headless \
    --csv=stress_test \
    --stop-timeout=120
```

### 6. Distributed Load Testing

For large-scale tests, run Locust in distributed mode:

```bash
# Terminal 1: Master node
locust -f tests/load_test.py \
    --host=http://localhost:8000 \
    --master

# Terminal 2-N: Worker nodes
locust -f tests/load_test.py \
    --host=http://localhost:8000 \
    --worker \
    --master-host=localhost

# Web UI: http://localhost:8089
```

## Understanding Results

### Response Time Metrics

- **Min**: Minimum response time in milliseconds
- **Max**: Maximum response time in milliseconds
- **P50**: 50th percentile (median)
- **P95**: 95th percentile (95% of requests faster than this)
- **P99**: 99th percentile (nearly all requests faster than this)
- **Avg**: Average response time

### Target Performance

```
Endpoint              Min (ms)   P50 (ms)   P95 (ms)   P99 (ms)   Max (ms)
─────────────────────────────────────────────────────────────────────────
/health               10         20         50         100        200
/api/v1/network       50         100        300        500        1000
/api/v1/cascades      100        200        500        1000       2000
/api/v1/alerts        100        200        500        1000       2000
/ws/alerts            N/A        N/A        N/A        N/A        N/A
```

### Interpreting Data

```bash
# Raw CSV output
cat baseline_test_stats.csv

# Shows columns:
# Type,Name,# requests,# failures,Median,Average,Min,Max,
# Content-Type,# 50ms,# 100ms,# 500ms,# 1000ms,# 10000ms,Total Requests,
# Total Failures,Failure Rate,%
```

## Sample Output Analysis

### Baseline Test Results
```
Scenario: 10 users for 5 minutes
Results:
  Total Requests: 4,500
  Total Failures: 10 (0.22%)
  Response Time P95: 150ms
  Response Time P99: 250ms
  
Analysis: ✅ Excellent - Well within targets
```

### Normal Load Results
```
Scenario: 50 users for 10 minutes
Results:
  Total Requests: 22,500
  Total Failures: 200 (0.89%)
  Response Time P95: 820ms
  Response Time P99: 1200ms
  
Analysis: ✅ Good - Acceptable performance
```

### Peak Load Results
```
Scenario: 200 users for 15 minutes
Results:
  Total Requests: 90,000
  Total Failures: 2,700 (3%)
  Response Time P95: 1800ms
  Response Time P99: 2500ms
  
Analysis: ⚠️  Marginal - Consider optimization
```

## Continuous Load Testing in CI/CD

### GitHub Actions Workflow

Create `.github/workflows/load-test.yml`:

```yaml
name: Load Testing

on:
  schedule:
    - cron: '0 2 * * *'  # Daily at 2 AM
  workflow_dispatch:

jobs:
  load-test:
    runs-on: ubuntu-latest
    
    services:
      drishti:
        image: ghcr.io/drishti-ai/drishti-backend:develop
        ports:
          - 8000:8000
      
      postgres:
        image: postgres:15
        env:
          POSTGRES_PASSWORD: password
        options: >-
          --health-cmd pg_isready
          --health-interval 10s

    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install locust
      
      - name: Run load test
        run: |
          locust -f tests/load_test.py \
            --host=http://localhost:8000 \
            -u 100 -r 10 -t 600 \
            --headless \
            --csv=load_test_results
      
      - name: Upload results
        uses: actions/upload-artifact@v3
        with:
          name: load-test-results
          path: load_test_results_*.csv
      
      - name: Comment on PR
        if: github.event_name == 'pull_request'
        uses: actions/github-script@v6
        with:
          script: |
            // Parse and comment with results
```

## Performance Optimization Tips

### 1. Database Optimization
```python
# Use connection pooling in FastAPI
from sqlalchemy.pool import NullPool
engine = create_engine(DATABASE_URL, poolclass=NullPool)
```

### 2. Caching
```python
# Add Redis caching for cascades
@app.get("/api/v1/cascades")
async def get_cascades(cache: Redis = Depends(get_redis)):
    key = "cascades:all"
    cached = await cache.get(key)
    if cached:
        return json.loads(cached)
    # ... fetch and cache
```

### 3. Async Task Processing
```python
# Use background tasks for heavy operations
from fastapi import BackgroundTasks

@app.post("/api/v1/cascades")
async def create_cascade(data: CascadeData, bg_tasks: BackgroundTasks):
    cascade = await db.save_cascade(data)
    bg_tasks.add_task(process_cascade, cascade.id)
    return cascade
```

### 4. Connection Pooling
```python
# Configure proper pool size
SQLALCHEMY_ENGINE_OPTS = {
    "pool_size": 20,
    "max_overflow": 40,
    "pool_pre_ping": True,
    "pool_recycle": 3600,
}
```

### 5. Resource Limits
```python
# Set ulimits in deployment
ulimit -n 65536  # Open files
ulimit -u 4096   # Processes
```

## Monitoring During Load Test

### Real-time Monitoring

```bash
# Monitor system resources
watch -n 1 'top -b -n 1 | head -20'

# Monitor database connections
psql -c "SELECT count(*) FROM pg_stat_activity;"

# Monitor Redis memory
redis-cli INFO memory

# Monitor application logs
tail -f logs/app.log
```

### Application Metrics (Prometheus)

```bash
# Access metrics during test
curl http://localhost:8000/metrics

# Common metrics to watch:
# - http_requests_total
# - http_request_duration_seconds
# - db_connection_pool_size
# - redis_commands_duration_seconds
```

## Troubleshooting

### High Failure Rate

```
Issue: > 5% failures during baseline test
Causes:
  1. Application not started
  2. Database connectivity issue
  3. Memory exhausted
  4. Connection timeouts
  
Solutions:
  - Check app logs: tail -f logs/app.log
  - Verify database: psql -c "SELECT 1"
  - Check system resources: free -m, df -h
  - Increase request timeout: locust --request-timeout=60
```

### Response Time Spike

```
Issue: P95 suddenly increases
Causes:
  1. Garbage collection
  2. Database timeout or lock
  3. Network congestion
  4. Resource exhaustion
  
Solutions:
  - Check GC logs
  - Monitor database activity
  - Check network stats: netstat -s
  - Scale horizontally (add more servers)
```

### Connection Errors

```
Issue: "Connection refused" errors
Causes:
  1. Application crashed
  2. File descriptor limit exceeded
  3. Network issue
  
Solutions:
  - Restart application
  - Increase ulimits: ulimit -n 65536
  - Check network: ping, traceroute
```

## Best Practices

1. **Test in Staging**: Always run load tests in staging environment first
2. **Baseline First**: Establish baseline before making changes
3. **Monitor Continuously**: Watch system resources during tests
4. **Gradual Ramp-up**: Increase users gradually to identify breaking point
5. **Test Regularly**: Run tests after each deployment
6. **Document Results**: Keep historical results for comparison
7. **Automate Tests**: Integrate load testing into CI/CD pipeline
8. **Test Failure Scenarios**: Simulate database outages, network issues
9. **Cleanup**: Stop test and cleanup resources after completion

## Performance Targets by Deployment Size

### Development (Local)
- Max Users: 10
- Target P95: < 500ms
- Failure Rate: < 1%

### Staging (2 servers)
- Max Users: 100
- Target P95: < 1000ms
- Failure Rate: < 2%

### Production (10+ servers)
- Max Users: 1000+
- Target P95: < 1500ms
- Failure Rate: < 1%

## References

- [Locust Documentation](https://docs.locust.io/)
- [Load Testing Best Practices](https://www.nginx.com/blog/testing-performance-automated-load-testing/)
- [Performance Testing Strategy](https://www.atlassian.com/continuous-delivery/performance-testing)

## Next Steps

1. Run baseline test (10 users, 5 min)
2. Analyze results against targets
3. Optimize bottlenecks
4. Run normal load test (50 users, 10 min)
5. Schedule regular load testing
6. Integrate into CI/CD pipeline
