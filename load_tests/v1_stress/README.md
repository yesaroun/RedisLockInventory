# V1 Stress Scenario - Black Friday

## 📋 시나리오 설명

**블랙프라이데이 경쟁 테스트**: 300명의 공격적 구매자가 한정판 100개 상품을 두고 경쟁!

### 목표
- ✅ **정확도 100%**: 정확히 100개만 판매, 초과 판매 0건
- ✅ **공정성**: 선착순 100명만 성공, 나머지 200명은 재고 부족 메시지
- ✅ **처리량**: 높은 경쟁 상황에서도 안정적 처리
- ✅ **응답시간**: P99 < 1000ms (경쟁이 치열해도 합리적 응답 시간)

### 테스트 조건
- **재고**: 100개
- **동시 사용자**: 300명 (3배 경쟁!)
- **구매 수량**: 1개/명
- **Wait Time**: 0.1-0.5초 (매우 공격적)
- **예상 성공률**: ~33% (100/300)

### ⚠️ SQLite 한계
- SQLite는 파일 기반 DB로 높은 동시성 처리에 한계가 있음
- 1000명+ 테스트는 PostgreSQL/MySQL 환경에서 권장
- 현재 설정(300명)은 SQLite에 최적화됨

## 🚀 실행 방법

### 1. 테스트 데이터 생성

```bash
# 프로젝트 루트에서 실행
uv run python load_tests/v1_stress/setup.py
```

생성되는 데이터:
- 관리자 계정: `admin_v1_stress`
- 테스트 상품: "Black Friday Limited Edition" (재고 100개)

### 2. Locust 스트레스 테스트 실행

**웹 UI 모드 (권장)**:
```bash
locust -f load_tests/v1_stress/locustfile.py --host=http://localhost:8080
```

브라우저에서 http://localhost:8089 접속 후:
- Number of users: `300`
- Spawn rate: `30`
- Host: `http://localhost:8080`

**헤드리스 모드 (2분 테스트)**:
```bash
locust -f load_tests/v1_stress/locustfile.py \
  --headless \
  --users 300 \
  --spawn-rate 30 \
  -t 2m \
  --host=http://localhost:8080
```

## 📊 예상 결과

### 정상 동작 시
```
✅ Successful Purchases: ~100
❌ Failed Purchases (Stock Exhausted): ~200
🚨 OVERSOLD Detected: 0
✅ PASS: No overselling detected.

📈 Competition Analysis:
   - Total purchase attempts: ~300
   - Success rate: ~33%
   - Expected success rate: ~33% (100/300)
```

### 성능 메트릭
- **Total Requests**: ~3,000+ (높은 경쟁)
- **Success Rate**: 100% (재고 부족 실패는 정상)
- **TPS**: 100+
- **Average Response Time**: < 200ms
- **P99 Response Time**: < 1000ms

## 🔍 검증 포인트

1. **재고 정합성**: Redis 재고 = 0
2. **구매 정확성**: 총 구매 건수 = 정확히 100건
3. **동시성 제어**: 초과 판매 0건
4. **공정성**: 선착순 원칙 (먼저 도착한 요청이 성공)
5. **DB-Redis 일관성**: 재고 불일치 0건

## 🎯 V1 Basic과의 차이점

| 항목 | V1 Basic | V1 Stress |
|------|----------|-----------|
| 사용자 수 | 100명 | 300명 |
| 재고 | 100개 | 100개 |
| 경쟁률 | 1:1 | 3:1 |
| Wait Time | 1-3초 | 0.1-0.5초 |
| 실패 예상 | 0명 | 200명 |
| 난이도 | ⭐ | ⭐⭐⭐ |

## 🛠️ 트러블슈팅

### 높은 실패율 (> 95%)
- **원인**: 락 경쟁이 너무 치열
- **해결**: `LOCK_RETRY_ATTEMPTS` 증가 또는 `spawn-rate` 낮춤

### 응답 시간 증가 (P99 > 2초)
- **원인**: 서버 부하 과다
- **해결**: 사용자 수를 500명으로 줄여서 테스트

### 초과 판매 발생
- **원인**: 락 메커니즘 버그
- **해결**: `app/services/inventory_service.py` 확인

### 이전 데이터 초기화
```bash
docker compose down
docker compose up -d
uv run python load_tests/v1_stress/setup.py
```

## 📈 성능 개선 아이디어

1. **락 타임아웃 최적화**: 현재 설정 확인 및 조정
2. **재시도 로직 개선**: Exponential backoff 적용
3. **Redis 연결 풀 크기 증가**: 높은 동시성 대응
4. **FastAPI Workers 증가**: `--workers 4` 옵션

## 🔮 다음 단계

- **V2**: 다중 상품 동시 판매 + 데드락 방지
- **V3**: Redlock 분산 락 구현 (5개 Redis 노드)
- **V4**: 프로덕션 레벨 (모니터링, 자동 복구)
