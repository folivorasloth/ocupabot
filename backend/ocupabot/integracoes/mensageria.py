"""Canal de mensagens (porta). O bot não sabe qual WhatsApp está do outro lado.

Trocar o WAHA pela API oficial é escrever outra classe com `enviar()` e `status()`.
"""

from __future__ import annotations

import logging
from typing import Protocol

import httpx

from ..config import Config, config

log = logging.getLogger("ocupabot.canal")


class ErroEnvio(Exception):
    pass


class Canal(Protocol):
    def enviar(self, telefone: str, texto: str) -> str | None: ...

    def status(self) -> str: ...


class CanalConsole:
    """Desenvolvimento: só registra no log. Guarda o que 'enviou' para os testes."""

    def __init__(self) -> None:
        self.enviadas: list[tuple[str, str]] = []

    def enviar(self, telefone: str, texto: str) -> str | None:
        self.enviadas.append((telefone, texto))
        log.info("[console] -> %s: %s", telefone[-4:], texto.replace("\n", " | ")[:200])
        return None

    def status(self) -> str:
        return "CONSOLE"


class CanalWaha:
    """WAHA (WhatsApp HTTP API). Integração NÃO oficial: o número pode ser bloqueado."""

    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg
        headers = {"X-Api-Key": cfg.waha_api_key} if cfg.waha_api_key else {}
        self.http = httpx.Client(base_url=cfg.waha_url, headers=headers, timeout=15)

    def enviar(self, telefone: str, texto: str) -> str | None:
        try:
            r = self.http.post("/api/sendText", json={
                "session": self.cfg.waha_sessao, "chatId": f"{telefone}@c.us", "text": texto,
            })
        except httpx.HTTPError as e:
            raise ErroEnvio(f"falha de conexão: {type(e).__name__}") from e
        if r.status_code >= 300:
            raise ErroEnvio(f"WAHA respondeu {r.status_code}")
        try:
            return (r.json().get("id") or {}).get("_serialized")
        except Exception:
            return None

    def status(self) -> str:
        try:
            r = self.http.get(f"/api/sessions/{self.cfg.waha_sessao}")
            return r.json().get("status", "DESCONHECIDO") if r.status_code == 200 else f"HTTP {r.status_code}"
        except Exception as e:  # noqa: BLE001
            return f"ERRO {type(e).__name__}"


_canal: Canal | None = None


def canal() -> Canal:
    global _canal
    if _canal is None:
        cfg = config()
        _canal = CanalWaha(cfg) if cfg.canal == "waha" else CanalConsole()
    return _canal


def definir_canal(c: Canal | None) -> None:
    global _canal
    _canal = c
