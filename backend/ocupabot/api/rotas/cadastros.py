from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ...dominio.texto import normalizar_telefone
from ...enums import AGENDA_PELA_EMPRESA, TipoContato
from ...modelos import (
    Contato,
    Empresa,
    Exame,
    Excecao,
    Expediente,
    Funcao,
    Grade,
    Paciente,
    Profissional,
    TipoAso,
    Usuario,
)
from ...servicos import agenda, auditoria, contatos
from ..crud import rotas_crud, serializar
from ..deps import admin, equipe, qualquer, sessao, supervisao
from ..esquemas import ExcecaoNova, GradeNova
from .agenda import resumo


def _telefone(valor: str | None) -> str | None:
    if not valor:
        return None
    numero = normalizar_telefone(valor)
    if not 12 <= len(numero) <= 13:
        raise HTTPException(422, "telefone incompleto: informe DDD e número")
    return numero


def _empresa(s: Session, e: Empresa, u: Usuario) -> None:
    e.rh_telefone = _telefone(e.rh_telefone)


def _paciente(s: Session, p: Paciente, u: Usuario) -> None:
    p.telefone = _telefone(p.telefone)
    contatos.do_particular(s, p, u.id)  # particular com telefone ganha o contato que recebe os avisos


def _contato(s: Session, c: Contato, u: Usuario) -> None:
    c.telefone = _telefone(c.telefone)


ROTAS = [
    rotas_crud(Empresa, "/empresas", "empresa", equipe, ordem=Empresa.razao_social,
               busca=["razao_social", "nome_fantasia", "cnpj"], ao_gravar=_empresa),
    rotas_crud(Paciente, "/pacientes", "paciente", equipe, ordem=Paciente.nome, busca=["nome", "cpf"],
               ao_gravar=_paciente),
    rotas_crud(Contato, "/contatos", "contato", equipe, busca=["telefone", "nome"], ao_gravar=_contato),
    rotas_crud(Profissional, "/profissionais", "profissional", supervisao, ordem=Profissional.nome),
    rotas_crud(Funcao, "/funcoes", "funcao", admin, ordem=Funcao.nome),
    rotas_crud(Exame, "/exames", "exame", admin, ordem=Exame.ordem),
    rotas_crud(TipoAso, "/tipos-aso", "tipo_aso", admin, ordem=TipoAso.ordem),
    rotas_crud(Expediente, "/expediente", "expediente", admin, excluir=True),
]

r = APIRouter(tags=["grade, exceções e quem agenda"])


# --- Quem agenda: contatos e as empresas de cada um -------------------------------------------------

def _nome(e: Empresa) -> str:
    return e.nome_fantasia or e.razao_social


def _quem(s: Session, c: Contato) -> dict:
    return {**serializar(c), "optout": c.optout_em is not None,
            "empresas": [{"id": e.id, "nome": _nome(e)} for e in contatos.empresas_do_contato(s, c)]}


@r.get("/quem-agenda", summary="Contatos que agendam por empresas (RH, credenciadora, contabilidade)")
def quem_agenda(s: Session = Depends(sessao), _: Usuario = Depends(qualquer)):
    consulta = (select(Contato).where(Contato.tipo.in_(AGENDA_PELA_EMPRESA))
                .options(selectinload(Contato.vinculos)).order_by(Contato.nome, Contato.id).limit(2000))
    return [_quem(s, c) for c in s.scalars(consulta)]


def _par(s: Session, c_id: int, e_id: int | None = None) -> tuple[Contato, Empresa | None]:
    c = s.get(Contato, c_id) if c_id < 2**63 else None
    e = s.get(Empresa, e_id) if e_id is not None and e_id < 2**63 else None
    if c is None or (e_id is not None and e is None):
        raise HTTPException(404, "não encontrado")
    return c, e


@r.put("/contatos/{c_id}/empresas/{e_id}", summary="Liga o contato à empresa (confirma quem agenda por ela)")
def vincular(c_id: int, e_id: int, tipo: TipoContato | None = None, s: Session = Depends(sessao),
             u: Usuario = Depends(equipe)):
    c, e = _par(s, c_id, e_id)
    novo_tipo = tipo or (c.tipo if c.tipo in AGENDA_PELA_EMPRESA else TipoContato.RH)
    if novo_tipo not in AGENDA_PELA_EMPRESA:
        raise HTTPException(422, "tipo inválido: use RH, CREDENCIADORA ou CONTABILIDADE")
    contatos.vincular(s, c, e, u.id, novo_tipo)
    return _quem(s, c)


@r.delete("/contatos/{c_id}/empresas/{e_id}", summary="Tira a empresa do contato")
def desvincular(c_id: int, e_id: int, s: Session = Depends(sessao), u: Usuario = Depends(equipe)):
    c, _ = _par(s, c_id)
    contatos.desvincular(s, c, e_id, u.id)
    return _quem(s, c)


