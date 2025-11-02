# 문제 해결 가이드

## 🚨 긴급 대응 가이드

### 시스템 다운 시 복구 절차

```bash
# 1. 서비스 상태 확인
docker-compose ps
systemctl status redis
ps aux | grep python

# 2. 긴급 재시작
docker-compose restart
# 또는
systemctl restart redis
uvicorn app.main:app --reload

# 3. 로그 확인
docker-compose logs --tail=100 app
journalctl -u redis -n 100
tail -f /var/log/app/error.log

# 4. 헬스체크
curl http://localhost:8000/health
redis-cli ping
```

---

## 🔴 재고 관련 문제

### Problem 1: 재고 불일치

**증상**: Redis 재고와 실제 판매량이 맞지 않음

**진단**:
```sql
-- SQLite에서 실제 재고 계산
SELECT
    p.id,
    p.name,
    p.initial_stock,
    COALESCE(SUM(pu.quantity), 0) as total_sold,
    p.initial_stock - COALESCE(SUM(pu.quantity), 0) as expected_stock
FROM products p
LEFT JOIN purchases pu ON p.id = pu.product_id
GROUP BY p.id;
```

```bash
# Redis 재고 확인
redis-cli GET stock:1
```

**해결책**:
```python
# scripts/fix_inventory_mismatch.py
async def fix_inventory_mismatch(product_id: int):
    """재고 불일치 수정"""

    # 1. DB에서 정확한 재고 계산
    actual_stock = await calculate_actual_stock(product_id)

    # 2. 락 획득
    lock = await acquire_lock(f"lock:stock:{product_id}")
    if not lock:
        raise Exception("Failed to acquire lock")

    try:
        # 3. Redis 재고 수정
        await redis.set(f"stock:{product_id}", actual_stock)

        # 4. 감사 로그 기록
        await log_inventory_fix(product_id, actual_stock)
    finally:
        await release_lock(lock)
```

### Problem 2: 음수 재고 발생

**증상**: Redis에 음수 값 저장됨

**원인**:
- Lua 스크립트 없이 DECRBY 직접 사용
- 재고 체크 없이 차감

**해결책**:
```lua
-- 원자적 재고 차감 스크립트
local current = redis.call('GET', KEYS[1])
if not current then
    return {err = "Stock not found"}
end

current = tonumber(current)
local quantity = tonumber(ARGV[1])

if current < quantity then
    return {err = "Insufficient stock"}
end

redis.call('DECRBY', KEYS[1], quantity)
return {ok = current - quantity}
```

### Problem 3: 재고 초과 판매

**증상**: 100개 재고에 101개 이상 판매됨

**진단**:
```python
# 구매 이력 분석
async def analyze_overselling():
    # 시간대별 구매 패턴 분석
    purchases = await db.execute("""
        SELECT
            product_id,
            COUNT(*) as purchase_count,
            SUM(quantity) as total_quantity,
            MIN(purchased_at) as first_purchase,
            MAX(purchased_at) as last_purchase
        FROM purchases
        WHERE product_id = ?
        GROUP BY product_id
    """, [product_id])

    # 동시 구매 감지
    concurrent_purchases = await detect_concurrent_purchases()
    return concurrent_purchases
```

**해결책**:
- 비관적 락 타임아웃 증가
- 락 재시도 로직 강화
- 트랜잭션 격리 수준 조정

---

## 🔒 락 관련 문제

### Problem 4: 데드락 발생

**증상**: 모든 요청이 락 대기 상태

**진단**:
```bash
# 활성 락 확인
redis-cli --scan --pattern "lock:*"

# 락 TTL 확인
redis-cli TTL lock:stock:1

# 락 소유자 확인
redis-cli GET lock:stock:1
```

**해결책**:
```python
# 데드락 감지 및 해제
async def detect_and_break_deadlock():
    """데드락 감지 및 강제 해제"""

    # 1. 오래된 락 찾기
    locks = await redis.scan_iter("lock:*")
    for lock_key in locks:
        ttl = await redis.ttl(lock_key)

        # TTL이 없거나 너무 긴 락
        if ttl == -1 or ttl > MAX_LOCK_TTL:
            # 강제 해제
            await redis.delete(lock_key)
            logger.warning(f"Force released lock: {lock_key}")

    # 2. 순환 대기 감지 (다중 락 사용 시)
    await detect_circular_wait()
```

