from datetime import timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from ...enums import (
    STATUS_ATIVOS,
    EstadoConversa,
    PcmsoElaboradoPor,
    Perfil,
    StatusAgendamento,
    StatusAprovacao,
    StatusEnvio,
)
from ...integracoes.mensageria import canal
from ...modelos import (
    Agendamento,
    Aprovacao,
    Auditoria,
    Batimento,
    Conversa,
    Empresa,
    LeituraExterna,
    Mensagem,
    Usuario,
)
from ...relogio import agora, hoje
from ...servicos import agenda, parametros
from ..deps import qualquer, sessao

r = APIRouter(tags=["painel"])
ATRASO_MIN = 30  # passou disso sem presença nem falta marcada: a tela Hoje avisa


def _plural(n: int, um: str, varios: str) -> str:
    return f"{n} {um if n == 1 else varios}"


def _alertas_pcmso(s: Session) -> list[dict]:
    """PCMSO das empresas acompanhadas (quem fez preenchido): vencido, vencendo e, quando outra empresa
    elaborou, documento em vigor que não chegou. Só avisa: a recepção cobra."""
    dias = parametros.inteiro(s, "pcmso_alerta_dias")
    vencido = vencendo = sem_documento = 0
    for e in s.scalars(select(Empresa).where(Empresa.ativa.is_(True), Empresa.pcmso_elaborado_por.is_not(None))):
        if e.pcmso_vence_em is not None and e.pcmso_vence_em < hoje():
            vencido += 1
        elif e.pcmso_vence_em is not None and e.pcmso_vence_em <= hoje() + timedelta(days=dias):
            vencendo += 1
        if e.pcmso_elaborado_por == PcmsoElaboradoPor.TERCEIRO and not e.pcmso_recebido:
            sem_documento += 1
    saida = []
    if vencido:
        saida.append({"nivel": "erro", "para": "/cadastros", "texto":
                      f"{_plural(vencido, 'empresa', 'empresas')} com PCMSO vencido: peça o documento novo."})
    if vencendo:
        saida.append({"nivel": "aviso", "para": "/cadastros", "texto":
                      f"{_plural(vencendo, 'empresa', 'empresas')} com PCMSO vencendo nos próximos {dias} dias."})
    if sem_documento:
        saida.append({"nivel": "aviso", "para": "/cadastros", "texto":
                      f"{_plural(sem_documento, 'empresa ainda não mandou', 'empresas ainda não mandaram')} "
                      "o PCMSO em vigor."})
    return saida


def _atrasados(s: Session) -> int:
    limite = agora() - timedelta(minutes=ATRASO_MIN)
    if limite.date() < hoje():  # logo depois da meia-noite ninguém de hoje está atrasado
        return 0
    return s.scalar(select(func.count(Agendamento.id)).where(
        Agendamento.data == hoje(), Agendamento.status.in_(STATUS_ATIVOS),
        Agendamento.horario <= limite.time())) or 0


