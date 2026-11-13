from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ...dominio.documentos import cpf_valido, mascarar_cpf, so_digitos
from ...dominio.texto import normalizar_telefone
from ...enums import APROVACAO_EM_ABERTO, Origem, Perfil, StatusAgendamento
from ...modelos import Agendamento, Aprovacao, ItemAgendamento, Paciente, Usuario
from ...relogio import hoje
from ...servicos import agenda, aprovacoes, auditoria, conversas
from ..deps import equipe, qualquer, sessao
from ..esquemas import AgendamentoNovo, Motivo, Remarcar

r = APIRouter(tags=["agenda"])


def resumo(ag: Agendamento) -> dict:
    return {
        "id": ag.id,
        "data": ag.data.isoformat(),
        "horario": ag.horario.strftime("%H:%M"),
        "turno": ag.turno.value,
        "status": ag.status.value,
        "origem": ag.origem.value,
        "paciente": {"id": ag.paciente_id, "nome": ag.paciente.nome, "cpf": mascarar_cpf(ag.paciente.cpf)},
        "empresa": ag.empresa and (ag.empresa.nome_fantasia or ag.empresa.razao_social),
        "empresa_id": ag.empresa_id,
        "tipo_aso": ag.tipo_aso and ag.tipo_aso.nome,
        "contato": ag.contato and ag.contato.telefone,
        "contato_nome": ag.contato and ag.contato.nome,
        "sem_aviso": ag.contato is None or ag.contato.optout_em is not None,  # ninguém recebe mensagem
        "exames": [
            {"id": i.exame_id, "nome": i.exame.nome, "profissional": i.profissional and i.profissional.nome}
            for i in ag.itens
        ],
        "remarcado_de_id": ag.remarcado_de_id,
        "motivo_cancelamento": ag.motivo_cancelamento,
        "observacao": ag.observacao,
        "no_sistema_externo": ag.no_sistema_externo,
    }


def _opcoes():
    return [
        selectinload(Agendamento.paciente), selectinload(Agendamento.empresa), selectinload(Agendamento.tipo_aso),
        selectinload(Agendamento.contato),
        selectinload(Agendamento.itens).selectinload(ItemAgendamento.exame),
        selectinload(Agendamento.itens).selectinload(ItemAgendamento.profissional),
    ]


@r.get("/agenda", summary="Agendamentos de um período")
def listar(de: date | None = None, ate: date | None = None, status: str | None = None,
           s: Session = Depends(sessao), _: Usuario = Depends(qualquer)):
    de = de or hoje()
    ate = ate or de
    if (ate - de).days > 62:
        raise HTTPException(422, "período máximo de 62 dias")
    consulta = select(Agendamento).where(Agendamento.data.between(de, ate)).options(*_opcoes())
    if status:
        pedidos = status.split(",")
        if any(p not in StatusAgendamento.__members__ for p in pedidos):
            raise HTTPException(422, "status inválido")  # sem repetir o valor recebido
        consulta = consulta.where(Agendamento.status.in_(pedidos))
    consulta = consulta.order_by(Agendamento.data, Agendamento.horario, Agendamento.id)
    return [resumo(a) for a in s.scalars(consulta)]


@r.get("/agendamentos/{ag_id}")
def ler(ag_id: int, s: Session = Depends(sessao), _: Usuario = Depends(qualquer)):
    return resumo(_alvo(s, ag_id))


def _executar(fn):
    try:
        return fn()
    except agenda.VagaIndisponivel as e:
        raise HTTPException(409, str(e)) from e
    except agenda.OperacaoInvalida as e:
        raise HTTPException(422, str(e)) from e


@r.post("/agendamentos", status_code=201)
def criar(dados: AgendamentoNovo, s: Session = Depends(sessao), u: Usuario = Depends(equipe)):
    if dados.forcar and u.perfil not in (Perfil.ADMIN, Perfil.SUPERVISAO):
        raise HTTPException(403, "encaixe fora da vaga exige a Supervisão")
    if dados.paciente_id:
        pac = s.get(Paciente, dados.paciente_id)
        if pac is None:
            raise HTTPException(404, "paciente não encontrado")
    else:
        if not dados.paciente_nome:
            raise HTTPException(422, "informe o paciente")
        cpf = so_digitos(dados.paciente_cpf or "") or None
        if cpf and not cpf_valido(cpf):
            raise HTTPException(422, "CPF inválido")
        pac = s.scalar(select(Paciente).where(Paciente.cpf == cpf)) if cpf else None
        if pac is None:
            pac = Paciente(nome=dados.paciente_nome.strip(), cpf=cpf, nascimento=dados.paciente_nascimento,
                           empresa_id=dados.empresa_id)
            s.add(pac)
            s.flush()
    contato_id = None
    if dados.contato_telefone:
        telefone = normalizar_telefone(dados.contato_telefone)
        if not 12 <= len(telefone) <= 13:
            raise HTTPException(422, "telefone incompleto: informe DDD e número")
        contato_id = conversas.contato(s, telefone).id
    ag = _executar(lambda: agenda.criar(
        s, paciente_id=pac.id, exame_ids=dados.exame_ids, data=dados.data, horario=dados.horario,
        origem=Origem.PAINEL, empresa_id=dados.empresa_id or pac.empresa_id, contato_id=contato_id,
        tipo_aso_id=dados.tipo_aso_id, observacao=dados.observacao, forcar=dados.forcar,
        usuario_id=u.id, ator="painel",
    ))
    return resumo(_alvo(s, ag.id))


