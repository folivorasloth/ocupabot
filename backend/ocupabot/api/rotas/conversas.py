from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from ...enums import EstadoConversa, Perfil, TipoContato
from ...modelos import Conversa, Mensagem, Usuario
from ...servicos import auditoria, conversas
from ..deps import equipe, qualquer, sessao
from ..esquemas import Responder

r = APIRouter(prefix="/conversas", tags=["conversas"])


def _resumo(c: Conversa, perfil: Perfil, ultima: str | None = None) -> dict:
    return {
        "id": c.id, "estado": c.estado.value, "fluxo": c.fluxo, "etapa": c.etapa,
        "motivo_humano": c.motivo_humano, "atendente_id": c.atendente_id,
        "ultima_entrada_em": c.ultima_entrada_em and c.ultima_entrada_em.isoformat(),
        "contato": {
            "id": c.contato.id, "nome": c.contato.nome, "tipo": c.contato.tipo.value,
            "telefone": c.contato.telefone if perfil != Perfil.LEITURA else "***" + c.contato.telefone[-4:],
            "empresa": c.contato.empresa and (c.contato.empresa.nome_fantasia or c.contato.empresa.razao_social),
            "optout": c.contato.optout_em is not None,
        },
        "ultima_mensagem": ultima if perfil != Perfil.LEITURA else None,
        "empresa_informada": (c.dados or {}).get("empresa_id"),
    }


@r.get("")
def listar(estado: EstadoConversa | None = None, s: Session = Depends(sessao), u: Usuario = Depends(qualquer)):
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
    return [_resumo(c, u.perfil, ultimas.get(c.id)) for c in lista]


def _conv(s: Session, c_id: int) -> Conversa:
    c = s.get(Conversa, c_id)
    if c is None:
        raise HTTPException(404, "não encontrada")
    return c


@r.get("/{c_id}")
def ler(c_id: int, s: Session = Depends(sessao), u: Usuario = Depends(qualquer)):
    c = _conv(s, c_id)
    dados = _resumo(c, u.perfil)
    if u.perfil == Perfil.LEITURA:
        dados["mensagens"] = []  # perfil de consulta não lê mensagens
        return dados
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
    return _resumo(c, u.perfil)


@r.post("/{c_id}/devolver", summary="Devolve a conversa para o bot")
def devolver(c_id: int, s: Session = Depends(sessao), u: Usuario = Depends(equipe)):
    c = _conv(s, c_id)
    conversas.devolver(s, c, u.id)
    return _resumo(c, u.perfil)


@r.post("/{c_id}/responder", summary="Resposta da equipe (o envio é feito pelo worker)")
def responder(c_id: int, dados: Responder, s: Session = Depends(sessao), u: Usuario = Depends(equipe)):
    c = _conv(s, c_id)
    m = conversas.responder(s, c, dados.texto, u.id)
    return {"id": m.id, "status": m.status.value}


@r.post("/{c_id}/confirmar-rh", summary="Confirma o número como RH da empresa informada ao bot")
def confirmar_rh(c_id: int, empresa_id: int, s: Session = Depends(sessao), u: Usuario = Depends(equipe)):
    c = _conv(s, c_id)
    antes = auditoria.foto(c.contato)
    c.contato.tipo = TipoContato.RH
    c.contato.empresa_id = empresa_id
    auditoria.registrar(s, "contato", c.contato.id, "confirmar_rh", antes, auditoria.foto(c.contato), u.id, "painel")
    return _resumo(c, u.perfil)
