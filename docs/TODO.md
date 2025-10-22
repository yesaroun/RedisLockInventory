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

## Phase 0: 환경 설정 및 설치

### 0.1 uv 설치
**작업 내용**:
- [x] uv 패키지 매니저 설치 (아직 설치하지 않은 경우)
  ```bash
  # macOS/Linux
  curl -LsSf https://astral.sh/uv/install.sh | sh

  # Windows (PowerShell)
  powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

  # 또는 pip로 설치
  pip install uv
  ```

### 0.2 프로젝트 초기화
**작업 내용**:
- [x] 가상환경 생성 및 활성화
  ```bash
  # uv로 가상환경 생성
  uv venv

  # 가상환경 활성화
  source .venv/bin/activate  # Linux/Mac
  # .venv\Scripts\activate   # Windows
  ```

### 0.3 의존성 설치
**작업 내용**:
- [x] pyproject.toml 기반 의존성 설치
  ```bash
  # 개발 의존성 포함 전체 설치
  uv sync --all-extras

  # 또는 프로덕션 의존성만
  uv sync
  ```

### 0.4 환경 변수 설정
**작업 내용**:
- [x] `.env` 파일 생성 (`.env.example` 참고)
  ```bash
  cp .env.example .env
  ```
- [x] `.env` 파일 내용 확인 및 수정
  ```
  REDIS_HOST=localhost
  REDIS_PORT=6379
  REDIS_DB=0
  DATABASE_URL=sqlite:///./inventory.db
  JWT_SECRET_KEY=your-secret-key-change-in-production
  JWT_ALGORITHM=HS256
  JWT_EXPIRATION_MINUTES=30
  LOCK_TIMEOUT_SECONDS=10
  LOCK_MAX_RETRIES=3
  LOCK_RETRY_DELAY=0.1
  ```

### 0.5 Docker 환경 확인
**작업 내용**:
- [x] Docker 및 Docker Compose 설치 확인
  ```bash
  docker --version
  docker-compose --version
  ```
- [x] Docker Compose로 Redis 실행 테스트
  ```bash
  docker-compose up -d redis
  docker-compose logs redis
  ```

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
- [x] User 모델 정의 (SQLAlchemy)
  - `id`: Integer, Primary Key, AutoIncrement
  - `username`: String(50), Unique, Not Null
  - `email`: String(100), Unique, Not Null (선택적)
  - `hashed_password`: String(255), Not Null
  - `created_at`: DateTime, Default=now
  - `updated_at`: DateTime, onupdate=now
- [x] 테스트 작성:
  - 모델 생성 테스트
  - Unique constraint 테스트
  - 필드 검증 테스트

### 1.2 상품 모델 구현
**파일**: `app/models/product.py`

**테스트 파일**: `tests/models/test_product.py`

**작업 내용**:
- [x] Product 모델 정의
  - `id`: Integer, Primary Key, AutoIncrement
  - `name`: String(100), Not Null
  - `description`: Text, Nullable
  - `price`: Integer, Not Null (단위: 원)
  - `stock`: Integer, Not Null (현재 재고 수량)
  - `created_at`: DateTime, Default=now
  - `updated_at`: DateTime, Default=now, onupdate=now
- [x] 테스트 작성:
  - 상품 생성 테스트
  - 필드 검증 테스트

**참고**:
- **이중 저장소 전략**: Redis와 SQLite를 함께 사용
- **SQLite `stock`**: DB에 저장된 현재 재고 (영속성, 감사 추적용)
- **Redis `stock:{product_id}`**: 실시간 재고 관리 (빠른 조회/업데이트, 분산 락킹)
- **동기화 전략**:
  - 매 구매 완료 후 Redis 재고 감소 → DB stock 업데이트 (트랜잭션 내)
  - Redis 장애 시 DB의 stock 값으로 복구 가능
- **정합성**: Redis와 DB가 주기적으로 동기화되어 거의 일치 (eventual consistency)

### 1.3 구매 이력 모델 구현
**파일**: `app/models/purchase.py`

