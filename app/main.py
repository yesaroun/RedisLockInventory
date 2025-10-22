from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import auth

app = FastAPI(
    title="Redis Lock Inventory API",
    description="Redis 기반 비관적 락을 활용한 재고 관리 시스템",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 라우터 등록
app.include_router(auth.router, prefix="/api/auth", tags=["authentication"])


@app.get("/")
async def root():
    """루트 엔드포인트"""
    return {
        "message": "Redis Lock Inventory API",
        "status": "running",
        "docs": "/docs",
    }


@app.get("/health")
async def health_check():
    """헬스체크 엔드포인트 (Docker 헬스체크용)"""
    return {"status": "healthy"}
