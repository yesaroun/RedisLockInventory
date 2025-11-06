# V1 Basic Scenario

## 📋 시나리오 설명

**기본 동시성 테스트**: 100명의 사용자가 동시에 재고 100개 상품을 구매 시도

### 목표
- ✅ **정확도 100%**: 정확히 100개만 판매, 초과 판매 0건
- ✅ **처리량**: 최소 100 TPS 달성
- ✅ **응답시간**: P50 < 100ms, P99 < 500ms

### 테스트 조건
- **재고**: 100개
- **동시 사용자**: 100명
- **구매 수량**: 1개/명
- **Wait Time**: 1-3초 (일반 사용자 행동)

## 🚀 실행 방법

### 1. 테스트 데이터 생성

```bash
# 프로젝트 루트에서 실행
uv run python load_tests/v1_basic/setup.py
```

생성되는 데이터:
- 관리자 계정: `admin_v1_basic`
- 테스트 상품: "V1 Basic Test Product" (재고 100개)

### 2. Locust 부하 테스트 실행

**웹 UI 모드 (권장)**:
```bash
locust -f load_tests/v1_basic/locustfile.py --host=http://localhost:8080
```

브라우저에서 http://localhost:8089 접속 후:
- Number of users: `100`
- Spawn rate: `10`
- Host: `http://localhost:8080`

**헤드리스 모드**:
```bash
locust -f load_tests/v1_basic/locustfile.py \
  --headless \
  --users 100 \
  --spawn-rate 10 \
  -t 60s \
  --host=http://localhost:8080
```

## 📊 예상 결과

### 정상 동작 시
```
✅ Successful Purchases: 100
❌ Failed Purchases (Stock Exhausted): 0
🚨 OVERSOLD Detected: 0
✅ PASS: No overselling detected.
```

### 성능 메트릭
- **Total Requests**: ~1000+ (구매, 재고조회, 목록조회 등)
- **Success Rate**: 100%
- **TPS**: 100+
- **Average Response Time**: < 100ms
- **P99 Response Time**: < 500ms

## 🔍 검증 포인트

1. **재고 정합성**: Redis 재고 = 0
2. **구매 정확성**: 총 구매 건수 = 100건
3. **동시성 제어**: 초과 판매 0건
4. **DB-Redis 일관성**: 재고 불일치 0건

## 🛠️ 트러블슈팅

### 구매 실패 (404 에러)
```bash
# Redis 재고 확인
docker compose exec redis redis-cli GET stock:1

# 없으면 setup.py 재실행
uv run python load_tests/v1_basic/setup.py
```

### 이전 데이터 초기화
```bash
docker compose down
docker compose up -d
uv run python load_tests/v1_basic/setup.py
```

## 📈 다음 단계

- **V1 Stress**: 1000명 → 100개 재고 (블랙프라이데이 시나리오)
- **V2**: 다중 상품 동시 판매
- **V3**: Redlock 분산 락 구현