def _alertas(s: Session, u: Usuario) -> list[dict]:
    alertas = []
    b = s.get(Batimento, "worker")
    if b is None or agora() - b.em > timedelta(minutes=5):
        alertas.append({"nivel": "erro", "texto": "O worker não deu sinal de vida nos últimos 5 minutos."})
    if agenda.integracao_externa_ativa() and not agenda.leitura_externa_valida(s):
        alertas.append({"nivel": "erro", "texto": "Leitura da agenda externa inválida: o bot passa tudo à equipe."})
    falhas = s.scalar(select(func.count(Mensagem.id)).where(
        Mensagem.status.in_([StatusEnvio.FALHOU, StatusEnvio.EXPIRADA]), Mensagem.em >= agora() - timedelta(days=1)))
    if falhas:
        alertas.append({"nivel": "aviso", "para": "/conversas", "texto":
                        f"{_plural(falhas, 'mensagem não saiu', 'mensagens não saíram')} nas últimas 24 h."})
    antigas = s.scalar(select(func.count(Aprovacao.id)).where(
        Aprovacao.status == StatusAprovacao.PENDENTE, Aprovacao.criado_em <= agora() - timedelta(hours=2)))
    if antigas:
        alertas.append({"nivel": "aviso", "para": "/aprovacoes", "texto":
                        f"{_plural(antigas, 'pedido', 'pedidos')} esperando aprovação há mais de 2 h."})
    vencidas = s.scalar(select(func.count(Aprovacao.id)).where(
        Aprovacao.status == StatusAprovacao.EXPIRADA, Aprovacao.decidida_em >= agora() - timedelta(days=1)))
    if vencidas:
        alertas.append({"nivel": "aviso", "para": "/aprovacoes", "texto":
                        f"{_plural(vencidas, 'proposta de horário venceu', 'propostas de horário venceram')} "
                        "sem resposta nas últimas 24 h: fale com a pessoa."})
    atrasados = _atrasados(s)
    if atrasados:
        alertas.append({"nivel": "aviso", "texto":
                        f"{_plural(atrasados, 'agendamento passou', 'agendamentos passaram')} do horário sem "
                        "presença nem falta marcada."})
    alertas.extend(_alertas_pcmso(s))
    if u.perfil == Perfil.ADMIN:
        recusas = s.scalar(select(func.count(Auditoria.id)).where(
            Auditoria.entidade == "seguranca", Auditoria.em >= agora() - timedelta(days=1)))
        if recusas > parametros.inteiro(s, "alerta_seguranca_limite"):
            alertas.append({"nivel": "erro", "para": "/auditoria", "texto":
                            f"{recusas} tentativas de acesso recusadas nas últimas 24 h (login ou webhook). "
                            "Veja a auditoria."})
    if not parametros.ligado(s, "envios_automaticos"):
        alertas.append({"nivel": "info", "texto": "Envios automáticos (lembretes e avisos) estão desligados."})
    return alertas


def _contadores(s: Session) -> dict:
    return {
        "aprovacoes_pendentes": s.scalar(select(func.count(Aprovacao.id))
                                         .where(Aprovacao.status == StatusAprovacao.PENDENTE)),
        "esperando_cliente": s.scalar(select(func.count(Aprovacao.id))
                                      .where(Aprovacao.status == StatusAprovacao.AGUARDANDO_CLIENTE)),
        "conversas_esperando": s.scalar(select(func.count(Conversa.id))
                                        .where(Conversa.estado == EstadoConversa.AGUARDANDO_HUMANO)),
        "conversas_com_equipe": s.scalar(select(func.count(Conversa.id))
                                         .where(Conversa.estado == EstadoConversa.HUMANO)),
    }


@r.get("/painel/contadores", summary="Números do menu: pedidos e conversas esperando a equipe")
def contadores(s: Session = Depends(sessao), _: Usuario = Depends(qualquer)):
    return _contadores(s)


@r.get("/painel/hoje", summary="Tela inicial: contadores do dia e alertas")
def hoje_(s: Session = Depends(sessao), u: Usuario = Depends(qualquer)):
    d = hoje()
    por_status = dict(s.execute(select(Agendamento.status, func.count(Agendamento.id))
                                .where(Agendamento.data == d).group_by(Agendamento.status)).all())
    return {
        "data": d.isoformat(),
        "agendamentos": {k.value: v for k, v in por_status.items()},
        **_contadores(s),
        "proximos_7_dias": s.scalar(select(func.count(Agendamento.id)).where(
            Agendamento.data.between(d, d + timedelta(days=7)),
            Agendamento.status.in_([StatusAgendamento.AGENDADO, StatusAgendamento.CONFIRMADO]))),
        "alertas": _alertas(s, u),
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
def indicadores(s: Session = Depends(sessao), _: Usuario = Depends(qualquer)):
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
            "taxa_falta": round(faltas / (faltas + compareceu), 3) if faltas + compareceu else None}
