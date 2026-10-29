from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.router import router
from app.core.config import settings

app = FastAPI(title="Acompañamiento IT", version="0.1.0")


@app.middleware("http")
async def require_trusted_origin(request: Request, call_next):
    if (
        request.url.path.startswith("/api/v1/auth/")
        and request.method in {"POST", "PUT", "PATCH", "DELETE"}
        and request.headers.get("origin") not in {settings.frontend_origin, settings.backend_origin}
    ):
        return JSONResponse({"detail": "Origen no permitido."}, status_code=403)
    return await call_next(request)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)
