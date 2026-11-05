"""Worker: tudo o que roda sozinho. Cada etapa tem sessão e try próprios — uma falha não para as outras."""

from __future__ import annotations

import logging
import time as _time
from collections.abc import Callable

from sqlalchemy.orm import Session

from . import db
from .integracoes.agenda_externa import agenda_externa
from .integracoes.mensageria import canal
from .modelos import Batimento
from .relogio import agora
from .servicos import conversas, externo, notificacoes

log = logging.getLogger("ocupabot.worker")


def _leitura_externa(s: Session) -> object:
    fonte = agenda_externa()
    if fonte is None:
        return "desligada"
    leitura = externo.sincronizar(s, fonte)
    return "ok" if leitura.ok else leitura.erro


ETAPAS: list[tuple[str, Callable[[Session], object]]] = [
    ("agenda_externa", _leitura_externa),
    ("notificacoes", notificacoes.processar),
    ("envios", lambda s: conversas.enviar_pendentes(s, canal())),
]


def rodada() -> dict[str, str]:
    resultado = {}
    for nome, etapa in ETAPAS:
        try:
            with db.sessao() as s:
                resultado[nome] = str(etapa(s))
        except Exception as e:  # noqa: BLE001
            log.exception("etapa %s falhou", nome)
            resultado[nome] = f"ERRO {type(e).__name__}"
    with db.sessao() as s:
        b = s.get(Batimento, "worker") or Batimento(nome="worker", em=agora())
        b.em = agora()
        b.detalhe = "; ".join(f"{k}={v}" for k, v in resultado.items())[:1000]
        s.merge(b)
    return resultado


def main(intervalo: int = 60) -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    log.info("worker iniciado (intervalo %ss)", intervalo)
    while True:
        rodada()
        _time.sleep(intervalo)


if __name__ == "__main__":
    main()
