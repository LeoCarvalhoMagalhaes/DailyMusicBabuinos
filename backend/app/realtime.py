"""Tempo real do multiplayer (WebSocket).

- O banco é a fonte da verdade. O WebSocket só entrega o estado já calculado; ações
  (palpite, pular, pronto, iniciar) vão pelas rotas HTTP, validadas no servidor.
- Um laço a cada `realtime_interval_seconds` avança rodadas vencidas pelo relógio
  (`services.multiplayer.tick`) e, para cada sala com conexões, envia o estado a quem
  está conectado sempre que a versão da sala muda (ou alguém entra/sai da conexão).
- O estado é montado por jogador (cada um vê só o que pode ver).
- Instância única: conexões e presença ficam em memória. Ao reiniciar, os clientes
  reconectam e recebem o estado completo de novo, sem perder nada.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field

import anyio
from fastapi import FastAPI, WebSocket

from app.api.mp_presenter import room_state
from app.models import Account, Room
from app.services import multiplayer as mp

logger = logging.getLogger("babuinos.realtime")


@dataclass
class _Connection:
    websocket: WebSocket
    account_id: str


@dataclass
class RealtimeHub:
    rooms: dict[str, list[_Connection]] = field(default_factory=dict)
    sent_version: dict[str, int] = field(default_factory=dict)
    dirty: set[str] = field(default_factory=set)

    def connected(self, room_id: str) -> set[str]:
        return {c.account_id for c in self.rooms.get(room_id, [])}

    def add(self, room_id: str, websocket: WebSocket, account_id: str) -> None:
        self.rooms.setdefault(room_id, []).append(_Connection(websocket, account_id))
        self.dirty.add(room_id)

    def remove(self, room_id: str, websocket: WebSocket) -> None:
        connections = [c for c in self.rooms.get(room_id, []) if c.websocket is not websocket]
        if connections:
            self.rooms[room_id] = connections
        else:
            self.rooms.pop(room_id, None)
            self.sent_version.pop(room_id, None)
        self.dirty.add(room_id)

    # ------------------------------------------------------------- laço
    def _collect(self, app: FastAPI) -> list[tuple[WebSocket, str]]:
        """Roda numa thread: avança as partidas e monta as mensagens a enviar."""
        settings, provider, clock = app.state.settings, app.state.audio_provider, app.state.clock
        now = clock.now()
        outgoing: list[tuple[WebSocket, str]] = []
        with app.state.session_factory() as db:
            mp.tick(db, settings, now)
            presence = {c.account_id for conns in self.rooms.values() for c in conns}
            for room_id, connections in list(self.rooms.items()):
                room = db.get(Room, room_id)
                if room is None:
                    continue
                # Quem está conectado conta como presente (evita encerrar por inatividade).
                for member in room.members:
                    if member.account_id in presence:
                        mp.touch(member, now)
                db.commit()
                if self.sent_version.get(room_id) == room.version and room_id not in self.dirty:
                    continue
                self.sent_version[room_id] = room.version
                self.dirty.discard(room_id)
                connected = self.connected(room_id)
                for conn in connections:
                    account = db.get(Account, conn.account_id)
                    if account is None:
                        continue
                    state = room_state(db, settings, provider, clock, room, account, connected,
                                       now)
                    outgoing.append((conn.websocket,
                                     '{"type":"state","state":' + state.model_dump_json() + "}"))
        return outgoing

    async def run(self, app: FastAPI) -> None:
        interval = app.state.settings.realtime_interval_seconds
        while True:
            await asyncio.sleep(interval)
            try:
                outgoing = await anyio.to_thread.run_sync(self._collect, app)
            except Exception:  # noqa: BLE001 - o laço não pode morrer
                logger.exception("Falha no laço de tempo real")
                continue
            for websocket, message in outgoing:
                try:
                    await websocket.send_text(message)
                except Exception:  # noqa: BLE001 - conexão caiu; o cliente reconecta
                    for room_id in list(self.rooms):
                        self.remove(room_id, websocket)
