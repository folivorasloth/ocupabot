from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...enums import StatusAprovacao
from ...modelos import Aprovacao, Usuario
from ...servicos import agenda, aprovacoes
from ..deps import equipe, qualquer, sessao
from ..esquemas import Aprovar, Motivo
from .agenda import aprovacao_resumo

r = APIRouter(prefix="/aprovacoes", tags=["aprovações"])


@r.get("")
def listar(status: StatusAprovacao = StatusAprovacao.PENDENTE, limite: int = 200, s: Session = Depends(sessao),
           u: Usuario = Depends(qualquer)):
    consulta = select(Aprovacao).where(Aprovacao.status == status)
    consulta = consulta.order_by(Aprovacao.id if status == StatusAprovacao.PENDENTE else Aprovacao.id.desc())
    return [aprovacao_resumo(a, u.perfil) for a in s.scalars(consulta.limit(min(limite, 500)))]


def _ap(s: Session, ap_id: int) -> Aprovacao:
    ap = s.get(Aprovacao, ap_id)
    if ap is None:
        raise HTTPException(404, "não encontrado")
    return ap


@r.post("/{ap_id}/aprovar", summary="Aprova (ou altera e aprova); a resposta ao contato sai pelo worker")
def aprovar(ap_id: int, dados: Aprovar | None = None, s: Session = Depends(sessao), u: Usuario = Depends(equipe)):
    ap = _ap(s, ap_id)
    dados = dados or Aprovar()
    try:
        aprovacoes.aprovar(s, ap, u.id, u.perfil, dados.data, dados.horario)
    except aprovacoes.SemPermissao as e:
        raise HTTPException(403, str(e)) from e
    except agenda.VagaIndisponivel as e:
        raise HTTPException(409, str(e)) from e
    except agenda.OperacaoInvalida as e:
        raise HTTPException(422, str(e)) from e
    return aprovacao_resumo(ap, u.perfil)


@r.post("/{ap_id}/recusar", summary="Recusa: libera a vaga e passa a conversa para a equipe")
def recusar(ap_id: int, dados: Motivo, s: Session = Depends(sessao), u: Usuario = Depends(equipe)):
    ap = _ap(s, ap_id)
    try:
        aprovacoes.recusar(s, ap, u.id, dados.motivo)
    except agenda.OperacaoInvalida as e:
        raise HTTPException(422, str(e)) from e
    return aprovacao_resumo(ap, u.perfil)
