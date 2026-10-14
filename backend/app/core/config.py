"""Configuração central da aplicação.

Todos os parâmetros ajustáveis do jogo (estágios de áudio, pontuação, fuso horário,
janelas de repetição) ficam aqui e podem ser sobrescritos por variáveis de ambiente.
"""

from __future__ import annotations

from datetime import date
from functools import lru_cache
from typing import Annotated, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

DEV_SECRET = "dev-only-secret-troque-em-producao"

AudioProviderName = Literal["demo", "deezer", "local"]


def _split_csv(value: object) -> object:
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    return value


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: Literal["development", "test", "production"] = "development"
    app_name: str = "Músicas Babuínas"

    database_url: str = "sqlite:///./babuinos.db"

    # Segredo usado no HMAC que ordena as músicas candidatas de cada dia.
    # Sem ele não é possível prever os desafios futuros.
    challenge_secret: str = DEV_SECRET
    # Zona usada para definir "o dia" do desafio. Brasília não tem horário de verão
    # desde 2019, então a virada acontece sempre à meia-noite local (03:00 UTC).
    challenge_timezone: str = "America/Sao_Paulo"
    launch_date: date = date(2026, 10, 14)

    # Duração (s) de cada estágio de pista. O número de estágios define o número
    # de tentativas e precisa coincidir com a tabela de pontuação.
    clip_stages_seconds: Annotated[list[float], NoDecode] = Field(
        default_factory=lambda: [1, 2, 3, 5, 8, 12]
    )
    score_table: Annotated[list[int], NoDecode] = Field(
        default_factory=lambda: [100, 80, 60, 40, 20, 10]
    )

    # Controle de repetição na seleção diária.
    repeat_window_days: int = 60
    artist_cooldown_days: int = 7

    # Modo ilimitado: quantas músicas recentes do jogador (por categoria) evitar.
    endless_recent_window: int = 50

    # Multiplayer (ver docs/06-modos-de-jogo.md). O número de músicas por categoria é
    # fixo em 3 (18 por partida), como pede a especificação.
    mp_min_players: int = 2
    mp_max_players: int = 8
    mp_round_seconds: float = 60.0
    mp_reveal_seconds: float = 8.0
    mp_speed_bonus_max: int = 50
    # Partida sem nenhum jogador ativo por esse tempo é encerrada (abandono).
    mp_idle_minutes: float = 10.0
    # Sala de espera sem atividade por esse tempo é fechada.
    mp_room_idle_minutes: float = 30.0
    auth_session_days: int = 30
    # Laço do servidor em tempo real (avança rodadas pelo relógio e avisa os clientes).
    realtime_enabled: bool = True
    realtime_interval_seconds: float = 0.5
    rate_limit_auth_per_hour: int = 30

    audio_provider: AudioProviderName = "deezer"
    audio_local_dir: str = "./audio-local"
    audio_cache_ttl_seconds: int = 600
    audio_cache_max_items: int = 32
    deezer_api_base: str = "https://api.deezer.com"
    deezer_timeout_seconds: float = 8.0

    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:5173", "http://127.0.0.1:5173"]
    )

    # Limites de requisições (por janela de 60 s, exceto criação de jogador: 1 h).
    rate_limit_enabled: bool = True
    rate_limit_guess_per_minute: int = 30
    rate_limit_search_per_minute: int = 120
    rate_limit_audio_per_minute: int = 60
    rate_limit_players_per_hour: int = 20

    # Sincroniza o catálogo JSON com o banco ao iniciar.
    auto_sync_catalog: bool = True

    @field_validator("clip_stages_seconds", mode="before")
    @classmethod
    def _parse_stages(cls, value: object) -> object:
        return [float(v) for v in _split_csv(value)] if isinstance(value, str) else value

    @field_validator("score_table", mode="before")
    @classmethod
    def _parse_scores(cls, value: object) -> object:
        return [int(v) for v in _split_csv(value)] if isinstance(value, str) else value

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _parse_origins(cls, value: object) -> object:
        return _split_csv(value)

    @field_validator("database_url")
    @classmethod
    def _normalize_db_url(cls, value: str) -> str:
        # Provedores como Render/Heroku entregam "postgres://"; o SQLAlchemy precisa
        # do dialeto explícito com o driver psycopg 3.
        if value.startswith("postgres://"):
            value = "postgresql://" + value[len("postgres://") :]
        if value.startswith("postgresql://"):
            value = "postgresql+psycopg://" + value[len("postgresql://") :]
        return value

    @field_validator("challenge_timezone")
    @classmethod
    def _validate_tz(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:  # pragma: no cover - erro de configuração
            raise ValueError(f"Fuso horário inválido: {value}") from exc
        return value

    @model_validator(mode="after")
    def _check_consistency(self) -> Settings:
        if not self.clip_stages_seconds:
            raise ValueError("CLIP_STAGES_SECONDS precisa de pelo menos um estágio")
        if len(self.clip_stages_seconds) != len(self.score_table):
            raise ValueError("CLIP_STAGES_SECONDS e SCORE_TABLE precisam ter o mesmo tamanho")
        stages = self.clip_stages_seconds
        if any(b <= a for a, b in zip(stages, stages[1:], strict=False)):
            raise ValueError("Os estágios de áudio precisam ser estritamente crescentes")
        if any(s <= 0 for s in self.clip_stages_seconds):
            raise ValueError("Os estágios de áudio precisam ser positivos")
        if self.app_env == "production" and self.challenge_secret in ("", DEV_SECRET):
            raise ValueError("Defina CHALLENGE_SECRET com um valor aleatório em produção")
        if self.app_env == "production" and len(self.challenge_secret) < 32:
            raise ValueError("CHALLENGE_SECRET precisa ter ao menos 32 caracteres")
        return self

    @property
    def max_attempts(self) -> int:
        return len(self.clip_stages_seconds)

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.challenge_timezone)

    @property
    def catalog_edition(self) -> str:
        """Catálogo ativo: o modo demo usa melodias de domínio público sintetizadas."""
        return "demo" if self.audio_provider == "demo" else "main"


@lru_cache
def get_settings() -> Settings:
    return Settings()
