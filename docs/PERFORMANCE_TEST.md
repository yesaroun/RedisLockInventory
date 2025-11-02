# 성능 테스트 계획서

## 🎯 테스트 목표

블랙프라이데이 시나리오(1초 1000명 동시 접속, 100개 한정 판매)를 시뮬레이션하여 시스템의 성능 한계와 병목 지점을 파악합니다.

---

## 📊 주요 성능 지표 (KPI)

| 지표 | 설명 | 목표값 | 측정 방법 |
|------|------|--------|-----------|
| **TPS** | 초당 처리 트랜잭션 | v1: 100, v4: 1000+ | Locust/JMeter |
| **Response Time** | 응답 시간 | P50 < 100ms, P99 < 500ms | Percentile 분석 |
| **Error Rate** | 에러 발생률 | < 0.1% | 4xx, 5xx 응답 비율 |
| **Concurrency** | 동시 사용자 수 | 1000명 | Active connections |
| **Lock Contention** | 락 경합률 | < 30% | Redis 메트릭 |
| **Accuracy** | 재고 정확도 | 100% | 실제 vs 예상 재고 |

---

## 🧪 테스트 도구

### 1. Locust (Python 기반)

```python
# load_tests/locustfile.py
from locust import HttpUser, task, between
import random

class BlackFridayUser(HttpUser):
    wait_time = between(0.1, 0.5)  # 0.1~0.5초 대기

    def on_start(self):
        """사용자 세션 시작 시 로그인"""
        response = self.client.post("/login", json={
            "username": f"user_{random.randint(1, 10000)}",
            "password": "password123"
        })
        if response.status_code == 200:
            self.token = response.json()["access_token"]
            self.client.headers.update({
                "Authorization": f"Bearer {self.token}"
            })

    @task(3)
    def check_inventory(self):
        """재고 조회 (30% 비중)"""
        product_id = random.randint(1, 10)
        self.client.get(f"/inventory/{product_id}")

    @task(7)
    def purchase_item(self):
        """구매 시도 (70% 비중)"""
        product_id = random.randint(1, 10)
        quantity = random.randint(1, 3)
        self.client.post(
            f"/purchase/{product_id}",
            json={"quantity": quantity}
        )
```

### 2. 실행 명령어

```bash
# Web UI 모드
uv run locust -f load_tests/locustfile.py \
    --host http://localhost:8000

# Headless 모드 (CI/CD용)
uv run locust -f load_tests/locustfile.py \
    --host http://localhost:8000 \
    --headless \
    --users 1000 \
    --spawn-rate 50 \
    --run-time 60s \
    --csv=results/test_$(date +%Y%m%d_%H%M%S)
```

### 3. pytest-asyncio (동시성 테스트)

```python
# tests/test_concurrency.py
import pytest
import asyncio
import aiohttp

@pytest.mark.asyncio
async def test_concurrent_purchases():
    """100명이 동시에 1개씩 구매"""

    async def purchase_one(session, user_id):
        headers = {"Authorization": f"Bearer {tokens[user_id]}"}
        async with session.post(
            f"http://localhost:8000/purchase/1",
            json={"quantity": 1},
            headers=headers
        ) as response:
            return response.status

    # 100명 동시 요청
    async with aiohttp.ClientSession() as session:
        tasks = [
            purchase_one(session, i)
            for i in range(100)
        ]
        results = await asyncio.gather(*tasks)

    # 검증: 정확히 100개 판매
    success_count = results.count(200)
    assert success_count == 100
    assert results.count(400) == 0  # 재고 부족 없음
```

---

## 📈 테스트 시나리오

### Scenario 1: Baseline Test (기준선 설정)

```yaml
name: Baseline Performance Test
description: 단일 사용자로 시스템 기본 성능 측정
steps:
  - users: 1
    duration: 60s
    requests:
      - GET /inventory/1: 50%
      - POST /purchase/1: 50%
expected:
  - response_time_p99: < 50ms
  - error_rate: 0%
```

### Scenario 2: Load Test (부하 테스트)

```yaml
name: Black Friday Load Test
description: 점진적 부하 증가
steps:
  - users: 100
    duration: 120s
    ramp_up: 30s
  - users: 500
    duration: 120s
    ramp_up: 30s
  - users: 1000
    duration: 300s
    ramp_up: 60s
expected:
  - tps: > 100
  - response_time_p99: < 500ms
  - error_rate: < 1%
```

### Scenario 3: Spike Test (스파이크 테스트)

```yaml
name: Flash Sale Spike Test
description: 갑작스러운 트래픽 급증
steps:
  - users: 10
    duration: 30s
  - users: 1000  # 갑자기 증가
    duration: 60s
    ramp_up: 5s
  - users: 10
    duration: 30s
expected:
  - system_recovery_time: < 10s
  - no_system_crash: true
```

