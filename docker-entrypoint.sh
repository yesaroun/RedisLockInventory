#!/bin/bash
set -e

echo "Waiting for database to be ready..."
# 데이터베이스 연결 대기 (SQLite는 파일 기반이므로 빠르게 진행)
sleep 1

echo "Running database migrations..."
alembic upgrade head

echo "Migrations completed successfully!"
echo "Starting FastAPI server..."

# exec를 사용하여 PID 1로 uvicorn 실행 (신호 처리를 위해 중요)
exec uvicorn app.main:app --host 0.0.0.0 --port 8000