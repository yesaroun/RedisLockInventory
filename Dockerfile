FROM python:3.11-slim as builder

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

COPY pyproject.toml ./
COPY uv.lock* ./

# 프로덕션 의존성만 설치
RUN uv sync --no-dev --no-install-project

FROM python:3.11-slim

WORKDIR /app

# uv는 런타임에 필요 없지만, 디버깅 시 유용할 수 있음
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# 가상환경 복사
COPY --from=builder /app/.venv /app/.venv

# 애플리케이션 파일 복사
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./
COPY main.py ./

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD python -c "import requests; requests.get('http://localhost:8080/health', timeout=2)" || exit 1

# entrypoint 스크립트 복사 및 실행 권한 설정
COPY docker-entrypoint.sh ./
RUN chmod +x docker-entrypoint.sh

ENTRYPOINT ["./docker-entrypoint.sh"]