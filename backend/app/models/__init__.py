"""Modelos relacionais do Músicas Babuínas.

Separação importante: as tabelas `music_tracks` e `daily_challenges` contêm dados
secretos (qual música é a resposta). Nenhum endpoint serializa essas entidades
diretamente; a API só expõe a resposta através de `services.game.reveal_answer`,
que exige uma partida encerrada.
"""

from app.models.catalog import CatalogEntry, CatalogSource, MusicTrack
from app.models.challenge import DailyChallenge
from app.models.game import GameGuess, GameSession
from app.models.player import Player, PlayerStatistics

__all__ = [
    "CatalogEntry",
    "CatalogSource",
    "DailyChallenge",
    "GameGuess",
    "GameSession",
    "MusicTrack",
    "Player",
    "PlayerStatistics",
]
