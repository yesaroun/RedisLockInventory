# Load Testing Guide

이 디렉토리는 ROADMAP.md의 Version 1 성능 테스트를 위한 Locust 부하 테스트를 포함합니다.

## 목표 (Version 1)

- **목표 TPS**: 100
- **응답시간**: P50 < 100ms, P99 < 500ms
- **정확도**: 100% (초과 판매 0건)
- **가용성**: 99%

## 사전 준비

### 1. 애플리케이션 실행

```bash
# Docker Compose로 앱 실행
docker-compose up -d

# 로그 확인
docker-compose logs -f app
```

### 2. Locust 설치

```bash
# uv를 사용하는 경우 (권장)
uv pip install locust

# 또는 pip
pip install locust
```

### 3. 테스트 데이터 초기화

```bash
# 기본 시나리오 (100개 재고)
python load_tests/setup_test_data.py --scenario v1_basic

# 블랙프라이데이 시나리오 (100개 재고, 1000명 경쟁)
python load_tests/setup_test_data.py --scenario v1_stress

# 커스텀 재고
python load_tests/setup_test_data.py --scenario custom --stock 500
```

## 테스트 시나리오

### 시나리오 1: 기본 동시성 테스트

**목표**: 100명이 동시에 1개씩 구매 (총 100개 재고)

**기대 결과**:
- 정확히 100개 판매
- 초과 판매 0건
- DB-Redis 재고 일치

**실행 방법**:

```bash
# 웹 UI 모드 (http://localhost:8089)
locust -f load_tests/locustfile.py --host=http://localhost:8000

# 헤드리스 모드 (60초 실행)
locust -f load_tests/locustfile.py \
    --headless \
    --users 100 \
    --spawn-rate 10 \
    --run-time 60s \
    --host=http://localhost:8000
```

### 시나리오 2: 락 타임아웃 테스트

**목표**: 락 홀딩 시간 초과 시 자동 해제

**검증 방법**:
- 기본 락 타임아웃: 10초 (`.env`의 `LOCK_TIMEOUT` 참조)
- 장시간 실행하여 데드락이 발생하지 않는지 확인

```bash
# 5분 동안 지속적인 부하
locust -f load_tests/locustfile.py \
    --headless \
    --users 50 \
    --spawn-rate 5 \
    --run-time 5m \
    --host=http://localhost:8000
```

### 시나리오 3: 블랙프라이데이 스트레스 테스트

**목표**: 1000명이 100개 재고를 두고 경쟁

**기대 결과**:
- 100명만 구매 성공
- 900명은 "재고 부족" 응답
- 초과 판매 0건
- 시스템 안정성 유지

**실행 방법**:

```bash
# AggressiveBuyer 사용 (빠른 요청 간격)
locust -f load_tests/locustfile.py \
    --headless \
    --users 1000 \
    --spawn-rate 50 \
    --run-time 3m \
    --user-classes AggressiveBuyer \
    --host=http://localhost:8000
```

### 시나리오 4: 성능 벤치마크 (TPS 목표 달성)

**목표**: 100 TPS 달성 및 응답시간 검증

```bash
# CSV 리포트 저장
locust -f load_tests/locustfile.py \
    --headless \
    --users 100 \
    --spawn-rate 10 \
    --run-time 2m \
    --csv=results/v1_benchmark \
    --html=results/v1_benchmark.html \
    --host=http://localhost:8000
```

## 결과 분석

### 1. 웹 UI에서 확인 (권장)

1. `locust -f load_tests/locustfile.py --host=http://localhost:8000` 실행
2. 브라우저에서 http://localhost:8089 접속
3. Number of users, Spawn rate 설정 후 Start
4. 실시간 차트와 통계 확인

### 2. 터미널 출력

테스트 종료 시 다음 메트릭이 출력됩니다:

```
📊 Test Results Summary
============================================================
✅ Successful Purchases: 100
❌ Failed Purchases (Stock Exhausted): 0
🚨 OVERSOLD Detected: 0
⚠️  Stock Mismatch Detected: 0
============================================================
✅ PASS: No overselling detected.
✅ PASS: DB-Redis stock consistency maintained.
============================================================
```

