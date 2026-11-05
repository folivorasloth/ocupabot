from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...enums import Perfil
from ...modelos import Auditoria, Parametro, Texto, Usuario
from ...servicos import auditoria, parametros, textos
from ..crud import serializar
from ..deps import admin, exige, sessao
from ..esquemas import AuditoriaSaida, Previa, ValorTexto

r = APIRouter(tags=["configuração"])
supervisao = exige(Perfil.SUPERVISAO)


@r.get("/parametros")
def listar_parametros(s: Session = Depends(sessao), _: Usuario = Depends(supervisao)):
    parametros.garantir_padroes(s)
    return [serializar(p) for p in s.scalars(select(Parametro).order_by(Parametro.chave))]


@r.put("/parametros/{chave}")
def alterar_parametro(chave: str, dados: ValorTexto, s: Session = Depends(sessao), u: Usuario = Depends(admin)):
    p = s.get(Parametro, chave)
    if p is None:
        raise HTTPException(404, "parâmetro desconhecido")
    padrao = parametros.PADROES.get(chave, ("",))[0]
    if padrao.lower() in ("true", "false") and dados.valor.lower() not in ("true", "false"):
        raise HTTPException(422, "use true ou false")
    if padrao.isdigit() and not dados.valor.isdigit():
        raise HTTPException(422, "use um número inteiro")
    antes = auditoria.foto(p)
    p.valor = dados.valor
    auditoria.registrar(s, "parametro", chave, "alterar", antes, auditoria.foto(p), u.id, "painel")
    return serializar(p)


@r.get("/textos")
def listar_textos(s: Session = Depends(sessao), _: Usuario = Depends(supervisao)):
    textos.garantir_padroes(s)
    return [serializar(t) for t in s.scalars(select(Texto).order_by(Texto.chave))]


@r.put("/textos/{chave}")
def alterar_texto(chave: str, dados: ValorTexto, s: Session = Depends(sessao), u: Usuario = Depends(supervisao)):
    t = s.get(Texto, chave)
    if t is None:
        raise HTTPException(404, "texto desconhecido")
    faltando = set(textos.variaveis(dados.valor)) - set(textos.variaveis(textos.PADROES.get(chave, ""))) - {
        "clinica", "horario_atendimento", "orientacoes"}
    if faltando:
        raise HTTPException(422, f"variáveis desconhecidas: {', '.join(sorted(faltando))}")
    antes = auditoria.foto(t)
    t.texto = dados.valor
    auditoria.registrar(s, "texto", chave, "alterar", antes, auditoria.foto(t), u.id, "painel")
    return serializar(t)


@r.post("/textos/previa")
def previa(dados: Previa, _: Usuario = Depends(supervisao)):
    exemplo = {"paciente": "Maria", "data": "ter 10/11", "horario": "08:00", "empresa": "Empresa Exemplo",
               "tipo": "Periódico", "lista": "ter 10/11: 07:30 às 09:00", "exemplo": "10/11 08:00",
               "opcoes": "1 - Opção A\n2 - Opção B", "problema": "exemplo.", "dica": "Responda 1 ou 2.",
               "exames": "EEG", "orientacoes": "Traga documento com foto.", "horario_atendimento": "seg a sex"}
    return {"texto": textos.renderizar(dados.texto, **exemplo)}


@r.get("/auditoria", response_model=list[AuditoriaSaida])
def listar_auditoria(entidade: str | None = None, entidade_id: str | None = None, limite: int = 200,
                     s: Session = Depends(sessao), _: Usuario = Depends(supervisao)):
    consulta = select(Auditoria).order_by(Auditoria.id.desc())
    if entidade:
        consulta = consulta.where(Auditoria.entidade == entidade)
    if entidade_id:
        consulta = consulta.where(Auditoria.entidade_id == entidade_id)
    return list(s.scalars(consulta.limit(min(limite, 1000))))
