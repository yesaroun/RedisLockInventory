"""
애플리케이션 설정 관리

Pydantic Settings를 사용하여 환경 변수를 로드합니다.
.env 파일 또는 시스템 환경 변수에서 설정을 읽어옵니다.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """애플리케이션 설정 클래스"""

    # Redis 설정 (단일 Redis)
    redis_host: str
    redis_port: int
    redis_db: int
    redis_password: str

    # Redlock 설정 (분산 락)
    redis_nodes: str = ""  # 쉼표로 구분된 host:port 목록
    use_redlock: bool = False  # Redlock 모드 활성화 여부

    # JWT 설정
    jwt_secret_key: str
    jwt_algorithm: str
    jwt_expiration_minutes: int

    # 데이터베이스 설정
    database_url: str = "sqlite:///./inventory.db"

    # 락 설정
    lock_timeout_seconds: int = 10
    lock_retry_attempts: int = 3
    lock_retry_delay_ms: int = 100

    # 애플리케이션 설정
    app_env: str = "development"
    log_level: str = "INFO"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # 정의되지 않은 환경 변수 무시
    )

    @property
    def redis_url(self) -> str:
        """
        Redis 연결 URL 생성

        비밀번호가 있는 경우: redis://:password@host:port/db
        비밀번호가 없는 경우: redis://host:port/db
        """
        if self.redis_password:
            return f"redis://:{self.redis_password}@{self.redis_host}:{self.redis_port}/{self.redis_db}"
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"

    @property
    def redis_node_list(self) -> list[dict[str, str | int]]:
        """
        Redlock을 위한 Redis 노드 목록 파싱

        Returns:
            [{"host": "redis1", "port": 6380}, {"host": "redis2", "port": 6381}, ...]
        """
        if not self.redis_nodes:
            return []

        nodes = []
        for node in self.redis_nodes.split(","):
            node = node.strip()
            if ":" in node:
                host, port = node.split(":")
                nodes.append({"host": host, "port": int(port)})
            else:
                # 포트가 없으면 기본 포트 6380 사용
                nodes.append({"host": node, "port": 6380})
        return nodes


def get_settings() -> Settings:
    """
    Settings 인스턴스를 반환하는 팩토리 함수
    """
    return Settings()
