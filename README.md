# Resume Checker

Personal AI career assistant MVP. Upload your resume, answer a few questions, paste job postings,
get ATS + semantic gap analysis, generate tailored resumes and cover letters in your voice, track
applications on a kanban board. RAG over pgvector — only relevant chunks go to Claude.

## Local development

```bash
# 1. Start Postgres + pgvector
docker compose up -d

# 2. Backend
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example .env   # then fill in a real ANTHROPIC_API_KEY and a random SESSION_SECRET
uvicorn app.main:app --reload
```

Open http://localhost:8000 — it redirects to `/login.html` if you're not signed in. Register an
account first (invite-only in practice: registration works but no signup link is advertised
anywhere), which logs you in and drops you into onboarding.

Without a real `ANTHROPIC_API_KEY`, everything except AI calls (analysis, resume/cover-letter
generation) works: register/login, upload, chunking, embeddings, the tracker board.

Multi-user: every account gets its own isolated resume/jobs/tracker data (`user_id` scoping enforced
on every query — see `app/search.py` and the ownership checks in `routers/jobs.py`/`routers/generate.py`).
Not built: email verification, password-reset-by-email, login rate-limiting — fine for invite-only
use, revisit before opening registration to the public.

## Deploying to the VPS

Currently targets a specific shared box (`checker.norwen.nl`) that already runs another app
(Norwen) — see `deploy/deploy.sh`'s header comment for the assumptions baked in (systemd not PM2,
Postgres on host port 5434 since 5432/5433 are taken, reuses an existing `*.norwen.nl` wildcard
cert instead of running certbot).

```bash
export VPS_HOST=85.17.151.90
export VPS_USER=root
export SSH_KEY=~/.ssh/id_ed25519
export ANTHROPIC_API_KEY=sk-ant-...  # optional, only needed on first deploy

./deploy/setup_vps.sh   # run this on the VPS once (or ssh in and run it manually) — mostly a
                         # no-op if Docker/nginx/python3-venv are already present
./deploy/deploy.sh      # run this locally — syncs code, installs deps, configures nginx+systemd
```

Notes:
- `db/init.sql` only runs on first container creation (empty Postgres volume). Schema changes on
  redeploy need a manual `docker compose exec db psql ...` or a volume reset.
- The app runs under **systemd** (`deploy/resumechecker.service`), not PM2 or Docker — matches the
  existing convention on this box. Debug with `journalctl -u resumechecker -f`.
- `deploy.sh` won't overwrite an existing `.env` on the box unless you export `ANTHROPIC_API_KEY`
  locally before running it, so a key set directly on the server via SSH survives redeploys.
- After any deploy that touches nginx config, check the other app on the box still works:
  `curl -I https://norwen.nl` and `curl -I https://demo.norwen.nl`.

## Architecture

- FastAPI + SQLAlchemy (async) + asyncpg + pgvector
- Embeddings: local `sentence-transformers` (`all-MiniLM-L6-v2`, 384-dim) — no external API needed
- Claude API for analysis/generation (`app/claude_client.py`, model set via `CLAUDE_MODEL` env var)
- Plain HTML/CSS/JS frontend, served as static files by FastAPI
- Multi-user with email/password auth (bcrypt hashing) and server-side sessions via a signed,
  HttpOnly cookie (Starlette `SessionMiddleware`) — no JWT, no separate auth service needed