**테스트 파일**: `tests/models/test_purchase.py`

**작업 내용**:
- [x] Purchase 모델 정의
  - `id`: Integer, Primary Key, AutoIncrement
  - `user_id`: Integer, ForeignKey(users.id), Not Null
  - `product_id`: Integer, ForeignKey(products.id), Not Null
  - `quantity`: Integer, Not Null
  - `total_price`: Integer, Not Null
  - `purchased_at`: DateTime, Default=now
  - `user`: relationship with User
  - `product`: relationship with Product
- [x] 테스트 작성:
  - 구매 기록 생성 테스트
  - Relationship 테스트
  - Foreign key constraint 테스트

### 1.4 모델 초기화 및 마이그레이션
**파일**: `app/models/__init__.py`, `alembic/`

**작업 내용**:
- [x] 모든 모델 import 및 export
  ```python
  # app/models/__init__.py
  from app.db.models import User, Product, Purchase

  __all__ = ["User", "Product", "Purchase"]
  ```

- [x] Alembic 마이그레이션 초기 설정
  ```bash
  # Alembic 초기화
  uv run alembic init alembic
  ```

- [x] `alembic.ini` 파일 수정
  ```ini
  # alembic.ini에서 sqlalchemy.url 주석 처리 또는 삭제
  # sqlalchemy.url = driver://user:pass@localhost/dbname
  ```

- [x] `alembic/env.py` 파일 수정
  ```python
  # alembic/env.py
  from app.core.config import get_settings
  from app.db.database import Base
  from app.db.models import User, Product, Purchase  # 모든 모델 import

  # settings에서 DATABASE_URL 가져오기
  settings = get_settings()
  config.set_main_option("sqlalchemy.url", settings.database_url)

  # target_metadata 설정
  target_metadata = Base.metadata
  ```

- [x] 초기 마이그레이션 생성 및 적용
  ```bash
  # 첫 번째 마이그레이션 생성 (자동 감지)
  uv run alembic revision --autogenerate -m "Initial tables: users, products, purchases"

  # 마이그레이션 적용
  uv run alembic upgrade head

  # 마이그레이션 상태 확인
  uv run alembic current

  # 마이그레이션 히스토리 확인
  uv run alembic history
  ```

- [x] 테이블 생성 검증
  ```bash
  # SQLite DB 파일 확인
  ls -l inventory.db

  # SQLite CLI로 테이블 확인 (선택적)
  sqlite3 inventory.db ".tables"
  sqlite3 inventory.db ".schema users"
  ```

---

## Phase 2: 인증 시스템 (Authentication)

### 2.1 비밀번호 해싱 유틸리티
**파일**: `app/core/security.py`

**테스트 파일**: `tests/core/test_security.py`

**작업 내용**:
- [x] 비밀번호 해싱 함수 구현 (bcrypt)
  - `hash_password(password: str) -> str`
  - `verify_password(plain_password: str, hashed_password: str) -> bool`
- [x] 테스트 작성:
  - 해싱 동작 테스트
  - 검증 성공/실패 테스트
  - 같은 비밀번호의 다른 해시값 테스트

### 2.2 JWT 토큰 유틸리티
**파일**: `app/core/security.py` (추가)

**테스트 파일**: `tests/core/test_security.py` (추가)

**작업 내용**:
- [x] JWT 토큰 생성/검증 함수 구현
  - `create_access_token(data: dict, settings: Settings) -> str`
  - `verify_access_token(token: str, settings: Settings) -> dict`
