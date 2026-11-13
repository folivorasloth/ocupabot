from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...enums import StatusAprovacao
from ...modelos import Aprovacao, Usuario
from ...servicos import agenda, aprovacoes
from ..deps import equipe, qualquer, sessao
from ..esquemas import MotivoOpcional, Remarcar
from .agenda import aprovacao_resumo

r = APIRouter(prefix="/aprovacoes", tags=["aprovações"])
ESPERANDO = (StatusAprovacao.PENDENTE, StatusAprovacao.AGUARDANDO_CLIENTE)


@r.get("")
def listar(status: StatusAprovacao = StatusAprovacao.PENDENTE, limite: int = 200, s: Session = Depends(sessao),
           _: Usuario = Depends(qualquer)):
    consulta = select(Aprovacao).where(Aprovacao.status == status)
    consulta = consulta.order_by(Aprovacao.id if status in ESPERANDO else Aprovacao.id.desc())
    return [aprovacao_resumo(s, a) for a in s.scalars(consulta.limit(max(1, min(limite, 500))))]


def _ap(s: Session, ap_id: int) -> Aprovacao:
    ap = s.get(Aprovacao, ap_id) if ap_id < 2**63 else None
    if ap is None:
        raise HTTPException(404, "não encontrado")
    return ap


def _executar(fn):
    try:
        return fn()
    except aprovacoes.SemPermissao as e:
        raise HTTPException(403, str(e)) from e
    except agenda.VagaIndisponivel as e:
        raise HTTPException(409, str(e)) from e
    except agenda.OperacaoInvalida as e:
        raise HTTPException(422, str(e)) from e


@r.post("/{ap_id}/aprovar", summary="Aprova o pedido como veio; a resposta ao contato sai pelo worker")
def aprovar(ap_id: int, s: Session = Depends(sessao), u: Usuario = Depends(equipe)):
    ap = _ap(s, ap_id)
    _executar(lambda: aprovacoes.aprovar(s, ap, u.id, u.perfil))
    return aprovacao_resumo(s, ap)


@r.post("/{ap_id}/propor", summary="Propõe outro horário: a vaga fica segura e a pessoa responde 1 ou 2")
def propor(ap_id: int, dados: Remarcar, s: Session = Depends(sessao), u: Usuario = Depends(equipe)):
    ap = _ap(s, ap_id)
    _executar(lambda: aprovacoes.propor(s, ap, u.id, u.perfil, dados.data, dados.horario))
    return aprovacao_resumo(s, ap)


@r.post("/{ap_id}/cancelar-proposta", summary="Desiste da proposta: libera a vaga e a conversa volta à equipe")
def cancelar_proposta(ap_id: int, s: Session = Depends(sessao), u: Usuario = Depends(equipe)):
    ap = _ap(s, ap_id)
    _executar(lambda: aprovacoes.cancelar_proposta(s, ap, u.id))
    return aprovacao_resumo(s, ap)


@r.post("/{ap_id}/recusar", summary="Recusa: libera a vaga e passa a conversa para a equipe")
def recusar(ap_id: int, dados: MotivoOpcional | None = None, s: Session = Depends(sessao),
            u: Usuario = Depends(equipe)):
    ap = _ap(s, ap_id)
    _executar(lambda: aprovacoes.recusar(s, ap, u.id, dados.motivo if dados else None))
    return aprovacao_resumo(s, ap)
