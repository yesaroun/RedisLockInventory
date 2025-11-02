# Redis 기반 비관적 락 재고 관리 시스템

## 프로젝트 개요

이 프로젝트는 FastAPI와 Redis를 활용하여 비관적 락(Pessimistic Locking)을 적용한 재고 관리 시스템을 구현합니다. 온라인 쇼핑몰 환경을 가정하며, 물건 구매 프로세스를 중심으로 동시 구매
요청 시 재고 불일치를 방지합니다. Redis의 SETNX 명령어를 통해 락을 획득하고, 재고 업데이트를 원자적으로 처리합니다. 또한, 사용자 인증(회원 가입 및 로그인)을 포함하여 실제 운영에 가까운 구조를
채택합니다. TDD(Test-Driven Development) 접근을 통해 안정성을 확보하였습니다.

## 프로젝트 시나리오

### 블랙프라이데이 한정 판매
이 프로젝트는 실제 이커머스에서 자주 발생하는 "한정 수량 상품의 동시 구매 폭주" 문제를 시뮬레이션합니다.

**상황**: 블랙프라이데이 특가 상품 100개 한정 판매
- 1초에 최대 1000명이 동시 구매 시도
- 정확히 100개만 판매되어야 함 (초과 판매 절대 금지)
- 공정한 선착순 보장 필요
- 시스템 다운 없이 안정적 처리

**해결 과제**:
- 재고 정확성: 동시 요청 처리 시에도 정확한 재고 관리
- 성능: 높은 처리량과 낮은 응답 시간 달성
- 공정성: 요청 순서대로 공정한 처리
- 확장성: 트래픽 증가에 대응 가능한 아키텍처

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
- **테스트 도구**: pytest (단위/통합 테스트)
- **기타**: Docker (배포 용도).

## 설치 방법

### 필수 요구사항

- Python 3.11 이상
- Docker 및 Docker Compose
- uv

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

1. **프로젝트 클론**
   ```bash
   git clone https://github.com/your-repo/inventory-system.git
   cd inventory-system
   ```

2. **환경 변수 설정**
   ```bash
   cp .env.example .env
   # .env 파일을 열어 필요한 값 수정
   # REDIS_HOST는 'redis'로 설정 (Docker Compose 서비스명)
   ```

3. **Docker Compose로 실행**
   ```bash
   # 빌드 및 실행
   docker-compose up --build

   # 또는 백그라운드 실행
   docker-compose up -d

   # 로그 확인
   docker-compose logs -f app
   ```

4. **Swagger UI 확인**
    - 브라우저에서 `http://localhost:8000/docs` 접속

5. **종료 및 정리**
   ```bash
   # 서비스 종료
   docker-compose down

   # 볼륨까지 삭제 (데이터 초기화)
   docker-compose down -v
   ```

## 테스트

- **TDD 프로세스**: 각 기능 구현 전에 pytest 테스트 작성 (예: `tests/test_auth.py`, `tests/test_inventory.py`).
- **단위/통합 테스트**:
  ```bash
  # uv run으로 테스트 실행
  uv run pytest

  # 상세 출력
  uv run pytest -v
  ```

## 프로젝트 문서

- **[로드맵](./docs/ROADMAP.md)** - 단계별 구현 계획 (v1~v4)
- **[아키텍처](./docs/ARCHITECTURE.md)** - 시스템 설계 및 구조
- **[성능 테스트](./docs/PERFORMANCE_TEST.md)** - 부하 테스트 계획 및 벤치마크
- **[Redlock 설계](./docs/REDLOCK_DESIGN.md)** - 분산 락 알고리즘 상세 설명
- **[문제 해결](./docs/TROUBLESHOOTING.md)** - 일반적인 문제와 해결 방법