- [x] 테스트 작성:
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
    - **용도**: 상품 생성 시 SQLite의 stock을 Redis에 동기화
    ```python
    # 재고 초기화 (Product.stock → Redis)
    redis.set(f"stock:{product_id}", quantity)
    ```

  - `get_stock(product_id: int, redis: Redis) -> int | None`
    - Redis에서 실시간 재고 수량 조회
    ```python
    stock = redis.get(f"stock:{product_id}")
    return int(stock) if stock else None
    ```

  - `_get_lock_key(product_id: int) -> str`
    - 락 키 생성: `lock:stock:{product_id}`

  - `_acquire_lock(product_id: int, redis: Redis, settings: Settings) -> str | None`
    - SETNX로 락 획득, TTL 설정 (데드락 방지)
    - 고유 락 ID (UUID) 반환
    ```python
    import uuid
    lock_key = f"lock:stock:{product_id}"
    lock_id = str(uuid.uuid4())
    # NX: key가 없을 때만 set, EX: TTL 설정
    acquired = redis.set(lock_key, lock_id, nx=True, ex=settings.lock_timeout_seconds)
    return lock_id if acquired else None
    ```

  - `_release_lock(product_id: int, lock_id: str, redis: Redis) -> bool`
    - Lua 스크립트로 원자적 락 해제 (락 ID 비교 후 삭제)
    ```python
    # Lua 스크립트: 자신이 획득한 락만 해제
    release_script = """
    if redis.call("GET", KEYS[1]) == ARGV[1] then
        return redis.call("DEL", KEYS[1])
    else
        return 0
    end
    """
    lock_key = f"lock:stock:{product_id}"
    result = redis.eval(release_script, 1, lock_key, lock_id)
    return bool(result)
    ```

  - `decrease_stock(product_id: int, quantity: int, redis: Redis, settings: Settings) -> bool`
    - 락 획득 → 재고 확인 → 재고 감소 → 락 해제
    - 재시도 메커니즘 포함
    ```python
    # Lua 스크립트를 사용한 원자적 재고 감소 (선택적, 더 안전)
    decrease_script = """
    local current_stock = redis.call("GET", KEYS[1])
    if not current_stock then
        return -2  -- 상품 없음
    end
    current_stock = tonumber(current_stock)
    local quantity = tonumber(ARGV[1])
    if current_stock >= quantity then
        redis.call("DECRBY", KEYS[1], quantity)
        return current_stock - quantity  -- 남은 재고 반환
    else
        return -1  -- 재고 부족
    end
    """
    # 또는 락 기반 방식으로 구현
    ```

- [ ] 테스트 작성 (TDD):
  - 재고 초기화 테스트
  - 재고 조회 테스트
  - 락 획득/해제 테스트
  - Lua 스크립트 락 해제 테스트 (잘못된 lock_id로 해제 시도 실패)
  - 재고 감소 성공 테스트
  - 재고 부족 시 감소 실패 테스트
  - 락 충돌 시 재시도 테스트
  - 락 만료 테스트 (TTL, time.sleep 활용)

**Lua 스크립트 사용 이유**:
- Redis 명령어의 원자성 보장 (GET + 비교 + DEL을 하나의 트랜잭션으로)
- 다른 클라이언트가 획득한 락을 실수로 해제하는 것 방지
- 네트워크 왕복 횟수 감소

### 3.2 상품 관리 서비스
**파일**: `app/services/product_service.py`

**테스트 파일**: `tests/services/test_product_service.py`

**작업 내용**:
- [ ] ProductService 클래스 구현
  - `create_product(name: str, price: int, stock: int, db: Session, redis: Redis) -> Product`
    - **SQLite**: Product 레코드 생성 (name, price, stock 저장)
    - **Redis**: 실시간 재고 초기화 (`stock:{product_id}` = stock)
    - 트랜잭션 실패 시 Redis 롤백 고려
  - `get_product(product_id: int, db: Session) -> Product | None`
  - `get_product_with_stock(product_id: int, db: Session, redis: Redis) -> dict`
    - DB에서 상품 정보 조회 (DB의 stock 포함)
    - Redis에서 실시간 재고 조회
    - 반환: `{"product": Product, "db_stock": int, "redis_stock": int}`
  - `list_products(db: Session, skip: int = 0, limit: int = 100) -> list[Product]`
  - `sync_stock_to_db(product_id: int, redis_stock: int, db: Session) -> bool`
    - Redis의 재고를 DB에 동기화 (구매 완료 후 호출)
