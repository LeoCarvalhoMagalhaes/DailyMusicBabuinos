"""As seis categorias diárias do jogo."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Category:
    slug: str
    name: str
    description: str


CATEGORIES: tuple[Category, ...] = (
    Category("rock", "Rock", "Clássico, alternativo, indie, hard rock, punk e metal."),
    Category("pop", "Pop", "Hits pop nacionais e internacionais de várias décadas."),
    Category("rap", "Rap", "Rap, hip-hop e seus subgêneros."),
    Category("country", "Country", "Country tradicional, moderno e country pop."),
    Category("eletronica", "Eletrônica", "EDM, house, techno, trance, drum and bass e afins."),
    Category("geral", "Geral", "Uma mistura de sucessos de todos os gêneros."),
)

CATEGORY_BY_SLUG = {c.slug: c for c in CATEGORIES}
CATEGORY_SLUGS = tuple(CATEGORY_BY_SLUG)
