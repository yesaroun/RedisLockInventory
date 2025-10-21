"""
설정(Config) 관련 테스트
"""

from app.core.config import Settings


def test_config_from_env(monkeypatch):
    """환경 변수로부터 설정을 로드하는지 테스트"""
    monkeypatch.setenv("REDIS_HOST", "test-redis")
    monkeypatch.setenv("REDIS_PORT", "6380")
    monkeypatch.setenv("REDIS_DB", "0")
    monkeypatch.setenv("REDIS_PASSWORD", "")
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-key")
    monkeypatch.setenv("JWT_ALGORITHM", "HS256")
    monkeypatch.setenv("JWT_EXPIRATION_MINUTES", "30")

    settings = Settings()

    assert settings.redis_host == "test-redis"
    assert settings.redis_port == 6380
    assert settings.jwt_secret_key == "test-secret-key"
