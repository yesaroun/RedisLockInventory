"""
SQLAlchemy 데이터베이스 설정

SQLAlchemy 엔진, 세션, Base 클래스를 정의합니다.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from app.core.config import get_settings

settings = get_settings()

# SQLite 사용 시 check_same_thread 비활성화
# Connection Pool 설정 (V1 Stress 테스트를 위해 증가)
engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False},
    pool_size=50,  # 기본 connection pool 크기 (기본값: 5 → 50)
    max_overflow=100,  # 추가 가능한 connection 수 (기본값: 10 → 100)
    pool_timeout=60,  # connection 대기 timeout 초 (기본값: 30 → 60)
    pool_pre_ping=True,  # connection 유효성 자동 체크
    pool_recycle=3600,  # 1시간마다 connection 재생성 (stale connection 방지)
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """
    FastAPI 의존성 주입용 데이터베이스 세션 제너레이터

    사용 예:
        @app.get("/items/")
        def read_items(db: Session = Depends(get_db)):
            return db.query(Item).all()
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
