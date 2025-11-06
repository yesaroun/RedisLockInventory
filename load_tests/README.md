# Load Tests - Redis Lock Inventory System

Redis 비관적 락 기반 재고 관리 시스템의 부하 테스트 시나리오 모음입니다.

## 📁 시나리오 구조

```
load_tests/
├── v1_basic/                   # 기본 동시성 테스트 (100명 → 100개)
│   ├── setup.py
│   ├── locustfile.py
│   └── README.md
├── v1_stress/                  # 블랙프라이데이 경쟁 (300명 → 100개)
│   ├── setup.py
│   ├── locustfile.py
│   └── README.md
├── v3_redlock_aioredlock/      # Redlock (aioredlock 라이브러리)
│   ├── setup.py
│   ├── locustfile.py
│   └── README.md
└── v3_redlock_manual/          # Redlock (수동 쿼럼 구현)
    ├── setup.py
    ├── locustfile.py
    └── README.md
```

## 🎯 시나리오 개요

### V1 Basic - 기본 동시성 테스트
**목표**: 동시 구매 요청 처리의 정확성 검증

| 항목 | 값 |
|------|-----|
| 재고 | 100개 |
| 사용자 | 100명 |
| 경쟁률 | 1:1 |
| 예상 성공 | 100명 |
| 난이도 | ⭐ |

```bash
cd load_tests/v1_basic
uv run python setup.py
locust -f locustfile.py --host=http://localhost:8080
```

➡️ [자세한 설명](v1_basic/README.md)

### V1 Stress - 블랙프라이데이 경쟁
**목표**: 높은 경쟁 상황에서도 정확한 재고 관리

| 항목 | 값 |
|------|-----|
| 재고 | 100개 |
| 사용자 | 300명 |
| 경쟁률 | 3:1 |
| 예상 성공 | 100명 |
| 난이도 | ⭐⭐⭐ |

```bash
cd load_tests/v1_stress
uv run python setup.py
locust -f locustfile.py --host=http://localhost:8080
```

➡️ [자세한 설명](v1_stress/README.md)

### V3 Redlock Aioredlock - 분산 락 (라이브러리)
**목표**: aioredlock 라이브러리를 사용한 Redlock 알고리즘 검증

| 항목 | 값 |
|------|-----|
| 재고 | 100개 |
| 사용자 | 300명 |
| 경쟁률 | 3:1 |
| Redis 노드 | 5개 (쿼럼 3/5) |
| 예상 성공 | 100명 |
| 난이도 | ⭐⭐⭐⭐ |

```bash
cd load_tests/v3_redlock_aioredlock
uv run python setup.py
locust -f locustfile.py --host=http://localhost:8080
```

➡️ [자세한 설명](v3_redlock_aioredlock/README.md)

### V3 Redlock Manual - 분산 락 (수동 구현)
**목표**: 수동 쿼럼 구현으로 Redlock 알고리즘 원리 이해

| 항목 | 값 |
|------|-----|
| 재고 | 100개 |
| 사용자 | 300명 |
| 경쟁률 | 3:1 |
| Redis 노드 | 5개 (쿼럼 3/5) |
| 예상 성공 | 100명 |
| 난이도 | ⭐⭐⭐⭐⭐ |

```bash
cd load_tests/v3_redlock_manual
uv run python setup.py
locust -f locustfile.py --host=http://localhost:8080
```

➡️ [자세한 설명](v3_redlock_manual/README.md)

## 🚀 빠른 시작

### 1. 환경 준비

```bash
# Docker 컨테이너 시작
docker compose down && docker compose up -d

# 서비스 헬스체크 확인
curl http://localhost:8080/health
```

### 2. 시나리오 선택 및 실행

**V1 Basic (권장 - 처음 테스트)**:
```bash
uv run python load_tests/v1_basic/setup.py
locust -f load_tests/v1_basic/locustfile.py --host=http://localhost:8080
```

**V1 Stress (고급 - 스트레스 테스트)**:
```bash
uv run python load_tests/v1_stress/setup.py
locust -f load_tests/v1_stress/locustfile.py --host=http://localhost:8080
```

**V3 Redlock Aioredlock (분산 락 - aioredlock 라이브러리)**:
```bash
uv run python load_tests/v3_redlock_aioredlock/setup.py
locust -f load_tests/v3_redlock_aioredlock/locustfile.py --host=http://localhost:8080
```

**V3 Redlock Manual (분산 락 - 수동 구현)**:
```bash
uv run python load_tests/v3_redlock_manual/setup.py
locust -f load_tests/v3_redlock_manual/locustfile.py --host=http://localhost:8080
```

### 3. Locust 웹 UI 접속

브라우저에서 **http://localhost:8089** 접속

## 📊 성공 기준

모든 시나리오는 다음 기준을 만족해야 합니다:

### ✅ 정확도 (Critical)
- **초과 판매 0건**: `OVERSOLD Detected: 0`
- **재고 정합성**: Redis 재고 = 0 (모두 판매 시)
- **구매 건수**: 정확히 100건

### ✅ 성능 (Important)
- **TPS**: 100+
- **평균 응답시간**: < 200ms
- **P99 응답시간**: < 500ms (V1 Basic), < 1000ms (V1 Stress)

