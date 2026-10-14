"""Modelos relacionais do Músicas Babuínas.

Separação importante: as tabelas `music_tracks` e `daily_challenges` contêm dados
secretos (qual música é a resposta). Nenhum endpoint serializa essas entidades
diretamente; a API só expõe a resposta através de `services.game.reveal_answer`,
que exige uma partida encerrada.
"""

from app.models.catalog import CatalogEntry, CatalogSource, MusicTrack
from app.models.challenge import DailyChallenge
from app.models.game import GAME_MODES, MODE_DAILY, MODE_ENDLESS, MODE_MATCH, GameGuess, GameSession
from app.models.multiplayer import Account, AuthSession, Match, MatchRound, Room, RoomMember
from app.models.player import Player, PlayerStatistics

__all__ = [
    "GAME_MODES",
    "MODE_DAILY",
    "MODE_ENDLESS",
    "MODE_MATCH",
    "Account",
    "AuthSession",
    "Match",
    "MatchRound",
    "Room",
    "RoomMember",
    "CatalogEntry",
    "CatalogSource",
    "DailyChallenge",
    "GameGuess",
    "GameSession",
    "MusicTrack",
    "Player",
    "PlayerStatistics",
]