### Scenario 4: Stress Test (한계 테스트)

```yaml
name: System Breaking Point Test
description: 시스템 한계점 파악
steps:
  - start_users: 100
    increment: 100
    increment_interval: 60s
    max_users: 5000
expected:
  - identify_breaking_point: true
  - graceful_degradation: true
```

### Scenario 5: Soak Test (장시간 테스트)

```yaml
name: Long Duration Test
description: 메모리 누수, 성능 저하 확인
steps:
  - users: 500
    duration: 3600s  # 1시간
expected:
  - memory_leak: false
  - performance_degradation: < 10%
  - error_rate_stable: true
```

---

## 🔧 테스트 환경 구성

### 하드웨어 사양

```yaml
Test Server:
  CPU: 8 cores (Intel Xeon)
  RAM: 16GB
  Disk: SSD 100GB
  Network: 1Gbps

Redis Server:
  CPU: 4 cores
  RAM: 8GB (Redis 전용)
  Persistence: AOF enabled

Load Generator:
  CPU: 4 cores
  RAM: 8GB
  Location: Same network (< 1ms latency)
```

### Docker Compose 테스트 환경

```yaml
# docker-compose.test.yml
version: '3.8'

services:
  app:
    build: .
    environment:
      - WORKERS=4
      - LOG_LEVEL=WARNING
    deploy:
      resources:
        limits:
          cpus: '4'
          memory: 4G

  redis:
    image: redis:7-alpine
    command: redis-server --maxmemory 2gb --maxmemory-policy allkeys-lru
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 2G

  locust:
    image: locustio/locust
    volumes:
      - ./load_tests:/mnt/locust
    command: -f /mnt/locust/locustfile.py --host http://app:8000
```

---

## 📉 성능 메트릭 수집

### 1. Application Metrics

```python
# app/metrics.py
from prometheus_client import Counter, Histogram, Gauge

# 요청 카운터
request_count = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status']
)

# 응답 시간 히스토그램
request_duration = Histogram(
    'http_request_duration_seconds',
    'HTTP request duration',
    ['method', 'endpoint']
)

# 현재 재고
current_stock = Gauge(
    'inventory_stock_current',
    'Current stock level',
    ['product_id']
)

# 락 메트릭
lock_acquired = Counter('lock_acquired_total', 'Locks acquired')
lock_failed = Counter('lock_failed_total', 'Lock failures')
lock_wait_time = Histogram('lock_wait_seconds', 'Lock wait time')
```

### 2. Redis Metrics

```bash
# Redis 모니터링 명령어
redis-cli --stat  # 실시간 통계

# 주요 메트릭
redis-cli INFO stats
# - total_connections_received: 총 연결 수
# - instantaneous_ops_per_sec: 초당 명령 처리
# - rejected_connections: 거부된 연결

redis-cli INFO memory
# - used_memory: 사용 메모리
# - mem_fragmentation_ratio: 메모리 단편화

# 락 관련 메트릭
redis-cli --scan --pattern "lock:*" | wc -l  # 활성 락 수
```

### 3. System Metrics

```bash
# CPU 사용률
top -b -n 1 | grep "Cpu(s)"

# 메모리 사용률
free -h

# 네트워크 통계
netstat -s

# 디스크 I/O
iostat -x 1

# 프로세스별 리소스
ps aux | grep python
```

---

## 📊 결과 분석 및 리포트

### 1. 성능 테스트 결과 템플릿

```markdown
## Test Report: [Test Name]
- Date: 2024-01-01
- Version: v1.0
- Duration: 60 seconds
- Users: 1000 concurrent

### Summary
- ✅ TPS: 150 (Target: 100)
- ⚠️ P99 Response Time: 550ms (Target: 500ms)
- ✅ Error Rate: 0.05% (Target: < 0.1%)
- ✅ Inventory Accuracy: 100%

### Detailed Results
| Metric | Value | Target | Status |
|--------|-------|--------|--------|
| Requests/sec | 150 | 100 | ✅ Pass |
| P50 Latency | 80ms | 100ms | ✅ Pass |
| P95 Latency | 320ms | 400ms | ✅ Pass |
| P99 Latency | 550ms | 500ms | ⚠️ Warning |

### Bottlenecks Identified
1. Redis lock contention at > 800 users
2. Database write queue buildup
3. Connection pool exhaustion

### Recommendations
1. Increase Redis connection pool size
2. Implement write batching for purchases
3. Add read replicas for inventory checks
```

### 2. 그래프 생성 스크립트

