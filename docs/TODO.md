# Redis Lock Inventory System - 개발 TODO

## 현재 상태

### 완료된 작업
- ✅ Docker 환경 설정 (docker-compose.yml, Dockerfile)
- ✅ FastAPI 기본 앱 구조 (app/main.py)
- ✅ 환경 설정 시스템 (app/core/config.py)
- ✅ Redis 클라이언트 연결 (app/db/redis_client.py)
- ✅ SQLAlchemy 데이터베이스 설정 (app/db/database.py)
- ✅ pytest 픽스처 설정 (tests/conftest.py)
- ✅ 프로젝트 문서화 (README.md, CLAUDE.md)

### 미완료 영역
- ❌ 데이터베이스 모델 정의 (app/models/)
- ❌ 비즈니스 로직 서비스 (app/services/)
- ❌ API 엔드포인트 (app/api/)
- ❌ 테스트 케이스 (tests/)
- ❌ 부하 테스트 (load_tests/)

---

## 개발 원칙

### TDD (Test-Driven Development)
1. 각 기능 구현 **전에** 테스트 작성
2. 테스트 실패 확인
3. 최소한의 코드로 테스트 통과
4. 리팩토링

### 의존성 순서
```
Models → Services → API → Integration Tests
```

---

## Phase 1: 데이터베이스 모델 (Models)

### 1.1 사용자 모델 구현
**파일**: `app/models/user.py`

**테스트 파일**: `tests/models/test_user.py`

**작업 내용**:
- [ ] User 모델 정의 (SQLAlchemy)
  - `id`: Integer, Primary Key, AutoIncrement
  - `username`: String(50), Unique, Not Null
  - `email`: String(100), Unique, Not Null (선택적)
  - `hashed_password`: String(255), Not Null
  - `created_at`: DateTime, Default=now
  - `updated_at`: DateTime, onupdate=now
- [ ] 테스트 작성:
  - 모델 생성 테스트
  - Unique constraint 테스트
  - 필드 검증 테스트

### 1.2 상품 모델 구현
**파일**: `app/models/product.py`

**테스트 파일**: `tests/models/test_product.py`

**작업 내용**:
- [ ] Product 모델 정의
  - `id`: Integer, Primary Key, AutoIncrement
  - `name`: String(100), Not Null
  - `description`: Text, Nullable
  - `price`: Integer, Not Null (단위: 원)
  - `created_at`: DateTime, Default=now
- [ ] 테스트 작성:
  - 상품 생성 테스트
  - 필드 검증 테스트

**참고**: 재고 수량은 Redis에서 관리하므로 SQLite에는 저장하지 않음

### 1.3 구매 이력 모델 구현
**파일**: `app/models/purchase.py`

**테스트 파일**: `tests/models/test_purchase.py`

**작업 내용**:
- [ ] Purchase 모델 정의
  - `id`: Integer, Primary Key, AutoIncrement
  - `user_id`: Integer, ForeignKey(users.id), Not Null
  - `product_id`: Integer, ForeignKey(products.id), Not Null
  - `quantity`: Integer, Not Null
  - `total_price`: Integer, Not Null
  - `purchased_at`: DateTime, Default=now
  - `user`: relationship with User
  - `product`: relationship with Product
- [ ] 테스트 작성:
  - 구매 기록 생성 테스트
  - Relationship 테스트
  - Foreign key constraint 테스트

### 1.4 모델 초기화 및 마이그레이션
**파일**: `app/models/__init__.py`

**작업 내용**:
- [ ] 모든 모델 import 및 export
- [ ] Alembic 마이그레이션 초기 설정
  - `alembic init alembic`
  - `alembic.ini` 설정 (database_url)
  - 초기 마이그레이션 생성
- [ ] 테이블 생성 검증

---

## Phase 2: 인증 시스템 (Authentication)

### 2.1 비밀번호 해싱 유틸리티
**파일**: `app/core/security.py`

**테스트 파일**: `tests/core/test_security.py`

**작업 내용**:
- [ ] 비밀번호 해싱 함수 구현 (bcrypt)
  - `hash_password(password: str) -> str`
  - `verify_password(plain_password: str, hashed_password: str) -> bool`
- [ ] 테스트 작성:
  - 해싱 동작 테스트
  - 검증 성공/실패 테스트
  - 같은 비밀번호의 다른 해시값 테스트

### 2.2 JWT 토큰 유틸리티
**파일**: `app/core/security.py` (추가)

**테스트 파일**: `tests/core/test_security.py` (추가)

**작업 내용**:
- [ ] JWT 토큰 생성/검증 함수 구현
  - `create_access_token(data: dict, settings: Settings) -> str`
  - `verify_access_token(token: str, settings: Settings) -> dict`
