"""Leitura periódica da agenda externa para a tabela `ocupacao_externa`."""

from datetime import timedelta

from sqlalchemy import delete
from sqlalchemy.orm import Session

from ..integracoes.agenda_externa import AgendaExterna
from ..modelos import LeituraExterna, OcupacaoExterna
from ..relogio import agora, hoje
from . import agenda, parametros


def sincronizar(s: Session, fonte: AgendaExterna) -> LeituraExterna:
    leitura = LeituraExterna(iniciada_em=agora())
    s.add(leitura)
    ate = hoje() + timedelta(days=parametros.inteiro(s, "prazo_maximo_dias"))
    try:
        compromissos = fonte.ler(hoje(), ate)
    except Exception as e:  # noqa: BLE001 - qualquer falha invalida a leitura
        leitura.erro = f"{type(e).__name__}: {e}"[:500]
        leitura.concluida_em = agora()
        return leitura
    s.execute(delete(OcupacaoExterna))
    for c in compromissos:
        s.add(OcupacaoExterna(data=c.data, horario=c.horario, codigo=c.codigo[:40],
                              cpf_hash=agenda.hash_cpf(c.cpf) if c.cpf else None))
    leitura.ok = True
    leitura.linhas = len(compromissos)
    leitura.ate = ate
    leitura.concluida_em = agora()
    return leitura