def _alvo(s: Session, ag_id: int) -> Agendamento:
    ag = s.get(Agendamento, ag_id, options=_opcoes()) if ag_id < 2**63 else None  # id gigante: 404, não 500
    if ag is None:
        raise HTTPException(404, "não encontrado")
    return ag


def _exige_supervisao_externo(ag: Agendamento, u: Usuario) -> None:
    if ag.no_sistema_externo and u.perfil not in (Perfil.ADMIN, Perfil.SUPERVISAO):
        raise HTTPException(403, "este agendamento já está no sistema externo: só a Supervisão altera")


@r.post("/agendamentos/{ag_id}/cancelar")
def cancelar(ag_id: int, dados: Motivo, s: Session = Depends(sessao), u: Usuario = Depends(equipe)):
    ag = _alvo(s, ag_id)
    _exige_supervisao_externo(ag, u)
    _executar(lambda: agenda.cancelar(s, ag, dados.motivo, u.id, "painel"))
    return resumo(ag)


@r.post("/agendamentos/{ag_id}/remarcar")
def remarcar(ag_id: int, dados: Remarcar, s: Session = Depends(sessao), u: Usuario = Depends(equipe)):
    ag = _alvo(s, ag_id)
    _exige_supervisao_externo(ag, u)
    novo = _executar(lambda: agenda.remarcar(s, ag, dados.data, dados.horario, u.id, "painel"))
    return resumo(_alvo(s, novo.id))


@r.post("/agendamentos/{ag_id}/presenca")
def presenca(ag_id: int, s: Session = Depends(sessao), u: Usuario = Depends(equipe)):
    ag = _alvo(s, ag_id)
    _executar(lambda: agenda.presenca(s, ag, u.id, "painel"))
    return resumo(ag)


@r.post("/agendamentos/{ag_id}/falta", summary="Marca falta e põe na fila o aviso com oferta de remarcação")
def falta(ag_id: int, s: Session = Depends(sessao), u: Usuario = Depends(equipe)):
    ag = _alvo(s, ag_id)
    _executar(lambda: agenda.falta(s, ag, u.id, "painel"))
    return resumo(ag)


@r.post("/agendamentos/{ag_id}/externo", summary="Marca (ou desmarca) que foi lançado no sistema externo")
def externo(ag_id: int, lancado: bool = True, codigo: str | None = None, s: Session = Depends(sessao),
            u: Usuario = Depends(equipe)):
    ag = _alvo(s, ag_id)
    if not lancado and ag.no_sistema_externo and u.perfil not in (Perfil.ADMIN, Perfil.SUPERVISAO):
        raise HTTPException(403, "só a Supervisão desmarca o que já foi lançado no sistema externo")
    antes = auditoria.foto(ag)
    ag.no_sistema_externo = lancado
    ag.codigo_externo = codigo[:40] if lancado and codigo else None
    auditoria.registrar(s, "agendamento", ag.id, "externo", antes, auditoria.foto(ag), u.id, "painel")
    return resumo(ag)


@r.get("/vagas", summary="Horários livres numa data (várias funções = todas livres ao mesmo tempo)")
def vagas(data: date, exames: list[int] = Query(...), s: Session = Depends(sessao),
          _: Usuario = Depends(qualquer)):
    hs = _executar(lambda: agenda.livres(s, data, exames))
    return {"data": data.isoformat(), "horarios": [h.strftime("%H:%M") for h in hs]}


@r.get("/vagas/proximas", summary="Próximos dias com vaga")
def proximas(exames: list[int] = Query(...), dias: int = 5, a_partir: date | None = None,
             s: Session = Depends(sessao), _: Usuario = Depends(qualquer)):
    res = _executar(lambda: agenda.proximos_dias(s, exames, min(dias, 30), para_bot=False,
                                                 a_partir=a_partir or hoje()))
    return [{"data": d.isoformat(), "horarios": [h.strftime("%H:%M") for h in hs]} for d, hs in res]


@r.get("/semana", summary="Agenda resumida por dia (contagem por status)")
def semana(inicio: date | None = None, s: Session = Depends(sessao), _: Usuario = Depends(qualquer)):
    inicio = inicio or hoje() - timedelta(days=hoje().weekday())
    fim = inicio + timedelta(days=6)
    contagem: dict[str, dict[str, int]] = {}
    for d, st in s.execute(select(Agendamento.data, Agendamento.status).where(Agendamento.data.between(inicio, fim))):
        dia = contagem.setdefault(d.isoformat(), {})
        dia[st.value] = dia.get(st.value, 0) + 1
    return contagem


def aprovacao_resumo(s: Session, ap: Aprovacao) -> dict:
    return {
        "id": ap.id, "tipo": ap.tipo.value, "status": ap.status.value,
        "pedida_em": ap.criado_em.isoformat() if ap.criado_em else None,
        "decidida_em": ap.decidida_em and ap.decidida_em.isoformat(), "motivo": ap.motivo,
        "alterada": ap.alterada, "agendamento": resumo(ap.agendamento),
        "original": ap.original and resumo(ap.original),
        "exige_supervisao": aprovacoes.exige_supervisao(ap),
        "contato_id": ap.contato_id,
        "proposta_em": ap.proposta_em and ap.proposta_em.isoformat(),
        "proposta_ate": ap.proposta_ate and ap.proposta_ate.isoformat(),
        "marcadores": aprovacoes.marcadores(s, ap) if ap.status in APROVACAO_EM_ABERTO else [],
    }
