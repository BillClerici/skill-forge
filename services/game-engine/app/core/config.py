"""
Configuration management for Game Engine
"""
from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional


class Settings(BaseSettings):
    """Application settings"""

    # Service Config
    SERVICE_NAME: str = "game-engine"
    SERVICE_VERSION: str = "1.0.0"
    DEBUG: bool = False
    ENVIRONMENT: str = Field(default="development", env="ENVIRONMENT")

    # CORS
    CORS_ORIGINS: list[str] = Field(
        default=["http://localhost:3000", "http://localhost:5173", "http://localhost:8000"],
        env="CORS_ORIGINS"
    )

    # API Keys
    ANTHROPIC_API_KEY: str = Field(..., env="ANTHROPIC_API_KEY")

    # Database URLs
    MONGODB_URL: str = Field(..., env="MONGODB_URL")
    NEO4J_URI: str = Field(..., env="NEO4J_URI")
    NEO4J_USER: str = Field(..., env="NEO4J_USER")
    NEO4J_PASSWORD: str = Field(..., env="NEO4J_PASSWORD")
    POSTGRES_URL: str = Field(..., env="POSTGRES_URL")
    REDIS_URL: str = Field(..., env="REDIS_URL")

    # RabbitMQ
    RABBITMQ_URL: str = Field(..., env="RABBITMQ_URL")

    # MCP Server URLs
    MCP_PLAYER_DATA_URL: str = Field(..., env="MCP_PLAYER_DATA_URL")
    MCP_NPC_PERSONALITY_URL: str = Field(..., env="MCP_NPC_PERSONALITY_URL")
    MCP_WORLD_UNIVERSE_URL: str = Field(..., env="MCP_WORLD_UNIVERSE_URL")
    MCP_QUEST_MISSION_URL: str = Field(..., env="MCP_QUEST_MISSION_URL")
    MCP_ITEM_EQUIPMENT_URL: str = Field(..., env="MCP_ITEM_EQUIPMENT_URL")
    MCP_AUTH_TOKEN: str = Field(..., env="MCP_AUTH_TOKEN")

    # Session Config
    SESSION_STATE_TTL_SECONDS: int = 86400  # 24 hours
    AUTOSAVE_INTERVAL_SECONDS: int = 900  # 15 minutes

    # WebSocket Config
    WS_HEARTBEAT_INTERVAL: int = 30
    WS_MAX_CONNECTIONS: int = 1000

    # Game Engine Config
    MAX_CONCURRENT_SESSIONS: int = 100
    SCENE_GENERATION_TIMEOUT: int = 30
    NPC_RESPONSE_TIMEOUT: int = 20
    ASSESSMENT_TIMEOUT: int = 30

    class Config:
        env_file = ".env"
        case_sensitive = True


# Global settings instance
settings = Settings()
