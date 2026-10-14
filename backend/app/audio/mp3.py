"""Corte de MP3 por duração, sem dependências externas.

O servidor entrega ao navegador apenas os quadros MP3 necessários para o estágio
liberado. Também remove metadados (ID3v1/ID3v2/APE) que poderiam conter o título
e o quadro Xing/Info/VBRI, que informaria a duração total do arquivo original.
"""

from __future__ import annotations

from dataclasses import dataclass

_BITRATES = {
    # (versão, layer) -> kbps por índice
    ("1", 3): [0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320],
    ("2", 3): [0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160],
    ("1", 2): [0, 32, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320, 384],
    ("2", 2): [0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160],
}
_SAMPLE_RATES = {
    "1": [44100, 48000, 32000],
    "2": [22050, 24000, 16000],
    "2.5": [11025, 12000, 8000],
}


class Mp3FormatError(ValueError):
    pass


@dataclass(frozen=True)
class FrameHeader:
    version: str
    layer: int
    bitrate_kbps: int
    sample_rate: int
    padding: int
    channel_mode: int

    @property
    def samples(self) -> int:
        if self.layer == 3:
            return 1152 if self.version == "1" else 576
        return 1152

    @property
    def length(self) -> int:
        coef = 144 if (self.layer == 2 or self.version == "1") else 72
        return coef * self.bitrate_kbps * 1000 // self.sample_rate + self.padding

    @property
    def duration(self) -> float:
        return self.samples / self.sample_rate


def parse_header(data: bytes, offset: int) -> FrameHeader | None:
    if offset + 4 > len(data):
        return None
    b0, b1, b2, b3 = data[offset : offset + 4]
    if b0 != 0xFF or (b1 & 0xE0) != 0xE0:
        return None
    version_bits = (b1 >> 3) & 0x3
    layer_bits = (b1 >> 1) & 0x3
    version = {0: "2.5", 2: "2", 3: "1"}.get(version_bits)
    layer = {1: 3, 2: 2}.get(layer_bits)
    if version is None or layer is None:
        return None
    bitrate_idx = (b2 >> 4) & 0xF
    sr_idx = (b2 >> 2) & 0x3
    if bitrate_idx in (0, 15) or sr_idx == 3:
        return None
    table_version = "1" if version == "1" else "2"
    bitrate = _BITRATES[(table_version, layer)][bitrate_idx]
    sample_rate = _SAMPLE_RATES[version][sr_idx]
    return FrameHeader(version, layer, bitrate, sample_rate, (b2 >> 1) & 0x1, (b3 >> 6) & 0x3)


def _skip_id3v2(data: bytes) -> int:
    offset = 0
    # Pode haver mais de uma tag ID3v2 concatenada.
    while data[offset : offset + 3] == b"ID3" and len(data) >= offset + 10:
        flags = data[offset + 5]
        size_bytes = data[offset + 6 : offset + 10]
        size = 0
        for byte in size_bytes:
            size = (size << 7) | (byte & 0x7F)
        offset += 10 + size + (10 if flags & 0x10 else 0)
    return offset


def _is_info_frame(frame: bytes) -> bool:
    head = frame[:64]
    return b"Xing" in head or b"Info" in head or frame[36:40] == b"VBRI"


def _find_first_frame(data: bytes, start: int) -> int:
    offset = start
    limit = min(len(data), start + 64 * 1024)
    while offset < limit:
        header = parse_header(data, offset)
        if header and header.length > 4:
            nxt = offset + header.length
            # Confirma o sincronismo com o próximo quadro para evitar falsos positivos.
            if nxt >= len(data) or parse_header(data, nxt):
                return offset
        offset += 1
    raise Mp3FormatError("Nenhum quadro MP3 válido encontrado")


def trim_mp3(data: bytes, seconds: float) -> tuple[bytes, float]:
    """Retorna (bytes com os quadros até `seconds`, duração efetiva em segundos)."""
    if seconds <= 0:
        raise ValueError("seconds precisa ser positivo")
    offset = _find_first_frame(data, _skip_id3v2(data))
    out = bytearray()
    duration = 0.0
    first = True
    while offset < len(data) and duration < seconds:
        header = parse_header(data, offset)
        if header is None:
            break
        frame = data[offset : offset + header.length]
        if len(frame) < header.length:
            break
        if not (first and _is_info_frame(frame)):
            out += frame
            duration += header.duration
        first = False
        offset += header.length
    if not out:
        raise Mp3FormatError("Arquivo MP3 sem quadros de áudio")
    return bytes(out), duration


def mp3_duration(data: bytes) -> float:
    _, duration = trim_mp3(data, float("inf"))
    return duration