### Problem 5: 락 릴리즈 실패

**증상**: 락이 해제되지 않고 TTL 만료까지 대기

**원인**:
- 프로세스 크래시
- 네트워크 단절
- 잘못된 lock_id

**해결책**:
```python
# Context manager로 안전한 락 관리
class SafeLock:
    async def __aenter__(self):
        self.lock = await acquire_lock(self.resource)
        if not self.lock:
            raise LockAcquisitionError()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        try:
            await release_lock(self.lock)
        except Exception as e:
            logger.error(f"Failed to release lock: {e}")
            # TTL에 의존
```

### Problem 6: 락 경합 심화

**증상**: 대부분의 요청이 409 Conflict 반환

**진단**:
```python
# 락 메트릭 수집
async def collect_lock_metrics():
    metrics = {
        "acquisition_attempts": 0,
        "acquisition_success": 0,
        "average_wait_time": 0,
        "max_wait_time": 0
    }

    # Redis에서 메트릭 조회
    metrics = await redis.hgetall("metrics:lock:stock:1")
    success_rate = metrics["acquisition_success"] / metrics["acquisition_attempts"]

    if success_rate < 0.5:
        logger.warning("High lock contention detected")
```

**해결책**:
- 락 세분화 (product별 → SKU별)
- 락 홀딩 시간 최소화
- 읽기/쓰기 락 분리
- 샤딩 도입

---

## 🌐 네트워크 관련 문제

### Problem 7: Redis 연결 실패

**증상**: `ConnectionError: Error connecting to Redis`

**진단**:
```bash
# Redis 접속 테스트
redis-cli -h localhost -p 6379 ping

# 네트워크 연결 확인
telnet localhost 6379
nc -zv localhost 6379

# 방화벽 확인
sudo iptables -L | grep 6379
```

**해결책**:
```python
# 연결 재시도 로직
class ResilientRedisClient:
    def __init__(self, **kwargs):
        self.pool = redis.ConnectionPool(
            max_connections=50,
            socket_keepalive=True,
            socket_keepalive_options={
                1: 1,  # TCP_KEEPIDLE
                2: 1,  # TCP_KEEPINTVL
                3: 5,  # TCP_KEEPCNT
            },
            **kwargs
        )

    async def execute_with_retry(self, func, *args, **kwargs):
        for attempt in range(3):
            try:
                return await func(*args, **kwargs)
            except redis.ConnectionError:
                if attempt == 2:
                    raise
                await asyncio.sleep(2 ** attempt)
```

### Problem 8: 네트워크 지연

**증상**: Redis 명령 응답 시간 증가

**진단**:
```bash
# Redis 응답 시간 측정
redis-cli --latency
redis-cli --latency-history

# 네트워크 지연 확인
ping -c 10 redis-server
traceroute redis-server
```

**해결책**:
- Connection pooling 최적화
- Pipeline 사용
- Local Redis 캐시

---

## 🔐 인증/인가 문제

### Problem 9: JWT 토큰 만료

**증상**: 401 Unauthorized 응답

**진단**:
```python
# JWT 디코딩 및 검증
import jwt
from datetime import datetime

def debug_jwt(token: str):
    try:
        # 서명 검증 없이 디코딩
        payload = jwt.decode(token, options={"verify_signature": False})
        exp = datetime.fromtimestamp(payload.get('exp', 0))
        print(f"Token expires at: {exp}")
        print(f"Current time: {datetime.now()}")
        print(f"Expired: {exp < datetime.now()}")
    except Exception as e:
        print(f"Invalid token: {e}")
```

**해결책**:
- 토큰 자동 갱신
- Refresh token 구현
- 토큰 만료 시간 조정

### Problem 10: 비밀번호 해싱 느림

**증상**: 로그인 응답 시간 > 1초

**진단**:
```python
import time
import bcrypt

# bcrypt cost factor 테스트
for cost in [10, 12, 14, 16]:
    start = time.time()
    bcrypt.hashpw(b"password", bcrypt.gensalt(cost))
    print(f"Cost {cost}: {time.time() - start:.2f}s")
```

**해결책**:
- Cost factor 조정 (12 권장)
- 비동기 처리
- 캐싱 고려

---

## 🐛 디버깅 도구

### 1. Redis 모니터링

```bash
# 실시간 명령 모니터링
redis-cli monitor

# 슬로우 쿼리 확인
redis-cli SLOWLOG GET 10

# 메모리 분석
redis-cli --bigkeys
redis-cli MEMORY DOCTOR
```

