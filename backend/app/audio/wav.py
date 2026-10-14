"""Leitura, escrita e corte de WAV PCM 16 bits.

O corte reconstrói um cabeçalho mínimo (sem blocos LIST/INFO de metadados) e aplica
um fade-out curto para evitar estalos no fim do trecho.
"""

from __future__ import annotations

import struct

import numpy as np


class WavFormatError(ValueError):
    pass


def encode_wav(samples: np.ndarray, sample_rate: int) -> bytes:
    """Codifica um array mono int16 em WAV."""
    pcm = np.asarray(samples, dtype="<i2").tobytes()
    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF", 36 + len(pcm), b"WAVE",
        b"fmt ", 16, 1, 1, sample_rate, sample_rate * 2, 2, 16,
        b"data", len(pcm),
    )
    return header + pcm


def decode_wav(data: bytes) -> tuple[np.ndarray, int, int]:
    """Retorna (amostras int16 intercaladas, sample_rate, canais)."""
    if data[:4] != b"RIFF" or data[8:12] != b"WAVE":
        raise WavFormatError("Arquivo não é WAV/RIFF")
    offset = 12
    fmt = None
    pcm = None
    while offset + 8 <= len(data):
        chunk_id, size = struct.unpack("<4sI", data[offset : offset + 8])
        body = data[offset + 8 : offset + 8 + size]
        if chunk_id == b"fmt ":
            fmt = struct.unpack("<HHIIHH", body[:16])
        elif chunk_id == b"data":
            pcm = body
        offset += 8 + size + (size & 1)
    if fmt is None or pcm is None:
        raise WavFormatError("WAV sem blocos fmt/data")
    audio_format, channels, sample_rate, _, _, bits = fmt
    if audio_format != 1 or bits != 16:
        raise WavFormatError("Apenas WAV PCM 16 bits é suportado")
    usable = len(pcm) - (len(pcm) % (2 * channels))
    return np.frombuffer(pcm[:usable], dtype="<i2"), sample_rate, channels


def trim_wav(data: bytes, seconds: float, fade_ms: float = 25.0) -> tuple[bytes, float]:
    samples, sample_rate, channels = decode_wav(data)
    if channels > 1:
        samples = samples.reshape(-1, channels).mean(axis=1).astype("<i2")
    count = min(len(samples), int(round(seconds * sample_rate)))
    if count <= 0:
        raise WavFormatError("Trecho vazio")
    clip = samples[:count].astype(np.float32)
    fade = min(count, int(sample_rate * fade_ms / 1000))
    if fade > 0 and count < len(samples):
        clip[-fade:] *= np.linspace(1.0, 0.0, fade, dtype=np.float32)
    return encode_wav(clip.astype("<i2"), sample_rate), count / sample_rate
