from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...enums import Perfil
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
from ...servicos import agenda, auditoria
from ..crud import rotas_crud, serializar
from ..deps import admin, equipe, exige, qualquer, sessao
from ..esquemas import ExcecaoNova, GradeNova
from .agenda import resumo

supervisao = exige(Perfil.SUPERVISAO)

ROTAS = [
    rotas_crud(Empresa, "/empresas", "empresa", equipe, ordem=Empresa.razao_social,
               busca=["razao_social", "nome_fantasia", "cnpj"]),
    rotas_crud(Paciente, "/pacientes", "paciente", equipe, ordem=Paciente.nome, busca=["nome", "cpf"]),
    rotas_crud(Contato, "/contatos", "contato", equipe, busca=["telefone", "nome"]),
    rotas_crud(Profissional, "/profissionais", "profissional", supervisao, ordem=Profissional.nome),
    rotas_crud(Funcao, "/funcoes", "funcao", admin, ordem=Funcao.nome),
    rotas_crud(Exame, "/exames", "exame", admin, ordem=Exame.ordem),
    rotas_crud(TipoAso, "/tipos-aso", "tipo_aso", admin, ordem=TipoAso.ordem),
    rotas_crud(Expediente, "/expediente", "expediente", admin, excluir=True),
]

r = APIRouter(tags=["grade e exceções"])


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


@r.get("/excecoes")
def excecoes(desde: date | None = None, s: Session = Depends(sessao), _: Usuario = Depends(qualquer)):
    consulta = select(Excecao).order_by(Excecao.data_inicio.desc())
    if desde:
        consulta = consulta.where(Excecao.data_fim >= desde)
    return [serializar(e) for e in s.scalars(consulta.limit(500))]


def _validar(dados: ExcecaoNova) -> Excecao:
    if dados.data_fim < dados.data_inicio:
        raise HTTPException(422, "a data final é antes da inicial")
    campos = dados.model_dump(exclude={"avisar_afetados"})
    return Excecao(**campos)


@r.post("/excecoes/previa", summary="Agendamentos que a exceção atingiria (sem salvar)")
def excecao_previa(dados: ExcecaoNova, s: Session = Depends(sessao), u: Usuario = Depends(qualquer)):
    return [resumo(a, u.perfil) for a in agenda.afetados_por_excecao(s, _validar(dados))]


@r.post("/excecoes", status_code=201, summary="Cria exceção; com avisar_afetados, avisa quem precisa remarcar")
def excecao_criar(dados: ExcecaoNova, s: Session = Depends(sessao), u: Usuario = Depends(equipe)):
    ex = _validar(dados)
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