### 2. Python 프로파일링

```python
# cProfile 사용
import cProfile
import pstats

profiler = cProfile.Profile()
profiler.enable()

# 측정할 코드
await purchase_with_lock(product_id)

profiler.disable()
stats = pstats.Stats(profiler)
stats.sort_stats('cumulative')
stats.print_stats(10)
```

### 3. 로그 분석

```python
# 구조화된 로깅
import structlog

logger = structlog.get_logger()

logger.info(
    "purchase_attempted",
    user_id=user_id,
    product_id=product_id,
    quantity=quantity,
    timestamp=datetime.now().isoformat()
)

# 로그 집계
grep "purchase_attempted" app.log | \
    jq '.product_id' | \
    sort | uniq -c | sort -rn
```

---

## 📊 모니터링 체크리스트

### 애플리케이션 레벨

- [ ] API 응답 시간 (P50, P95, P99)
- [ ] 에러율 (4xx, 5xx)
- [ ] 활성 연결 수
- [ ] 메모리 사용량
- [ ] CPU 사용률

### Redis 레벨

- [ ] 명령 처리량 (ops/sec)
- [ ] 메모리 사용률
- [ ] 연결 수
- [ ] 캐시 히트율
- [ ] 느린 쿼리

### 시스템 레벨

- [ ] 디스크 I/O
- [ ] 네트워크 트래픽
- [ ] 시스템 로드
- [ ] 파일 디스크립터
- [ ] TCP 연결 상태

---

## 🚑 복구 스크립트

### 재고 전체 동기화

```python
# scripts/sync_all_inventory.py
async def sync_all_inventory():
    """모든 상품 재고 동기화"""

    products = await db.fetch_all("SELECT id FROM products")

    for product in products:
        # 실제 재고 계산
        actual = await calculate_actual_stock(product.id)

        # Redis 업데이트
        await redis.set(f"stock:{product.id}", actual)

        logger.info(f"Synced product {product.id}: {actual}")
```

### 락 전체 초기화

```bash
#!/bin/bash
# scripts/reset_all_locks.sh

echo "Clearing all locks..."
redis-cli --scan --pattern "lock:*" | xargs redis-cli DEL
echo "All locks cleared"
```

### 데이터베이스 복구

```sql
-- 구매 이력 정합성 검사
SELECT
    p.id,
    p.name,
    COUNT(DISTINCT pu.id) as purchase_count,
    SUM(pu.quantity) as total_sold,
    p.initial_stock - SUM(pu.quantity) as remaining
FROM products p
LEFT JOIN purchases pu ON p.id = pu.product_id
GROUP BY p.id
HAVING remaining < 0;  -- 문제 있는 상품만

-- 중복 구매 제거
DELETE FROM purchases
WHERE id NOT IN (
    SELECT MIN(id)
    FROM purchases
    GROUP BY user_id, product_id, purchased_at
);
```

---

## 📞 에스컬레이션 가이드

### Level 1: 자동 복구
- 자동 재시작
- 캐시 클리어
- 커넥션 재연결

### Level 2: 운영팀 개입
- 수동 재시작
- 로그 분석
- 설정 조정

### Level 3: 개발팀 호출
- 코드 수정 필요
- 데이터 복구
- 아키텍처 변경

### 연락처
```yaml
on-call:
  primary: "+82-10-1234-5678"
  secondary: "+82-10-8765-4321"
  slack: "#emergency-alerts"
  email: "ops-team@company.com"
```

---

## 📚 추가 리소스

### 문서
- [Redis Troubleshooting](https://redis.io/docs/management/troubleshooting/)
- [FastAPI Debugging](https://fastapi.tiangolo.com/tutorial/debugging/)
- [Python Async Debugging](https://docs.python.org/3/library/asyncio-dev.html)

### 도구
- [Redis Commander](https://github.com/joeferner/redis-commander) - Web UI
- [RedisInsight](https://redis.com/redis-enterprise/redis-insight/) - 공식 GUI
- [Flower](https://flower.readthedocs.io/) - Celery 모니터링

### 커뮤니티
- [Redis Discord](https://discord.gg/redis)
- [FastAPI Discussions](https://github.com/tiangolo/fastapi/discussions)
- Stack Overflow: `[redis] [fastapi]` 태그