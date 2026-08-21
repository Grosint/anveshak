"""Anveshak API — FastAPI application entrypoint."""

import asyncio
from contextlib import asynccontextmanager

import httpx
import structlog
from anveshak.logging import configure_logging
from anveshak.tracing import configure_tracing

configure_logging("api")
configure_tracing("api")
from arq import create_pool as arq_create_pool
from arq.connections import RedisSettings
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import make_asgi_app

from .db.pool import close_pool, create_pool
from .metrics import REGISTRY as API_REGISTRY
from .middleware.rate_limit import RateLimitMiddleware
from .middleware.security import SecurityHeadersMiddleware
from .routes import auth, content, health, signals, sources, topics
from .routes.alerts import router as alerts_router
from .routes.assessments import router as assessments_router
from .routes.catalog import router as catalog_router
from .routes.export import router as export_router
from .routes.geocoded_locations import router as geocoded_locations_router
from .routes.identifiers import router as identifiers_router
from .routes.intelligence import router as intelligence_router
from .routes.organizations import router as organizations_router
from .routes.provenance import router as provenance_router
from .routes.reports import router as reports_router
from .routes.system import router as system_router
from .routes.templates import router as templates_router
from .routes.tipline import router as tipline_router
from .routes.trackers import router as trackers_router
from .routes.users import router as users_router
from .routes.vision import content_vision_router
from .routes.vision import router as vision_router
from .settings import settings
from .signal_delivery import signal_delivery_loop

log = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle."""
    # Startup
    log.info("anveshak_api.starting")
    app.state.db_pool = await create_pool()

    # ARQ pool — vision routes dispatch run_vision_analysis jobs via this
    app.state.arq_pool = await arq_create_pool(RedisSettings.from_dsn(settings.redis_url))

    # Pre-warm Ollama (prevents cold-start during demo)
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            await client.post(
                f"{settings.ollama_host}/api/generate",
                json={
                    "model": settings.ollama_cluster_model,
                    "prompt": "OK",
                    "stream": False,
                    "options": {"num_predict": 1},
                },
            )
        log.info("ollama.warmed", model=settings.ollama_cluster_model)
    except Exception as e:
        log.warning("ollama.warmup_failed", error=str(e))

    # Start signal delivery loop — polls DB for undelivered signals and
    # pushes them to connected WebSocket sessions (criteria 2.18, 2.29).
    delivery_task = asyncio.create_task(
        signal_delivery_loop(app.state.db_pool, signals.broadcast_signal)
    )
    log.info("anveshak_api.ready")
    yield

    # Shutdown
    delivery_task.cancel()
    try:
        await delivery_task
    except asyncio.CancelledError:
        pass
    await app.state.arq_pool.close()
    await close_pool()
    log.info("anveshak_api.stopped")


app = FastAPI(
    title="Anveshak OSINT API",
    description="AI-powered Open Source Intelligence Analysis Platform",
    version="1.0.0",
    lifespan=lifespan,
)

# 8D.5–8D.6 — Security headers + structured request logging
# Note: middleware is applied in LIFO order — SecurityHeaders wraps everything,
# RateLimit runs inside it so the 429 response still gets security headers.
app.add_middleware(SecurityHeadersMiddleware)

# 8D.1–8D.4 — Rate limiting (in-memory sliding window)
app.add_middleware(RateLimitMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Api-Key", "X-Org-Id"],
)

# Routes
app.include_router(health.router)
app.include_router(auth.router)
app.include_router(topics.router)
app.include_router(sources.router)
app.include_router(signals.router)
app.include_router(content.router)
app.include_router(vision_router)  # Phase 4: vision analysis + pHash search
app.include_router(content_vision_router)  # Phase 4: GET /api/v1/content/{id}/vision
app.include_router(reports_router)  # Phase 5: report generation + GeoJSON
app.include_router(export_router)  # CSV/JSON export for content, signals, entities
app.include_router(intelligence_router)  # Entity graph, topic similarity, source discovery
app.include_router(system_router)  # Pipeline health metrics for make validate
app.include_router(users_router)  # User management CRUD
app.include_router(catalog_router)  # Source catalog + discovery
app.include_router(organizations_router)  # Organization management (super-admin)
app.include_router(identifiers_router)  # Engine C: identifier search, clusters, export
app.include_router(tipline_router)  # Engine C: citizen tipline ingest
app.include_router(templates_router)  # Engine C: scam template CRUD
app.include_router(trackers_router)  # Trackers: persistent analyst case files
app.include_router(alerts_router)  # Keyword alert rules for social monitoring
app.include_router(assessments_router)  # Source Assessment: topic-scoped source intelligence cards
app.include_router(
    geocoded_locations_router
)  # Phase 1 map upgrade: geocoded locations + analyst override
app.include_router(provenance_router)  # Issue #7: intelligence view + provenance chains

# Prometheus metrics endpoint — uses isolated registry (API_REGISTRY) so custom
# api_* metrics are exposed alongside default process metrics.
metrics_app = make_asgi_app(registry=API_REGISTRY)
app.mount("/metrics", metrics_app)
