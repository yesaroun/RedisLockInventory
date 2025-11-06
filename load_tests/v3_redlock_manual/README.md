# V3 Redlock Manual Scenario

## 📋 시나리오 설명

**분산 락 스트레스 테스트 (수동 쿼럼 구현)**: 300명의 공격적 구매자가 재고 100개 상품을 경쟁

### 목표
- ✅ **정확도 100%**: 정확히 100개만 판매, 초과 판매 0건
- ✅ **처리량**: 최소 80 TPS 달성
- ✅ **응답시간**: P50 < 250ms, P99 < 1500ms
- ✅ **성공률**: ~33% (100/300)
- ✅ **분산 락**: 수동 Redlock 구현 검증

### 테스트 조건
- **재고**: 100개
- **동시 사용자**: 300명 (3:1 경쟁률)
- **구매 수량**: 1개/명
- **Wait Time**: 0.1-0.5초 (매우 공격적)
- **Redis 노드**: 5개 (quorum 3/5)
- **락 메커니즘**: 수동 쿼럼 구현 (aioredlock 미사용)

### 특징
- 🛠️ **수동 구현**: aioredlock 라이브러리 없이 직접 구현
- 📡 **5개 Redis 노드**: 분산 환경 시뮬레이션
- 🎯 **쿼럼 기반**: 과반수(3/5) 이상 노드에서 락 획득 필수
- 🔧 **동기 처리**: 순차적 락 획득 및 해제
- 📚 **학습 목적**: Redlock 알고리즘 원리 이해

## 🚀 실행 방법

### 1. Redis 노드 5개 실행

```bash
# Docker Compose로 5개 노드 시작
docker compose up -d

# 노드 상태 확인
docker compose ps

# 각 노드 접근 확인
docker compose exec redis redis-cli ping      # PONG
docker compose exec redis1 redis-cli ping     # PONG
docker compose exec redis2 redis-cli ping     # PONG
docker compose exec redis3 redis-cli ping     # PONG
docker compose exec redis4 redis-cli ping     # PONG
```

### 2. 테스트 데이터 생성

```bash
# 프로젝트 루트에서 실행
uv run python load_tests/v3_redlock_manual/setup.py
```

생성되는 데이터:
- 관리자 계정: `admin_v3_manual`
- 테스트 상품: "V3 Redlock Manual Test Product" (재고 100개)
- Redis: 5개 노드 모두에 재고 동기화

### 3. Locust 부하 테스트 실행

**웹 UI 모드 (권장)**:
```bash
locust -f load_tests/v3_redlock_manual/locustfile.py --host=http://localhost:8080
```

브라우저에서 http://localhost:8089 접속 후:
- Number of users: `300`
- Spawn rate: `10`
- Host: `http://localhost:8080`

**헤드리스 모드**:
```bash
locust -f load_tests/v3_redlock_manual/locustfile.py \
  --headless \
  --users 300 \
  --spawn-rate 10 \
  -t 60s \
  --host=http://localhost:8080
```

## 📊 예상 결과

### 정상 동작 시
```
✅ Successful Purchases: ~100
❌ Failed Purchases (Stock Exhausted): ~200
🚨 OVERSOLD Detected: 0
📈 Success Rate: 33.33%
✅ PASS: No overselling detected. Manual Redlock works correctly!
✅ PASS: DB-Redis stock consistency maintained.
```

### 성능 메트릭
- **Total Requests**: ~3000+ (구매, 재고조회, 목록조회 등)
- **Success Rate**: ~33% (100/300)
- **TPS**: 80+
- **Average Response Time**: < 250ms
- **P99 Response Time**: < 1500ms
- **Lock Acquisition Time**: < 100ms (순차 처리)

### 분산 락 메트릭
- **Quorum Success Rate**: 100% (쿼럼 획득 성공률)
- **Lock Acquisition**: 순차적으로 5개 노드 락 획득 시도
- **Lock Release**: 모든 노드에서 안전한 락 해제

## 🔍 검증 포인트

1. **재고 정합성**: 모든 Redis 노드에서 재고 = 0
2. **구매 정확성**: 총 구매 건수 = 100건
3. **동시성 제어**: 초과 판매 0건
4. **쿼럼 동작**: 과반수(3/5) 노드에서 락 획득 성공
5. **DB-Redis 일관성**: 재고 불일치 0건
6. **수동 구현 정확성**: aioredlock과 동일한 결과