- [ ] 테스트 작성:
  - 토큰 생성 테스트
  - 토큰 검증 테스트
  - 만료된 토큰 테스트
  - 잘못된 토큰 테스트

### 2.3 인증 서비스 구현
**파일**: `app/services/auth_service.py`

**테스트 파일**: `tests/services/test_auth_service.py`

**작업 내용**:
- [ ] AuthService 클래스 구현
  - `register_user(username: str, password: str, db: Session) -> User`
  - `authenticate_user(username: str, password: str, db: Session) -> User | None`
  - `get_current_user(token: str, db: Session, settings: Settings) -> User`
- [ ] 테스트 작성 (TDD):
  - 회원 가입 성공 테스트
  - 중복 사용자 등록 실패 테스트
  - 로그인 성공 테스트
  - 잘못된 비밀번호 로그인 실패 테스트
  - 존재하지 않는 사용자 로그인 실패 테스트
  - 토큰으로 사용자 조회 테스트

### 2.4 인증 API 엔드포인트
**파일**: `app/api/routes/auth.py`

**테스트 파일**: `tests/api/test_auth_api.py`

**작업 내용**:
- [ ] Pydantic 스키마 정의 (`app/schemas/auth.py`)
  - `UserRegisterRequest`: username, password
  - `UserLoginRequest`: username, password
  - `TokenResponse`: access_token, token_type
  - `UserResponse`: id, username, created_at
- [ ] API 엔드포인트 구현
  - `POST /api/auth/register`: 회원 가입
  - `POST /api/auth/login`: 로그인 (토큰 발급)
  - `GET /api/auth/me`: 현재 사용자 정보 조회 (인증 필요)
- [ ] 인증 의존성 함수 구현 (`app/api/deps.py`)
  - `get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db))`
- [ ] 테스트 작성 (API 통합 테스트):
  - 회원 가입 성공 (201)
  - 중복 사용자 등록 실패 (409)
  - 로그인 성공 (200, 토큰 반환)
  - 잘못된 credentials 로그인 실패 (401)
  - 인증된 사용자 정보 조회 성공 (200)
  - 인증 없이 보호된 엔드포인트 접근 실패 (401)

### 2.5 app/main.py에 라우터 등록
**파일**: `app/main.py`

**작업 내용**:
- [ ] auth 라우터 import 및 등록
  ```python
  from app.api.routes import auth
  app.include_router(auth.router, prefix="/api/auth", tags=["authentication"])
  ```

---

## Phase 3: 재고 관리 시스템 (Inventory)

### 3.1 Redis 재고 관리 서비스
**파일**: `app/services/inventory_service.py`

**테스트 파일**: `tests/services/test_inventory_service.py`

**작업 내용**:
- [ ] InventoryService 클래스 구현
  - `initialize_stock(product_id: int, quantity: int, redis: Redis) -> bool`
    - Redis key: `stock:{product_id}`, value: quantity
  - `get_stock(product_id: int, redis: Redis) -> int | None`
    - 재고 수량 조회
  - `_get_lock_key(product_id: int) -> str`
    - 락 키 생성: `lock:stock:{product_id}`
  - `_acquire_lock(product_id: int, redis: Redis, settings: Settings) -> bool`
    - SETNX로 락 획득, TTL 설정 (데드락 방지)
  - `_release_lock(product_id: int, redis: Redis) -> bool`
    - 락 해제
  - `decrease_stock(product_id: int, quantity: int, redis: Redis, settings: Settings) -> bool`
    - 락 획득 → 재고 확인 → 재고 감소 → 락 해제
    - 재시도 메커니즘 포함
- [ ] 테스트 작성 (TDD):
  - 재고 초기화 테스트
  - 재고 조회 테스트
  - 락 획득/해제 테스트
  - 재고 감소 성공 테스트
  - 재고 부족 시 감소 실패 테스트
  - 락 충돌 시 재시도 테스트
  - 락 만료 테스트 (TTL)

### 3.2 상품 관리 서비스
**파일**: `app/services/product_service.py`

**테스트 파일**: `tests/services/test_product_service.py`

**작업 내용**:
- [ ] ProductService 클래스 구현
  - `create_product(name: str, price: int, initial_stock: int, db: Session, redis: Redis) -> Product`
    - SQLite에 상품 정보 저장
    - Redis에 재고 초기화
  - `get_product(product_id: int, db: Session) -> Product | None`
  - `list_products(db: Session, skip: int = 0, limit: int = 100) -> list[Product]`