- [ ] 테스트 작성:
  - 상품 생성 테스트 (DB에 stock 저장, Redis에 동일 값 설정 확인)
  - 상품 조회 테스트
  - 상품 목록 조회 테스트
  - DB와 Redis 동기화 테스트

### 3.3 구매 처리 서비스
**파일**: `app/services/purchase_service.py`

**테스트 파일**: `tests/services/test_purchase_service.py`

**작업 내용**:
- [ ] PurchaseService 클래스 구현
  - `purchase_product(user_id: int, product_id: int, quantity: int, db: Session, redis: Redis, settings: Settings) -> Purchase`
    - 상품 존재 확인 (DB에서 조회)
    - 비관적 락으로 Redis 재고 감소 시도
    - 성공 시:
      1. Purchase 기록 생성 (SQLite)
      2. DB의 Product.stock 업데이트 (동기화)
      3. 모두 트랜잭션으로 처리
    - 실패 시 적절한 예외 발생
  - 커스텀 예외 정의 (`app/core/exceptions.py`)
    - `ProductNotFoundException`
    - `InsufficientStockException`
    - `LockAcquisitionException`
- [ ] 테스트 작성 (TDD):
  - 정상 구매 성공 테스트 (Redis + DB 모두 감소 확인)
  - 존재하지 않는 상품 구매 실패
  - 재고 부족 구매 실패
  - 락 획득 실패 테스트
  - 동시 구매 요청 시나리오 (멀티스레드 테스트)
  - DB와 Redis 재고 동기화 검증

### 3.4 재고 API 엔드포인트
**파일**: `app/api/routes/inventory.py`

**테스트 파일**: `tests/api/test_inventory_api.py`

**작업 내용**:
- [ ] Pydantic 스키마 정의 (`app/schemas/inventory.py`)
  - `ProductCreateRequest`: name, price, stock
  - `ProductResponse`: id, name, price, stock, redis_stock, created_at, updated_at
    - `stock`: SQLite에 저장된 현재 재고
    - `redis_stock`: Redis에서 조회한 실시간 재고 (옵션)
  - `StockResponse`: product_id, db_stock, redis_stock, synced (정합성 확인용)
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

### 5.1 Redis 초기 데이터 설정
**파일**: `scripts/init_redis.py`

**작업 내용**:
- [ ] Redis 초기 재고 설정 스크립트 작성
  ```python
  # scripts/init_redis.py
  import redis
  from sqlalchemy.orm import Session
  from app.core.config import get_settings
  from app.db.database import SessionLocal
  from app.db.models import Product

  def init_redis_data():
      """SQLite Product.stock을 Redis로 동기화"""
      settings = get_settings()
      r = redis.Redis(
          host=settings.redis_host,
          port=settings.redis_port,
          db=settings.redis_db,
          decode_responses=True
      )

      db: Session = SessionLocal()
      try:
          # DB에서 모든 상품 조회
          products = db.query(Product).all()

          for product in products:
              key = f"stock:{product.id}"
              # DB의 stock을 Redis에 동기화
              r.set(key, product.stock)
              print(f"Set {key} = {product.stock}")

          print(f"Redis initialization completed! ({len(products)} products)")
      finally:
          db.close()

  if __name__ == "__main__":
      init_redis_data()
  ```

  **중요**: 이 스크립트는 SQLite의 `stock`을 Redis로 동기화합니다.
  상품 생성 시에도 자동으로 Redis에 재고가 설정되므로, 이 스크립트는 주로 다음 상황에서 사용:
  - Redis 데이터 손실 후 복구 (DB의 stock을 기준으로)
  - 새로운 Redis 인스턴스로 마이그레이션
  - 개발/테스트 환경 초기화
  - 서버 재시작 시 Redis 재고 복원

- [ ] 스크립트 실행
  ```bash
  # 로컬 환경
  uv run python scripts/init_redis.py

  # Docker 환경
  docker-compose exec app python scripts/init_redis.py
  ```

- [ ] Redis CLI로 재고 확인
  ```bash
  # Docker 환경
  docker-compose exec redis redis-cli GET stock:1
  docker-compose exec redis redis-cli KEYS "stock:*"

  # 로컬 환경
  redis-cli GET stock:1
  redis-cli KEYS "stock:*"
  ```