## 🛠️ 트러블슈팅

### Redis 노드 상태 확인

```bash
# 각 노드별 재고 확인
docker compose exec redis redis-cli GET stock:1
docker compose exec redis1 redis-cli GET stock:1
docker compose exec redis2 redis-cli GET stock:1
docker compose exec redis3 redis-cli GET stock:1
docker compose exec redis4 redis-cli GET stock:1

# 모든 노드가 동일한 값을 반환해야 함
```

### 락 상태 확인

```bash
# 락 키 확인 (테스트 중)
docker compose exec redis redis-cli GET lock:stock:1

# 락 TTL 확인
docker compose exec redis redis-cli TTL lock:stock:1

# 락 소유자(UUID) 확인
docker compose exec redis redis-cli GET lock:stock:1
```

### 쿼럼 실패 디버깅

```bash
# 락 획득 실패 시 각 노드별 락 상태 확인
for i in {0..4}; do
  echo "Node $i:"
  docker compose exec redis${i:-''} redis-cli GET lock:stock:1
done
```

### 이전 데이터 초기화

```bash
# Redis 데이터 모두 삭제
docker compose down -v
docker compose up -d

# 테스트 데이터 재생성
uv run python load_tests/v3_redlock_manual/setup.py
```

## 🔬 고급 테스트

### 노드 장애 시뮬레이션

```bash
# 테스트 진행 중 1개 노드 중지
docker compose stop redis4

# 예상: 여전히 쿼럼(3/4) 만족하므로 정상 동작

# 2개 노드 중지
docker compose stop redis3

# 예상: 여전히 쿼럼(3/3) 만족하므로 정상 동작

# 3개 노드 중지 (쿼럼 실패)
docker compose stop redis2

# 예상: 쿼럼 실패(2/2), 모든 구매 실패
```

### 락 타임아웃 테스트

```bash
# .env에서 락 타임아웃 단축
LOCK_TIMEOUT_SECONDS=1

# 예상: 타임아웃 증가, 처리량 감소
```

## 📈 성능 비교

### V3 Aioredlock vs V3 Manual

| 항목 | V3 Aioredlock | V3 Manual |
|-----|---------------|-----------|
| 구현 방식 | aioredlock 라이브러리 | 수동 쿼럼 구현 |
| 락 획득 방식 | 비동기 병렬 | 동기 순차 |
| 평균 응답시간 | < 200ms | < 250ms |
| P99 응답시간 | < 1000ms | < 1500ms |
| TPS | 100+ | 80+ |
| 코드 복잡도 | 낮음 | 높음 |
| 학습 가치 | 보통 | 높음 |

### V1 Basic vs V3 Manual

| 항목 | V1 Basic | V3 Manual |
|-----|----------|-----------|
| 경쟁률 | 1:1 | 3:1 |
| Redis 노드 | 1개 | 5개 |
| 락 메커니즘 | SETNX (단일) | Redlock (수동) |
| 평균 응답시간 | < 100ms | < 250ms |
| P99 응답시간 | < 500ms | < 1500ms |
| 가용성 | 낮음 (SPOF) | 높음 (2개 장애 허용) |

## 💡 알고리즘 설명

### 수동 Redlock 구현 플로우

1. **락 획득 단계**:
   ```
   for each Redis node:
     try to SET lock:stock:1 = UUID with NX and EX
     if success: add to acquired_locks list

   if len(acquired_locks) >= quorum (3/5):
     proceed to step 2
   else:
     release all acquired locks and return failure
   ```

2. **재고 감소 단계**:
   ```
   for each Redis node:
     execute Lua script to decrease stock atomically
     if success: increment success_count

   if success_count >= quorum:
     return success
   else:
     rollback all changes and return failure
   ```

3. **락 해제 단계**:
   ```
   for each lock in acquired_locks:
     execute Lua script to check UUID and delete lock
   ```

### 왜 Lua 스크립트를 사용하는가?

- **원자성**: GET + DEL을 원자적으로 실행
- **정확성**: 다른 클라이언트의 락을 실수로 해제하지 않음
- **성능**: 네트워크 왕복 횟수 감소

## 📌 다음 단계

- **성능 최적화**: 병렬 락 획득 구현 (asyncio 사용)
- **클럭 드리프트 고려**: validity time 계산 추가
- **자동 복구**: 노드 장애 시 자동 재시도
- **모니터링**: 락 획득 실패율, 쿼럼 성공률 추적
