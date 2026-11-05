"""Aplicação FastAPI: API em /api, painel React em /, webhook do WhatsApp."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import APIRouter, FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .. import __version__, db
from ..config import config
from ..seeds import essenciais
from .rotas import acesso, agenda, aprovacoes, bot, cadastros, configuracao, conversas, painel

LIMITE_CORPO = 1_000_000

CABECALHOS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "same-origin",
    "Content-Security-Policy": "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; "
    "frame-ancestors 'none'",
}


def criar_app(inicializar: bool = True) -> FastAPI:
    cfg = config()
    @asynccontextmanager
    async def ciclo(_app: FastAPI):
        if inicializar:
            logging.basicConfig(level=logging.INFO)
            with db.sessao() as s:
                essenciais(s)
        yield

    app = FastAPI(title="OcupaBot", lifespan=ciclo, version=__version__,
                  docs_url="/api/docs" if cfg.docs_ativo else None, redoc_url=None,
                  openapi_url="/api/openapi.json" if cfg.docs_ativo else None)

    @app.middleware("http")
    async def protecao(request: Request, call_next):
        tamanho = request.headers.get("content-length")
        if tamanho and tamanho.isdigit() and int(tamanho) > LIMITE_CORPO:
            return JSONResponse({"detail": "corpo grande demais"}, status_code=413)
        resposta = await call_next(request)
        for k, v in CABECALHOS.items():
            resposta.headers.setdefault(k, v)
        if request.url.path.startswith("/api"):
            resposta.headers.setdefault("Cache-Control", "no-store")
        return resposta

    api = APIRouter(prefix="/api")
    for m in (acesso, agenda, aprovacoes, conversas, configuracao, painel, bot):
        api.include_router(m.r)
    api.include_router(cadastros.r)
    for rr in cadastros.ROTAS:
        api.include_router(rr)
    app.include_router(api)

    dist = Path(cfg.painel_dir)
    if dist.is_dir():
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

        @app.get("/{caminho:path}", include_in_schema=False)
        def painel_spa(caminho: str):
            alvo = (dist / caminho).resolve()
            if caminho and alvo.is_file() and dist.resolve() in alvo.parents:
                return FileResponse(alvo)
            return FileResponse(dist / "index.html")

    return app


app = criar_app()