### 5.2 통합 테스트
**파일**: `tests/integration/test_full_flow.py`

**작업 내용**:
- [ ] 전체 플로우 통합 테스트
  - 회원 가입 → 로그인 → 상품 생성 → 구매 → 구매 이력 조회
- [ ] 여러 사용자 시나리오 테스트
  - 여러 사용자가 동일 상품 구매 (동시성)

### 5.3 수동 테스트 시나리오
**작업 내용**:
- [ ] Docker Compose로 서버 실행
  ```bash
  # 모든 서비스 빌드 및 실행
  docker-compose up --build

  # 백그라운드 실행
  docker-compose up -d

  # 로그 확인
  docker-compose logs -f app

  # 서비스 상태 확인
  docker-compose ps
  ```

- [ ] Swagger UI 접속 및 API 테스트
  - URL: `http://localhost:8000/docs`
  - 테스트 시나리오:
    1. **회원 가입**: `POST /api/auth/register`
       ```json
       {
         "username": "testuser1",
         "password": "testpassword123"
       }
       ```
       - 예상 응답: 201 Created

    2. **로그인**: `POST /api/auth/login`
       ```json
       {
         "username": "testuser1",
         "password": "testpassword123"
       }
       ```
       - 예상 응답: 200 OK, `access_token` 발급
       - 토큰 복사 (Swagger UI의 "Authorize" 버튼에 입력)

    3. **상품 생성**: `POST /api/products`
       ```json
       {
         "name": "MacBook Pro",
         "price": 2500000,
         "stock": 10
       }
       ```
       - 예상 응답: 201 Created, `product_id` 반환

    4. **재고 조회**: `GET /api/products/{product_id}/stock`
       - 예상 응답: 200 OK, `db_stock: 10, redis_stock: 10, synced: true`

    5. **구매**: `POST /api/purchases`
       ```json
       {
         "product_id": 1,
         "quantity": 2
       }
       ```
       - 예상 응답: 200 OK

    6. **재고 재조회**: `GET /api/products/{product_id}/stock`
       - 예상 응답: 200 OK, `db_stock: 8, redis_stock: 8, synced: true` (10 - 2)
       - DB와 Redis 재고가 모두 동기화되어 감소했는지 확인

    7. **구매 이력 조회**: `GET /api/purchases/me`
       - 예상 응답: 200 OK, 구매 내역 목록

- [ ] Redis에서 최종 재고 확인
  ```bash
  docker-compose exec redis redis-cli GET stock:1
  # 예상 결과: "8"
  ```

- [ ] 서비스 종료 및 정리
  ```bash
  # 서비스 중지
  docker-compose down

  # 볼륨까지 삭제 (데이터 초기화)
  docker-compose down -v
  ```

### 5.4 동시성 테스트 (멀티스레드)
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
  ```python
  # load_tests/locustfile.py
  from locust import HttpUser, task, between
  import random

  class InventoryUser(HttpUser):
      wait_time = between(1, 3)  # 사용자당 대기 시간 1~3초

      def on_start(self):
          """각 사용자 시작 시 회원가입 및 로그인"""
          # 고유한 사용자명 생성
          self.username = f"user_{random.randint(1000, 9999)}"
          self.password = "testpass123"

          # 회원 가입
          response = self.client.post("/api/auth/register", json={
              "username": self.username,
              "password": self.password
          })

          # 로그인 및 토큰 저장
          response = self.client.post("/api/auth/login", json={
              "username": self.username,
              "password": self.password
          })
          if response.status_code == 200:
              self.token = response.json()["access_token"]
              self.headers = {"Authorization": f"Bearer {self.token}"}
          else:
              self.headers = {}

      @task(3)  # 가중치 3 (30%)
      def view_products(self):
          """상품 목록 조회"""
          self.client.get("/api/products", headers=self.headers)

      @task(2)  # 가중치 2 (20%)
      def view_stock(self):
          """재고 조회"""
          product_id = random.randint(1, 3)  # 상품 ID 1~3
          self.client.get(f"/api/products/{product_id}/stock", headers=self.headers)

      @task(5)  # 가중치 5 (50%)
      def purchase_product(self):
          """상품 구매"""
          product_id = random.randint(1, 3)
          quantity = random.randint(1, 2)

          self.client.post("/api/purchases", headers=self.headers, json={
              "product_id": product_id,
              "quantity": quantity
          })
  ```