### ✅ 일관성 (Important)
- **DB-Redis 일치**: Stock mismatch = 0
- **선착순 공정성**: 먼저 도착한 요청이 성공

## 🛠️ 공통 작업

### 데이터 초기화 (테스트 재실행 전)

```bash
# 모든 데이터 삭제 및 재시작
docker compose down
docker compose up -d

# 원하는 시나리오의 setup.py 실행
uv run python load_tests/v1_basic/setup.py
```

### 헤드리스 모드 (자동화 테스트)

```bash
# V1 Basic
locust -f load_tests/v1_basic/locustfile.py \
  --headless --users 100 --spawn-rate 10 -t 60s \
  --host=http://localhost:8080

# V1 Stress
locust -f load_tests/v1_stress/locustfile.py \
  --headless --users 300 --spawn-rate 30 -t 2m \
  --host=http://localhost:8080

# V3 Redlock Aioredlock
locust -f load_tests/v3_redlock_aioredlock/locustfile.py \
  --headless --users 300 --spawn-rate 10 -t 60s \
  --host=http://localhost:8080

# V3 Redlock Manual
locust -f load_tests/v3_redlock_manual/locustfile.py \
  --headless --users 300 --spawn-rate 10 -t 60s \
  --host=http://localhost:8080
```

### CSV 리포트 저장

```bash
locust -f load_tests/v1_basic/locustfile.py \
  --headless --users 100 --spawn-rate 10 -t 60s \
  --csv=results/v1_basic \
  --host=http://localhost:8080
```

## 🔍 디버깅

### Redis 재고 확인

**단일 Redis (V1 시나리오)**:
```bash
# 재고 키 확인
docker compose exec redis redis-cli KEYS "stock:*"

# 특정 상품 재고 조회
docker compose exec redis redis-cli GET stock:1

# 락 상태 확인
docker compose exec redis redis-cli KEYS "lock:*"
```

**다중 Redis 노드 (V3 Redlock 시나리오)**:
```bash
# 모든 노드의 재고 확인 (쿼럼 검증)
for i in {0..4}; do
  echo "Node $i:"
  docker compose exec redis${i:-''} redis-cli GET stock:1
done

# 모든 노드의 락 상태 확인
for i in {0..4}; do
  echo "Node $i lock:"
  docker compose exec redis${i:-''} redis-cli GET lock:stock:1
done
```

### 로그 확인

```bash
# FastAPI 앱 로그
docker compose logs app -f

# Redis 로그
docker compose logs redis -f
```

### DB 확인

```bash
# SQLite 직접 접속
docker compose exec app sqlite3 inventory.db

# 구매 이력 확인
docker compose exec app sqlite3 inventory.db "SELECT COUNT(*) FROM purchases;"
```

## 📈 로드맵

### ✅ V1 (완료)
- ✅ 단일 Redis 비관적 락
- ✅ 단일 상품 재고 관리
- ✅ 기본 동시성 테스트 (v1_basic)
- ✅ 블랙프라이데이 스트레스 테스트 (v1_stress)

### ✅ V3 (완료)
- ✅ Redlock 알고리즘 구현 (aioredlock 라이브러리)
- ✅ Redlock 알고리즘 구현 (수동 쿼럼)
- ✅ Redis 5개 노드 클러스터
- ✅ 쿼럼 기반 합의 알고리즘
- ✅ 노드 장애 허용 (2/5 노드 다운까지 동작)

### 🔜 V2 (계획)
- 다중 상품 동시 판매
- 데드락 방지 (락 획득 순서 통일)

### 🔜 V4 (계획)
- 모니터링 대시보드
- 자동 복구 메커니즘
- 써킷 브레이커 패턴
- 네트워크 파티션 시뮬레이션

## 🤝 기여하기

새로운 시나리오를 추가하려면:

1. 새 폴더 생성: `load_tests/v2_multiproduct/`
2. 필수 파일 작성:
   - `setup.py` - 테스트 데이터 생성
   - `locustfile.py` - Locust 부하 테스트 정의
   - `README.md` - 시나리오 설명
3. 이 파일에 시나리오 추가

## 📚 참고 자료

- [Locust 공식 문서](https://docs.locust.io/)
- [Redis 비관적 락 패턴](https://redis.io/docs/manual/patterns/distributed-locks/)
- [Redlock 알고리즘 공식 문서](https://redis.io/docs/manual/patterns/distributed-locks/#the-redlock-algorithm)
- [aioredlock 라이브러리](https://github.com/joanvila/aioredlock)
- [FastAPI 성능 최적화](https://fastapi.tiangolo.com/deployment/)

## 🔑 Redlock vs 단일 락 비교

| 특징 | 단일 Redis 락 (V1) | Redlock (V3) |
|------|-------------------|--------------|
| 구현 복잡도 | 낮음 | 높음 |
| 노드 개수 | 1개 | 5개 (권장) |
| 가용성 | 낮음 (SPOF) | 높음 (2/5 장애 허용) |
| 성능 | 빠름 (~100ms) | 중간 (~200ms) |
| 정확성 | 높음 | 매우 높음 |
| 사용 시기 | 단일 서버 환경 | 분산 환경, 고가용성 요구 |