@r.post("/contatos/{c_id}/sair", summary="Registra (ou desfaz) o pedido de não receber mensagens")
def sair(c_id: int, ativo: bool = True, s: Session = Depends(sessao), u: Usuario = Depends(equipe)):
    c, _ = _par(s, c_id)
    contatos.marcar_sair(s, c, ativo, u.id)
    return _quem(s, c)


# --- Grade ------------------------------------------------------------------------------------------

@r.get("/grade")
def grade(s: Session = Depends(sessao), _: Usuario = Depends(qualquer)):
    return [serializar(g) for g in s.scalars(select(Grade).order_by(Grade.dia_semana, Grade.turno))]


@r.post("/grade", status_code=201)
def grade_criar(dados: GradeNova, s: Session = Depends(sessao), u: Usuario = Depends(supervisao)):
    g = Grade(**dados.model_dump())
    s.add(g)
    try:
        s.flush()
    except Exception as e:
        raise HTTPException(409, "essa combinação já existe") from e
    auditoria.registrar(s, "grade", g.id, "criar", None, auditoria.foto(g), u.id, "painel")
    return serializar(g)


@r.delete("/grade/{g_id}", status_code=204)
def grade_excluir(g_id: int, s: Session = Depends(sessao), u: Usuario = Depends(supervisao)):
    g = s.get(Grade, g_id)
    if g is None:
        raise HTTPException(404, "não encontrado")
    auditoria.registrar(s, "grade", g.id, "excluir", auditoria.foto(g), None, u.id, "painel")
    s.delete(g)


# --- Exceções ---------------------------------------------------------------------------------------

@r.get("/excecoes")
def excecoes(desde: date | None = None, ate: date | None = None, s: Session = Depends(sessao),
             _: Usuario = Depends(qualquer)):
    """`desde` traz as atuais e futuras; `ate` (sem `desde`), as que já passaram."""
    consulta = select(Excecao).order_by(Excecao.data_inicio if desde else Excecao.data_inicio.desc())
    if desde:
        consulta = consulta.where(Excecao.data_fim >= desde)
    if ate:
        consulta = consulta.where(Excecao.data_fim < ate)
    return [serializar(e) for e in s.scalars(consulta.limit(500))]


def _validar(s: Session, dados: ExcecaoNova) -> Excecao:
    if dados.data_fim < dados.data_inicio:
        raise HTTPException(422, "a data final é antes da inicial")
    if dados.profissional_id is not None and s.get(Profissional, dados.profissional_id) is None:
        raise HTTPException(422, "profissional não encontrado")
    campos = dados.model_dump(exclude={"avisar_afetados"})
    return Excecao(**campos)


@r.post("/excecoes/previa", summary="Agendamentos que a exceção atingiria (sem salvar)")
def excecao_previa(dados: ExcecaoNova, s: Session = Depends(sessao), _: Usuario = Depends(qualquer)):
    return [resumo(a) for a in agenda.afetados_por_excecao(s, _validar(s, dados))]


@r.post("/excecoes", status_code=201, summary="Cria exceção; com avisar_afetados, avisa quem precisa remarcar")
def excecao_criar(dados: ExcecaoNova, s: Session = Depends(sessao), u: Usuario = Depends(equipe)):
    ex = _validar(s, dados)
    repetida = s.scalar(select(Excecao.id).where(
        Excecao.profissional_id.is_(None) if ex.profissional_id is None
        else Excecao.profissional_id == ex.profissional_id,
        Excecao.data_inicio == ex.data_inicio, Excecao.data_fim == ex.data_fim,
        Excecao.turno.is_(None) if ex.turno is None else Excecao.turno == ex.turno).limit(1))
    if repetida is not None:
        raise HTTPException(409, "já existe uma exceção igual (mesma pessoa, período e turno)")
    s.add(ex)
    s.flush()
    afetados = agenda.afetados_por_excecao(s, ex)
    avisos = agenda.avisar_remarcacao(s, afetados) if dados.avisar_afetados else 0
    auditoria.registrar(s, "excecao", ex.id, "criar", None, auditoria.foto(ex), u.id, "painel")
    return {**serializar(ex), "afetados": len(afetados), "avisos": avisos}


@r.delete("/excecoes/{e_id}", status_code=204)
def excecao_excluir(e_id: int, s: Session = Depends(sessao), u: Usuario = Depends(equipe)):
    ex = s.get(Excecao, e_id)
    if ex is None:
        raise HTTPException(404, "não encontrado")
    auditoria.registrar(s, "excecao", ex.id, "excluir", auditoria.foto(ex), None, u.id, "painel")
    s.delete(ex)
