from datetime import timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from ...enums import EstadoConversa, Perfil, StatusAgendamento, StatusAprovacao, StatusEnvio
from ...integracoes.mensageria import canal
from ...modelos import Agendamento, Aprovacao, Batimento, Conversa, LeituraExterna, Mensagem, Usuario
from ...relogio import agora, hoje
from ...servicos import agenda, parametros
from ..deps import qualquer, sessao

r = APIRouter(tags=["painel"])


def _alertas(s: Session) -> list[dict]:
    alertas = []
    b = s.get(Batimento, "worker")
    if b is None or agora() - b.em > timedelta(minutes=5):
        alertas.append({"nivel": "erro", "texto": "O worker não deu sinal de vida nos últimos 5 minutos."})
    if agenda.integracao_externa_ativa() and not agenda.leitura_externa_valida(s):
        alertas.append({"nivel": "erro", "texto": "Leitura da agenda externa inválida: o bot passa tudo à equipe."})
    falhas = s.scalar(select(func.count(Mensagem.id)).where(
        Mensagem.status.in_([StatusEnvio.FALHOU, StatusEnvio.EXPIRADA]), Mensagem.em >= agora() - timedelta(days=1)))
    if falhas:
        alertas.append({"nivel": "aviso", "texto": f"{falhas} mensagem(ns) não saíram nas últimas 24 h."})
    antigas = s.scalar(select(func.count(Aprovacao.id)).where(
        Aprovacao.status == StatusAprovacao.PENDENTE, Aprovacao.criado_em <= agora() - timedelta(hours=2)))
    if antigas:
        alertas.append({"nivel": "aviso", "texto": f"{antigas} pedido(s) esperando aprovação há mais de 2 h."})
    if not parametros.ligado(s, "envios_automaticos"):
        alertas.append({"nivel": "info", "texto": "Envios automáticos (lembretes e avisos) estão desligados."})
    return alertas


@r.get("/painel/hoje", summary="Tela inicial: contadores do dia e alertas")
def hoje_(s: Session = Depends(sessao), _: Usuario = Depends(qualquer)):
    d = hoje()
    por_status = dict(s.execute(select(Agendamento.status, func.count(Agendamento.id))
                                .where(Agendamento.data == d).group_by(Agendamento.status)).all())
    return {
        "data": d.isoformat(),
        "agendamentos": {k.value: v for k, v in por_status.items()},
        "aprovacoes_pendentes": s.scalar(select(func.count(Aprovacao.id))
                                         .where(Aprovacao.status == StatusAprovacao.PENDENTE)),
        "conversas_esperando": s.scalar(select(func.count(Conversa.id))
                                        .where(Conversa.estado == EstadoConversa.AGUARDANDO_HUMANO)),
        "conversas_com_equipe": s.scalar(select(func.count(Conversa.id))
                                         .where(Conversa.estado == EstadoConversa.HUMANO)),
        "proximos_7_dias": s.scalar(select(func.count(Agendamento.id)).where(
            Agendamento.data.between(d, d + timedelta(days=7)),
            Agendamento.status.in_([StatusAgendamento.AGENDADO, StatusAgendamento.CONFIRMADO]))),
        "alertas": _alertas(s),
    }


@r.get("/saude", summary="App, banco, worker, WhatsApp e agenda externa")
def saude(s: Session = Depends(sessao)):
    s.execute(text("SELECT 1"))
    b = s.get(Batimento, "worker")
    ultima = s.scalars(select(LeituraExterna).order_by(LeituraExterna.id.desc()).limit(1)).first()
    return {
        "app": "ok",
        "banco": "ok",
        "worker": b.em.isoformat() if b else None,
        "worker_ok": bool(b and agora() - b.em <= timedelta(minutes=5)),
        "whatsapp": canal().status(),
        "agenda_externa": None if ultima is None else {"ok": ultima.ok, "em": ultima.concluida_em
                                                       and ultima.concluida_em.isoformat()},
    }


@r.get("/painel/indicadores", summary="Indicadores simples dos últimos 30 dias")
def indicadores(s: Session = Depends(sessao), u: Usuario = Depends(qualquer)):
    de = hoje() - timedelta(days=30)
    linhas = s.execute(select(Agendamento.origem, Agendamento.status, func.count(Agendamento.id))
                       .where(Agendamento.data.between(de, hoje())).group_by(Agendamento.origem, Agendamento.status))
    por_origem: dict[str, dict[str, int]] = {}
    for origem, status, n in linhas:
        por_origem.setdefault(origem.value, {})[status.value] = n
    total = sum(sum(v.values()) for v in por_origem.values())
    faltas = sum(v.get("FALTOU", 0) for v in por_origem.values())
    compareceu = sum(v.get("COMPARECEU", 0) for v in por_origem.values())
    return {"de": de.isoformat(), "ate": hoje().isoformat(), "por_origem": por_origem, "total": total,
            "taxa_falta": round(faltas / (faltas + compareceu), 3) if faltas + compareceu else None,
            "perfil": u.perfil.value if u.perfil else Perfil.LEITURA.value}