- [ ] 테스트 작성:
  - 상품 생성 테스트 (DB + Redis 동시 확인)
  - 상품 조회 테스트
  - 상품 목록 조회 테스트

### 3.3 구매 처리 서비스
**파일**: `app/services/purchase_service.py`

**테스트 파일**: `tests/services/test_purchase_service.py`

**작업 내용**:
- [ ] PurchaseService 클래스 구현
  - `purchase_product(user_id: int, product_id: int, quantity: int, db: Session, redis: Redis, settings: Settings) -> Purchase`
    - 상품 존재 확인
    - 비관적 락으로 재고 감소 시도
    - 성공 시 Purchase 기록 생성 (SQLite)
    - 실패 시 적절한 예외 발생
  - 커스텀 예외 정의 (`app/core/exceptions.py`)
    - `ProductNotFoundException`
    - `InsufficientStockException`
    - `LockAcquisitionException`
- [ ] 테스트 작성 (TDD):
  - 정상 구매 성공 테스트
  - 존재하지 않는 상품 구매 실패
  - 재고 부족 구매 실패
  - 락 획득 실패 테스트
  - 동시 구매 요청 시나리오 (멀티스레드 테스트)

### 3.4 재고 API 엔드포인트
**파일**: `app/api/routes/inventory.py`

**테스트 파일**: `tests/api/test_inventory_api.py`

**작업 내용**:
- [ ] Pydantic 스키마 정의 (`app/schemas/inventory.py`)
  - `ProductCreateRequest`: name, price, initial_stock
  - `ProductResponse`: id, name, price, current_stock, created_at
  - `StockResponse`: product_id, quantity
  - `PurchaseRequest`: product_id, quantity
  - `PurchaseResponse`: id, product_id, quantity, total_price, purchased_at
- [ ] API 엔드포인트 구현
  - `POST /api/products`: 상품 생성 (인증 필요)
  - `GET /api/products`: 상품 목록 조회 (인증 필요)
  - `GET /api/products/{product_id}`: 상품 상세 조회 (인증 필요)
  - `GET /api/products/{product_id}/stock`: 재고 조회 (인증 필요)
  - `POST /api/purchases`: 상품 구매 (인증 필요)
  - `GET /api/purchases/me`: 내 구매 이력 조회 (인증 필요)
- [ ] 테스트 작성 (API 통합 테스트):
  - 상품 생성 성공 (201)
  - 상품 목록 조회 성공 (200)
  - 재고 조회 성공 (200)
  - 구매 성공 (200)
  - 재고 부족 구매 실패 (400)
  - 인증 없이 접근 실패 (401)

### 3.5 app/main.py에 라우터 등록
**파일**: `app/main.py`

**작업 내용**:
- [ ] inventory 라우터 import 및 등록
  ```python
  from app.api.routes import inventory
  app.include_router(inventory.router, prefix="/api", tags=["inventory"])
  ```

---

## Phase 4: 에러 핸들링 및 예외 처리

### 4.1 전역 예외 핸들러
**파일**: `app/core/exceptions.py` (추가), `app/main.py` (수정)

**작업 내용**:
- [ ] 커스텀 예외 클래스 정의
  - `ProductNotFoundException`: 404
  - `InsufficientStockException`: 400
  - `LockAcquisitionException`: 409 (Conflict)
  - `UserAlreadyExistsException`: 409
  - `InvalidCredentialsException`: 401
- [ ] FastAPI 예외 핸들러 등록
  ```python
  @app.exception_handler(ProductNotFoundException)
  async def product_not_found_handler(request, exc):
      return JSONResponse(status_code=404, content={"detail": str(exc)})
  ```
- [ ] 테스트 작성:
  - 각 예외에 대한 핸들러 응답 테스트

---

## Phase 5: 통합 테스트 및 동시성 테스트

### 5.1 통합 테스트
**파일**: `tests/integration/test_full_flow.py`

**작업 내용**:
- [ ] 전체 플로우 통합 테스트
  - 회원 가입 → 로그인 → 상품 생성 → 구매 → 구매 이력 조회
- [ ] 여러 사용자 시나리오 테스트
  - 여러 사용자가 동일 상품 구매 (동시성)

### 5.2 동시성 테스트 (멀티스레드)
**파일**: `tests/integration/test_concurrency.py`

**작업 내용**:
- [ ] 동시 구매 요청 테스트
  - 10개 재고, 20개 동시 구매 요청 → 10개만 성공
  - 락 충돌 시 재시도 메커니즘 검증
  - 재고 정합성 확인 (최종 재고 = 0)

---

## Phase 6: 부하 테스트 (Locust)

### 6.1 Locust 시나리오 작성
**파일**: `load_tests/locustfile.py`