### 3. CSV 리포트 분석

`--csv` 옵션을 사용하면 다음 파일이 생성됩니다:

- `results/v1_benchmark_stats.csv`: 요청별 통계 (RPS, 응답시간, 실패율)
- `results/v1_benchmark_stats_history.csv`: 시간별 메트릭
- `results/v1_benchmark_failures.csv`: 실패 요청 상세

**주요 확인 항목**:

```bash
# P50, P99 응답시간 확인 (ms)
cat results/v1_benchmark_stats.csv | grep "Aggregated"

# TPS 계산
# Total Request Count / Total Time (초)
```

### 4. 성공 기준

#### ✅ 정확도 검증
- [ ] 초과 판매 0건 (`OVERSOLD Detected: 0`)
- [ ] DB-Redis 재고 불일치 0건 (`Stock Mismatch Detected: 0`)

#### ✅ 성능 검증
- [ ] 목표 TPS ≥ 100
- [ ] P50 응답시간 < 100ms
- [ ] P99 응답시간 < 500ms
- [ ] 실패율 < 1% (재고 부족 제외)

#### ✅ 안정성 검증
- [ ] 데드락 발생 0건
- [ ] 서버 에러 (5xx) 0건
- [ ] 모든 락 정상 해제

## 트러블슈팅

### 문제: "Server is not reachable"

**해결**:
```bash
# 앱 상태 확인
docker-compose ps

# 재시작
docker-compose restart app

# 헬스체크
curl http://localhost:8000/health
```

### 문제: "초과 판매 발생"

**원인**: 동시성 버그 또는 락 메커니즘 문제

**디버깅**:
```bash
# Redis 재고 확인
docker-compose exec redis redis-cli
> GET stock:1
> KEYS lock:stock:*

# 앱 로그 확인
docker-compose logs app | grep -i error
```

### 문제: "높은 응답시간 (P99 > 500ms)"

**원인**:
- Redis 연결 성능
- DB I/O 병목
- 락 대기 시간

**최적화**:
```bash
# Redis 성능 확인
docker-compose exec redis redis-cli --latency

# 락 설정 조정 (.env)
LOCK_TIMEOUT=5  # 기본 10초 → 5초로 단축
LOCK_RETRY_DELAY=0.05  # 재시도 간격 단축
```

### 문제: "Connection pool exhausted"

**해결**:
```python
# locustfile.py에서 connection_timeout 증가 (필요 시)
class NormalUser(HttpUser):
    network_timeout = 10.0  # 기본값 증가
```

## 고급 사용법

### 분산 테스트 (여러 머신)

**Master 노드**:
```bash
locust -f load_tests/locustfile.py \
    --master \
    --expect-workers 3 \
    --host=http://localhost:8000
```

**Worker 노드** (다른 터미널/머신에서):
```bash
locust -f load_tests/locustfile.py \
    --worker \
    --master-host=localhost
```

### 커스텀 유저 클래스 선택

```bash
# NormalUser만 사용 (기본값)
locust -f load_tests/locustfile.py --user-classes NormalUser

# AggressiveBuyer만 사용
locust -f load_tests/locustfile.py --user-classes AggressiveBuyer

# 혼합 (50% Normal, 50% Aggressive)
locust -f load_tests/locustfile.py --user-classes NormalUser,AggressiveBuyer
```

### 단계별 부하 증가 (Step Load)

```bash
# 10명씩 단계적으로 증가 (60초마다)
locust -f load_tests/locustfile.py \
    --step-load \
    --step-users 10 \
    --step-time 60s
```

## 다음 단계 (Version 2)

Version 1 테스트를 통과한 후:
- [ ] 다중 상품 동시 구매 테스트
- [ ] 번들 상품 All-or-Nothing 테스트
- [ ] 데드락 시뮬레이션 (A→B, B→A 순서)
- [ ] 목표 TPS 200 달성

## 참고 자료

- [Locust 공식 문서](https://docs.locust.io/)
- [ROADMAP.md](../docs/ROADMAP.md) - 프로젝트 전체 로드맵
- [PERFORMANCE_TEST.md](../docs/PERFORMANCE_TEST.md) - 성능 테스트 상세 계획