- [ ] 실행 가이드 작성 (`load_tests/README.md`)
  ```markdown
  # Locust 부하 테스트 가이드

  ## 실행 방법

  ### 1. Locust 웹 UI 모드
  \`\`\`bash
  uv run locust -f load_tests/locustfile.py --host=http://localhost:8000
  \`\`\`
  - 브라우저에서 http://localhost:8089 접속
  - Number of users: 100
  - Spawn rate: 10 (초당 10명씩 증가)
  - Host: http://localhost:8000

  ### 2. 헤드리스 모드 (CLI)
  \`\`\`bash
  uv run locust -f load_tests/locustfile.py \\
    --headless \\
    --users 100 \\
    --spawn-rate 10 \\
    --run-time 60s \\
    --host=http://localhost:8000
  \`\`\`

  ## 테스트 시나리오
  - 동시 사용자: 100명
  - 증가율: 초당 10명
  - 실행 시간: 60초
  - 작업 비율:
    - 상품 목록 조회: 30%
    - 재고 조회: 20%
    - 구매: 50%
  \`\`\`

### 6.2 부하 테스트 실행 및 결과 분석
**작업 내용**:
- [ ] 사전 준비
  ```bash
  # 1. Docker Compose로 서비스 실행
  docker-compose up -d

  # 2. Redis 초기 데이터 설정
  docker-compose exec app python scripts/init_redis.py

  # 3. 초기 재고 확인
  docker-compose exec redis redis-cli KEYS "stock:*"
  docker-compose exec redis redis-cli GET stock:1
  ```

- [ ] Locust 웹 UI로 부하 테스트 수행
  ```bash
  # Locust 시작
  uv run locust -f load_tests/locustfile.py --host=http://localhost:8000

  # 브라우저에서 http://localhost:8089 접속
  # 설정:
  # - Number of users: 100
  # - Spawn rate: 10
  # - Run time: 60s
  ```

- [ ] 결과 분석 항목
  - **응답 시간 분포**:
    - p50 (중앙값): < 50ms
    - p95: < 100ms
    - p99: < 200ms

  - **처리량 (RPS)**:
    - 전체 RPS: 목표 > 100
    - 구매 API RPS: 목표 > 50

  - **에러율**:
    - 전체 에러율: < 5%
    - 재고 부족 에러는 정상 (400)
    - 500 에러는 0%

  - **재고 정합성**:
    ```bash
    # 테스트 종료 후 최종 재고 확인
    docker-compose exec redis redis-cli GET stock:1
    docker-compose exec redis redis-cli GET stock:2
    docker-compose exec redis redis-cli GET stock:3

    # SQLite 구매 내역 확인 (예시)
    sqlite3 inventory.db "SELECT product_id, SUM(quantity) FROM purchases GROUP BY product_id"

    # 정합성 검증 공식
    # Redis 현재 재고 = Product.initial_stock - SUM(Purchase.quantity)
    # 예: stock:1 = 100 (초기) - 30 (구매 합계) = 70 (현재)
    ```

- [ ] 결과 문서 작성 (`docs/LOAD_TEST_RESULT.md`)
  ```markdown
  # 부하 테스트 결과

  ## 테스트 환경
  - 동시 사용자: 100명
  - 실행 시간: 60초
  - 테스트 대상: http://localhost:8000

  ## 결과 요약
  - 전체 요청: X,XXX
  - 성공: X,XXX (XX%)
  - 실패: XXX (X%)
  - 평균 RPS: XXX

  ## 응답 시간
  - p50: XX ms
  - p95: XX ms
  - p99: XX ms

  ## 재고 정합성
  - **테스트 시작 재고** (SQLite Product.stock, 테스트 전):
    - Product 1: 100
    - Product 2: 50
    - Product 3: 200
  - **최종 재고** (테스트 후):
    - **Redis**: stock:1 = XX, stock:2 = XX, stock:3 = XX
    - **DB**: Product 1 stock = XX, Product 2 stock = XX, Product 3 stock = XX
  - **구매 합계** (SQLite SUM(Purchase.quantity)):
    - Product 1: XX개
    - Product 2: XX개
    - Product 3: XX개
  - **검증 결과**:
    - ✅ Redis와 DB 동기화: Redis 재고 == DB stock
    - ✅ 정합성: DB stock = 시작 재고 - 구매 합계
    - ❌ 불일치: 오차 발견 (원인 분석 필요)

  ## 결론
  - 락 메커니즘이 정상 작동하여 재고 정합성 유지
  - 목표 성능 달성 여부
  - 개선 사항
  \`\`\`

- [ ] 동시성 집중 테스트 (선택적)
  ```bash
  # 단일 상품에 집중 구매 요청
  # 목표: 재고 정합성 100% 검증
  # 설정:
  # - 사용자: 50명
  # - 초기 재고: 100개
  # - 각 사용자 구매량: 2개
  # - 기대 결과: 정확히 50건 성공, 나머지 재고 부족

  # Locustfile 수정하여 단일 상품(product_id=1)만 구매하도록 설정
  # 테스트 후 최종 재고 확인: stock:1 = 0
  ```

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
- [ ] 재고 수동 조정 API (SQLite stock + Redis 동기화)
  - DB stock 업데이트 → Redis 동기화
  - 또는 Redis 업데이트 → DB 동기화
- [ ] 전체 구매 이력 조회 API
- [ ] 재고 정합성 검증 API
  - 엔드포인트: `GET /api/admin/inventory/verify`
  - 로직: 모든 상품에 대해 `Redis 재고 == DB stock` 검증
  - 추가 검증: `DB stock == 초기값 - SUM(구매)` (히스토리 기반)
  - 응답: 불일치 항목 리스트 반환

### 8.4 Redis Sentinel/Cluster
- [ ] Redis 고가용성 설정 (프로덕션용)

---

## 체크리스트 요약

### Phase별 완료 체크
- [ ] Phase 0: 환경 설정 및 설치 (5개 항목)
  - uv 설치, 프로젝트 초기화, 의존성 설치, 환경 변수, Docker 확인
- [ ] Phase 1: 데이터베이스 모델 (Models) (4개 섹션)
  - 사용자, 상품, 구매 이력 모델, Alembic 마이그레이션
- [ ] Phase 2: 인증 시스템 (Authentication) (5개 섹션)
  - 비밀번호 해싱, JWT, 인증 서비스, API 엔드포인트, 라우터 등록
- [ ] Phase 3: 재고 관리 시스템 (Inventory) (5개 섹션)
  - Redis 재고 관리 (Lua 스크립트 포함), 상품 서비스, 구매 서비스, API, 라우터 등록
- [ ] Phase 4: 에러 핸들링 (1개 섹션)
  - 전역 예외 핸들러, 커스텀 예외
- [ ] Phase 5: 통합 테스트 및 동시성 테스트 (4개 섹션)
  - Redis 초기 데이터 설정, 통합 테스트, 수동 테스트, 동시성 테스트
- [ ] Phase 6: 부하 테스트 (Locust) (2개 섹션)
  - Locust 시나리오 작성, 부하 테스트 실행 및 결과 분석
- [ ] Phase 7: 문서화 및 배포 (3개 섹션)
  - API 문서 개선, 배포 문서, README 업데이트
- [ ] Phase 8: 추가 개선 사항 (선택적) (4개 섹션)
  - 로깅, 모니터링, 관리자 기능, Redis Cluster

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
**최종 수정일**: 2025-10-22 (Phase 0 추가, Alembic/Lua/Locust 상세 가이드 보강)