**작업 내용**:
- [ ] Locust User 클래스 구현
  - 회원 가입
  - 로그인 (토큰 저장)
  - 상품 조회
  - 구매 시도
  - 구매 이력 조회
- [ ] 실행 가이드 작성 (`load_tests/README.md`)
  - `uv run locust -f load_tests/locustfile.py`
  - 목표 RPS, 사용자 수, 시나리오 설명

### 6.2 부하 테스트 실행 및 결과 분석
**작업 내용**:
- [ ] 부하 테스트 수행
  - 100명 동시 사용자, 10초간 구매 요청
- [ ] 결과 분석 문서 작성 (`docs/LOAD_TEST_RESULT.md`)
  - 응답 시간 분포
  - 에러율
  - 락 충돌 재시도 빈도
  - 재고 정합성 확인

---

## Phase 7: 문서화 및 배포

### 7.1 API 문서 개선
**파일**: `app/main.py`, 각 라우터 파일

**작업 내용**:
- [ ] OpenAPI 스키마 개선
  - 각 엔드포인트에 상세한 docstring 추가
  - 예시 요청/응답 추가
- [ ] Swagger UI 확인 (`/docs`)

### 7.2 배포 문서 작성
**파일**: `docs/DEPLOYMENT.md`

**작업 내용**:
- [ ] Docker Compose 배포 가이드
- [ ] 환경 변수 설정 가이드
- [ ] 프로덕션 보안 체크리스트
  - Redis 인증 활성화
  - JWT secret 변경
  - HTTPS 적용
  - CORS 설정 제한

### 7.3 README 업데이트
**파일**: `README.md`

**작업 내용**:
- [ ] 완성된 기능 목록 업데이트
- [ ] API 엔드포인트 목록 추가
- [ ] 테스트 커버리지 배지 추가 (선택적)

---

## Phase 8: 추가 개선 사항 (선택적)

### 8.1 로깅 시스템
- [ ] 구조화된 로깅 추가 (structlog)
- [ ] 락 획득/해제 로그
- [ ] 구매 트랜잭션 로그

### 8.2 모니터링
- [ ] Prometheus 메트릭 추가
  - 구매 성공/실패 카운터
  - 락 대기 시간
  - 재고 수량 게이지

### 8.3 관리자 기능
- [ ] 상품 수정/삭제 API
- [ ] 재고 수동 조정 API
- [ ] 전체 구매 이력 조회 API

### 8.4 Redis Sentinel/Cluster
- [ ] Redis 고가용성 설정 (프로덕션용)

---

## 체크리스트 요약

### Phase별 완료 체크
- [ ] Phase 1: 데이터베이스 모델 (Models)
- [ ] Phase 2: 인증 시스템 (Authentication)
- [ ] Phase 3: 재고 관리 시스템 (Inventory)
- [ ] Phase 4: 에러 핸들링
- [ ] Phase 5: 통합 테스트
- [ ] Phase 6: 부하 테스트
- [ ] Phase 7: 문서화 및 배포
- [ ] Phase 8: 추가 개선 사항 (선택적)

### 테스트 커버리지 목표
- [ ] 전체 테스트 커버리지 > 80%
- [ ] 핵심 비즈니스 로직 (services) 커버리지 > 90%

### 성능 목표
- [ ] 단일 구매 요청 응답 시간 < 100ms (p95)
- [ ] 100명 동시 구매 요청 성공률 > 95%
- [ ] 재고 정합성 100% (동시성 테스트)

---

## 참고 사항

### 개발 순서 원칙
1. **항상 테스트 먼저 작성** (TDD)
2. **하위 계층부터 구현** (Models → Services → API)
3. **각 Phase 완료 후 커밋** (명확한 커밋 메시지)
4. **pytest로 모든 테스트 통과 확인** 후 다음 Phase 진행

### 테스트 실행 명령어
```bash
# 전체 테스트
uv run pytest

# 특정 Phase 테스트
uv run pytest tests/models/
uv run pytest tests/services/
uv run pytest tests/api/

# 커버리지 확인
uv run pytest --cov=app --cov-report=html

# 통합 테스트만
uv run pytest tests/integration/

# 부하 테스트
uv run locust -f load_tests/locustfile.py
```

### 의존성 추가 시
```bash
# 패키지 추가
uv add <package-name>

# 개발 의존성 추가
uv add --dev <package-name>
```

### Git 커밋 컨벤션
```
feat: 새 기능 추가
test: 테스트 추가/수정
fix: 버그 수정
refactor: 리팩토링
docs: 문서 수정
```

---

**작성일**: 2025-10-22
**최종 수정일**: 2025-10-22