```python
# scripts/analyze_results.py
import pandas as pd
import matplotlib.pyplot as plt

def analyze_locust_results(csv_file):
    """Locust 결과 CSV 분석 및 시각화"""

    # 데이터 로드
    stats = pd.read_csv(f"{csv_file}_stats.csv")

    # 시간대별 TPS 그래프
    plt.figure(figsize=(12, 6))

    plt.subplot(2, 2, 1)
    plt.plot(stats['Timestamp'], stats['Requests/s'])
    plt.title('Throughput Over Time')
    plt.xlabel('Time')
    plt.ylabel('Requests/sec')

    # 응답시간 분포
    plt.subplot(2, 2, 2)
    plt.hist(stats['95%'], bins=50, alpha=0.7, label='P95')
    plt.hist(stats['99%'], bins=50, alpha=0.7, label='P99')
    plt.title('Response Time Distribution')
    plt.xlabel('Response Time (ms)')
    plt.ylabel('Frequency')
    plt.legend()

    # 에러율 추이
    plt.subplot(2, 2, 3)
    plt.plot(stats['Timestamp'], stats['Failures/s'])
    plt.title('Error Rate Over Time')
    plt.xlabel('Time')
    plt.ylabel('Errors/sec')

    # 동시 사용자 수
    plt.subplot(2, 2, 4)
    plt.plot(stats['Timestamp'], stats['User Count'])
    plt.title('Concurrent Users')
    plt.xlabel('Time')
    plt.ylabel('Users')

    plt.tight_layout()
    plt.savefig('performance_report.png')
```

---

## 🚀 성능 최적화 체크리스트

### Application Level

- [ ] Connection pooling 구성
- [ ] 비동기 처리 최적화
- [ ] 불필요한 로깅 제거
- [ ] JSON serialization 최적화
- [ ] Prepared statements 사용

### Redis Level

- [ ] Pipeline/Transaction 사용
- [ ] Lua script 최적화
- [ ] 적절한 maxclients 설정
- [ ] TCP keepalive 설정
- [ ] Persistence 설정 조정

### Database Level

- [ ] Index 최적화
- [ ] Query 최적화
- [ ] Connection pool 조정
- [ ] Write batching
- [ ] Read replica 구성

### Infrastructure Level

- [ ] CPU governor 성능 모드
- [ ] Network buffer 크기 조정
- [ ] File descriptor limit 증가
- [ ] Swap 비활성화
- [ ] THP (Transparent Huge Pages) 비활성화

---

## 🔍 병목 지점 진단

### 1. APM 도구 활용

```python
# New Relic, DataDog, AppDynamics 통합
from newrelic import agent

@agent.function_trace()
async def purchase_with_lock(product_id: int):
    # 자동으로 성능 추적
    pass
```

### 2. 프로파일링

```bash
# cProfile 실행
python -m cProfile -o profile.stats app/main.py

# 결과 분석
python -c "import pstats; p = pstats.Stats('profile.stats'); p.sort_stats('cumulative').print_stats(20)"
```

### 3. 병목 지점별 대응

| 병목 지점 | 증상 | 해결 방법 |
|-----------|------|-----------|
| CPU | High CPU usage | 코드 최적화, 스케일 아웃 |
| Memory | OOM, Swap 사용 | 메모리 누수 수정, 캐시 정리 |
| Network | High latency | Connection pool, Keep-alive |
| Disk I/O | Slow writes | SSD 사용, 비동기 쓰기 |
| Lock contention | 대기 시간 증가 | 락 세분화, 샤딩 |

---

## 📝 테스트 자동화

### GitHub Actions CI/CD

```yaml
# .github/workflows/performance-test.yml
name: Performance Test

on:
  schedule:
    - cron: '0 2 * * *'  # 매일 새벽 2시

jobs:
  performance-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2

      - name: Setup environment
        run: |
          docker-compose -f docker-compose.test.yml up -d
          sleep 10

      - name: Run performance test
        run: |
          docker run --rm \
            --network host \
            -v $PWD/load_tests:/mnt/locust \
            locustio/locust \
            -f /mnt/locust/locustfile.py \
            --host http://localhost:8000 \
            --headless \
            --users 100 \
            --spawn-rate 10 \
            --run-time 60s \
            --csv=results/test

      - name: Analyze results
        run: python scripts/analyze_results.py results/test

      - name: Upload artifacts
        uses: actions/upload-artifact@v2
        with:
          name: performance-results
          path: results/
```

---

## 📚 참고 자료

- [Locust Documentation](https://docs.locust.io/)
- [Redis Benchmarking](https://redis.io/docs/management/optimization/benchmarks/)
- [FastAPI Performance Tips](https://fastapi.tiangolo.com/deployment/concepts/)
- [High Performance Browser Networking](https://hpbn.co/)