"""Aplicação FastAPI: API em /api, painel React em /, webhook do WhatsApp."""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import APIRouter, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .. import __version__, db
from ..bot import rajadas
from ..config import SEGREDOS_PUBLICOS, config
from ..seeds import essenciais
from .deps import COOKIE
from .rotas import acesso, agenda, aprovacoes, bot, cadastros, configuracao, conversas, painel

log = logging.getLogger("ocupabot.app")
LIMITE_CORPO = 1_000_000

CABECALHOS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "same-origin",
    "Content-Security-Policy": "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; "
    "frame-ancestors 'none'",
}
SO_LEITURA = {"GET", "HEAD", "OPTIONS"}


def _de_fora(request: Request) -> bool:
    """Escrita com o cookie do painel só vale vinda do próprio painel (defesa extra ao SameSite=Strict)."""
    if request.method in SO_LEITURA or COOKIE not in request.cookies:
        return False
    if request.headers.get("sec-fetch-site", "same-origin") not in ("same-origin", "none"):
        return True
    origem = request.headers.get("origin")
    return bool(origem) and urlsplit(origem).netloc != request.headers.get("host", "")


async def _laco_rajadas() -> None:
    """Responde, a cada segundo, quem parou de escrever. Uma rodada com problema não derruba o laço."""
    while True:
        await asyncio.sleep(1)
        try:
            await asyncio.to_thread(rajadas.responder_vencidas)
        except Exception as e:  # noqa: BLE001
            log.error("rodada das rajadas falhou: %s", type(e).__name__)


def criar_app(inicializar: bool = True) -> FastAPI:
    cfg = config()
    if inicializar and cfg.segredo in SEGREDOS_PUBLICOS:
        if cfg.canal != "console":
            raise RuntimeError("OCUPABOT_SEGREDO está com o valor publicado no repositório: gere um segredo "
                               "próprio antes de ligar o WhatsApp")
        log.warning("OCUPABOT_SEGREDO com o valor de exemplo: use só em desenvolvimento")

    @asynccontextmanager
    async def ciclo(_app: FastAPI):
        tarefa = None
        if inicializar:
            logging.basicConfig(level=logging.INFO)
            with db.sessao() as s:
                essenciais(s)
            tarefa = asyncio.create_task(_laco_rajadas())
        yield
        if tarefa is not None:
            tarefa.cancel()

    app = FastAPI(title="OcupaBot", lifespan=ciclo, version=__version__,
                  docs_url="/api/docs" if cfg.docs_ativo else None, redoc_url=None,
                  openapi_url="/api/openapi.json" if cfg.docs_ativo else None)

    @app.exception_handler(RequestValidationError)
    async def dados_invalidos(_request: Request, erro: RequestValidationError):
        """Diz qual campo e por quê, sem devolver o valor digitado (pode ser um CPF ou uma senha)."""
        partes = []
        for e in erro.errors()[:5]:
            campo = ".".join(str(x) for x in e.get("loc", ())[1:]) or "dados"
            partes.append(f"{campo}: {str(e.get('msg', 'inválido')).removeprefix('Value error, ')}")
        return JSONResponse({"detail": "; ".join(partes) or "dados inválidos"}, status_code=422)

    @app.middleware("http")
    async def protecao(request: Request, call_next):
        tamanho = request.headers.get("content-length")
        if tamanho and tamanho.isdigit() and int(tamanho) > LIMITE_CORPO:
            return JSONResponse({"detail": "corpo grande demais"}, status_code=413)
        if request.url.path.startswith("/api") and _de_fora(request):
            return JSONResponse({"detail": "pedido vindo de outro site"}, status_code=403)
        resposta = await call_next(request)
        for k, v in CABECALHOS.items():
            resposta.headers.setdefault(k, v)
        if request.url.path.startswith("/api"):
            resposta.headers.setdefault("Cache-Control", "no-store")
        if cfg.cookie_seguro:  # atrás de proxy HTTPS
            resposta.headers.setdefault("Strict-Transport-Security", "max-age=31536000")
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
