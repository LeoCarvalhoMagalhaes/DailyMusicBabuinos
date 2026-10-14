# 🐒🎸 Músicas Babuínas

**Heard it? Guess it!** A daily music guessing game. Every day, six categories (Rock, Pop,
Rap, Country, Electronic and General) get a secret song — the same for every player. You hear
a 1-second clip and get six attempts; each wrong guess or skip plays a little more of the
song. The **Rock Baboon** mascot reacts to every move. The interface is in Brazilian
Portuguese.

*[Leia em português](README.md)*

![Home screen](docs/screenshots/inicio-desktop.png)

## Highlights

- **Six independent daily challenges**, identical for everyone, resetting at midnight in
  São Paulo time.
- **Progressive clues** (1, 2, 3, 5, 8, 12 s — configurable), six attempts, skip button and
  100/80/60/40/20/10 scoring.
- **Server-authoritative:** attempts, validation and scoring run on the backend; the secret
  song never reaches the browser before the game ends; audio is trimmed server-side and
  delivered without metadata.
- **Forgiving answers:** accents, case, punctuation, aliases and small typos are accepted
  without confusing similar titles.
- **Full statistics:** win rate, points, average, day streaks, guess distribution, per-genre
  performance and history.
- **Spoiler-free sharing** with the Web Share API and clipboard fallback.
- **Original SVG mascot** with seven moods.
- **Mobile first**, with loading, error and offline states.
- **Pluggable audio:** official Deezer previews, licensed files, or a **demo mode** with
  public-domain melodies synthesized by the game itself.

## Stack

React 19 · TypeScript · Vite · React Router · CSS Modules — Python 3.13 · FastAPI ·
Pydantic v2 · SQLAlchemy 2 · Alembic — PostgreSQL / SQLite — pytest · Vitest · Playwright —
Docker · Render Blueprint · GitHub Actions.

## Running locally

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload        # http://127.0.0.1:8000 (demo mode, SQLite)

cd frontend
npm install
npm run dev                          # http://localhost:5173
```

Set `AUDIO_PROVIDER=deezer` in `backend/.env` to use real Deezer previews and the main
6 × 100 catalog (internet access required, no API key). `docker compose up --build` runs the
API with PostgreSQL.

## Tests

```bash
cd backend && pytest                       # 107 tests (also run on PostgreSQL via TEST_DATABASE_URL)
cd frontend && npm run typecheck && npm test && npm run e2e   # 27 unit + 12 E2E (desktop & mobile)
```

## Documentation (Portuguese)

Analysis and planning, architecture/API/data model, audio and catalog, design, and
deployment guides live in [`docs/`](docs).

## Audio and catalog notes

- **Demo mode** (default) uses public-domain compositions with arrangements synthesized by
  the game; it is clearly labelled and is not the final catalog.
- The **main catalog** is a documented **editorial selection** of 100 songs per category — not
  an official chart, and no rank positions are invented.
- Deezer previews follow Deezer's developer terms (personal use, attribution). For commercial
  use, contact Deezer or use licensed audio (`AUDIO_PROVIDER=local`).

## License and credits

Code, copy and the Rock Baboon mascot are original to this project. Bungee and Rubik fonts
(SIL OFL), Lucide icons (ISC). Artist and song names belong to their owners. Independent
project inspired by daily games such as Bandle, not affiliated with it.
