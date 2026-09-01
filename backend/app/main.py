from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.config import settings
from app.routers import auth, generate, jobs, onboarding

app = FastAPI(title="Resume Checker")

app.add_middleware(SessionMiddleware, secret_key=settings.session_secret, same_site="lax")


@app.middleware("http")
async def no_cache_static(request: Request, call_next):
    response = await call_next(request)
    path = request.url.path
    if path.startswith(("/js/", "/css/")) or path.endswith(".html") or path == "/":
        response.headers["Cache-Control"] = "no-cache"
    return response


app.include_router(auth.router)
app.include_router(onboarding.router)
app.include_router(jobs.router)
app.include_router(generate.router)

FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
