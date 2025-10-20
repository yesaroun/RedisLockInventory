# Redis 기반 비관적 락 재고 관리 시스템

## 프로젝트 개요
이 프로젝트는 FastAPI와 Redis를 활용하여 비관적 락(Pessimistic Locking)을 적용한 재고 관리 시스템을 구현합니다. 온라인 쇼핑몰 환경을 가정하며, 물건 구매 프로세스를 중심으로 동시 구매 요청 시 재고 불일치를 방지합니다. Redis의 SETNX 명령어를 통해 락을 획득하고, 재고 업데이트를 원자적으로 처리합니다. 또한, 사용자 인증(회원 가입 및 로그인)을 포함하여 실제 운영에 가까운 구조를 채택합니다. TDD(Test-Driven Development) 접근을 통해 안정성을 확보하였습니다.

### 주요 기능
- **회원 가입**: 사용자 계정 생성 (아이디, 비밀번호 저장).
- **로그인**: JWT 기반 인증 토큰 발급.
- **재고 조회**: 특정 상품의 현재 재고 수량 확인 (인증 필요).
- **구매 처리**: 상품 구매 시 비관적 락 적용, 재고 감소 (수량 지정 가능, 인증 필요).
- **동시성 처리**: 락 만료 및 재시도 메커니즘으로 데드락 방지.
- **에러 핸들링**: 재고 부족, 락 충돌, 인증 실패 등에 대한 적절한 응답.

### 기술 스택
- **백엔드 프레임워크**: FastAPI (비동기 API 지원).
- **데이터 저장소**: Redis (버전 6.0 이상, 비관적 락 및 데이터 저장 용도).
- **패키지 관리**: uv (빠른 Python 패키지 관리 도구).
- **라이브러리**:
  - redis-py: Redis 클라이언트.
  - PyJWT: JWT 토큰 처리.
  - pydantic: 데이터 유효성 검사.
  - uvicorn: FastAPI 서버 실행.
- **테스트 도구**: pytest (단위/통합 테스트), Locust (부하 테스트, 다중 사용자 시뮬레이션).
- **기타**: Docker (배포 용도).

## 설치 방법

### 필수 요구사항
- Python 3.11 이상
- Redis 6.0 이상
- uv (Python 패키지 관리 도구)

### uv 설치
```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows (PowerShell)
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

# 또는 pip로 설치
pip install uv
```

### 프로젝트 설정
1. **Redis 서버 설치 및 실행**
   ```bash
   # Ubuntu/Debian
   sudo apt install redis-server
   redis-server

   # macOS
   brew install redis
   brew services start redis
   ```

2. **프로젝트 클론**
   ```bash
   git clone https://github.com/your-repo/inventory-system.git
   cd inventory-system
   ```

3. **가상환경 생성 및 의존성 설치**
   ```bash
   # uv로 가상환경 생성
   uv venv

   # 가상환경 활성화
   source .venv/bin/activate  # Linux/Mac
   # .venv\Scripts\activate   # Windows

   # 의존성 설치 (pyproject.toml 기반)
   uv sync

   # 또는 개발 의존성 포함 설치
   uv sync --all-extras
   ```

4. **환경 변수 설정**
   ```bash
   cp .env.example .env
   # .env 파일을 열어 필요한 값 수정
   ```

5. **애플리케이션 실행**
   ```bash
   # uv run으로 실행
   uv run uvicorn app.main:app --reload

   # 또는 가상환경 활성화 후
   uvicorn app.main:app --reload
   ```

6. **Swagger UI 확인**
   - 브라우저에서 `http://localhost:8000/docs` 접속

## 사용법
### API 엔드포인트
모든 엔드포인트는 FastAPI의 Swagger UI(`/docs`)에서 테스트 가능합니다. 구매 관련 엔드포인트는 Authorization 헤더에 Bearer JWT 토큰을 요구합니다.

- **POST /register**: 회원 가입.  
  요청 바디: `{"username": "user1", "password": "pass123"}`  
  응답: `{"message": "User registered successfully"}` (중복 시 400 에러).

- **POST /login**: 로그인.  
  요청 바디: `{"username": "user1", "password": "pass123"}`  
  응답: `{"access_token": "jwt_token_here"}` (실패 시 401 에러).

- **GET /inventory/{item_id}**: 재고 조회 (인증 필요).  
  예: `curl -H "Authorization: Bearer {token}" http://localhost:8000/inventory/item1`  
  응답: `{"item_id": "item1", "stock": 100}`.

- **POST /purchase/{item_id}**: 구매 처리 (인증 필요).  
  요청 바디: `{"quantity": 5}`  
  예: `curl -H "Authorization: Bearer {token}" -X POST http://localhost:8000/purchase/item1 -d '{"quantity": 5}'`  
  응답: `{"message": "Purchase successful", "remaining_stock": 95}` (재고 부족 시 400 에러).

### 예시 시나리오
1. 초기 재고 설정: Redis CLI에서 `HSET inventory:item1 stock 100` 명령어 실행.
2. 회원 가입 및 로그인 후 구매: 여러 클라이언트에서 동시에 요청 시 락으로 순차 처리 확인.

## 테스트
- **TDD 프로세스**: 각 기능 구현 전에 pytest 테스트 작성 (예: `tests/test_auth.py`, `tests/test_inventory.py`).
- **단위/통합 테스트**:
  ```bash
  # uv run으로 테스트 실행
  uv run pytest

  # 상세 출력
  uv run pytest -v
  ```
- **부하 테스트**:
  ```bash
  # Locust 실행
  uv run locust -f load_tests/locustfile.py
  ```
- **커버리지 확인**:
  ```bash
  uv run pytest --cov=app --cov-report=html
  ```

## 보안 고려사항
- 비밀번호는 해싱(bcrypt)하여 저장.
- JWT 토큰 만료 시간 설정(30분).
- 프로덕션 환경에서는 HTTPS 적용 및 Redis 인증 활성화.

