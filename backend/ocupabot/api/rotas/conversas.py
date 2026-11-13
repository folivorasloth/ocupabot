from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from ...enums import AGENDA_PELA_EMPRESA, EstadoConversa, TipoContato
from ...modelos import Conversa, Empresa, Mensagem, Usuario
from ...servicos import contatos, conversas
from ..deps import equipe, qualquer, sessao
from ..esquemas import Responder

r = APIRouter(prefix="/conversas", tags=["conversas"])


def _resumo(c: Conversa, ultima: str | None = None) -> dict:
    return {
        "id": c.id, "estado": c.estado.value, "fluxo": c.fluxo, "etapa": c.etapa,
        "motivo_humano": c.motivo_humano, "atendente_id": c.atendente_id, "simulada": c.simulada,
        "ultima_entrada_em": c.ultima_entrada_em and c.ultima_entrada_em.isoformat(),
        "contato": {
            "id": c.contato.id, "nome": c.contato.nome, "tipo": c.contato.tipo.value,
            "telefone": c.contato.telefone,
            "empresa": c.contato.empresa and (c.contato.empresa.nome_fantasia or c.contato.empresa.razao_social),
            "empresas_ids": c.contato.empresas_ids,
            "optout": c.contato.optout_em is not None,
        },
        "ultima_mensagem": ultima,
        "empresa_informada": (c.dados or {}).get("empresa_id"),
    }


@r.get("")
def listar(estado: EstadoConversa | None = None, s: Session = Depends(sessao), _: Usuario = Depends(qualquer)):
    consulta = select(Conversa).options(selectinload(Conversa.contato))
    if estado:
        consulta = consulta.where(Conversa.estado == estado)
    consulta = consulta.order_by(Conversa.ultima_entrada_em.desc().nulls_last()).limit(300)
    lista = list(s.scalars(consulta))
    ultimas = {}
    if lista:
        sub = (select(Mensagem.conversa_id, func.max(Mensagem.id))
               .where(Mensagem.conversa_id.in_([c.id for c in lista])).group_by(Mensagem.conversa_id))
        ids = [m for _, m in s.execute(sub)]
        ultimas = {m.conversa_id: m.texto[:120] for m in s.scalars(select(Mensagem).where(Mensagem.id.in_(ids)))}
    return [_resumo(c, ultimas.get(c.id)) for c in lista]


def _conv(s: Session, c_id: int) -> Conversa:
    c = s.get(Conversa, c_id) if c_id < 2**63 else None
    if c is None:
        raise HTTPException(404, "não encontrada")
    return c


@r.get("/{c_id}")
def ler(c_id: int, s: Session = Depends(sessao), _: Usuario = Depends(qualquer)):
    c = _conv(s, c_id)
    dados = _resumo(c)
    msgs = s.scalars(select(Mensagem).where(Mensagem.conversa_id == c.id).order_by(Mensagem.id.desc()).limit(300))
    dados["mensagens"] = [
        {"id": m.id, "autor": m.autor.value, "texto": m.texto, "status": m.status.value, "em": m.em.isoformat(),
         "erro": m.erro}
        for m in reversed(list(msgs))
    ]
    return dados


@r.post("/{c_id}/assumir", summary="A equipe assume: o bot para de responder")
def assumir(c_id: int, s: Session = Depends(sessao), u: Usuario = Depends(equipe)):
    c = _conv(s, c_id)
    conversas.assumir(s, c, u.id)
    return _resumo(c)


@r.post("/{c_id}/devolver", summary="Devolve a conversa para o bot")
def devolver(c_id: int, s: Session = Depends(sessao), u: Usuario = Depends(equipe)):
    c = _conv(s, c_id)
    conversas.devolver(s, c, u.id)
    return _resumo(c)


@r.post("/{c_id}/responder", summary="Resposta da equipe (o envio é feito pelo worker)")
def responder(c_id: int, dados: Responder, s: Session = Depends(sessao), u: Usuario = Depends(equipe)):
    c = _conv(s, c_id)
    try:
        m = conversas.responder(s, c, dados.texto, u.id)
    except conversas.SemDestinatario as e:
        raise HTTPException(409, str(e)) from e
    return {"id": m.id, "status": m.status.value}


@r.post("/{c_id}/confirmar-rh", summary="Confirma o número como quem agenda pela empresa (RH por padrão)")
def confirmar_rh(c_id: int, empresa_id: int, tipo: TipoContato = TipoContato.RH, s: Session = Depends(sessao),
                 u: Usuario = Depends(equipe)):
    c = _conv(s, c_id)
    empresa = s.get(Empresa, empresa_id) if empresa_id < 2**63 else None
    if empresa is None or tipo not in AGENDA_PELA_EMPRESA:
        raise HTTPException(422, "empresa ou tipo inválido")
    contatos.vincular(s, c.contato, empresa, u.id, tipo)
    return _resumo(c)
