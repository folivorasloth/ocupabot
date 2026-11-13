from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...modelos import Auditoria, Parametro, Texto, Usuario
from ...servicos import auditoria, parametros, textos
from ..crud import serializar
from ..deps import admin, sessao, supervisao
from ..esquemas import AuditoriaSaida, Previa, ValorTexto

r = APIRouter(tags=["configuração"])
SEMPRE = {"clinica", "horario_atendimento", "orientacoes"}  # variáveis que valem em qualquer texto


@r.get("/parametros")
def listar_parametros(s: Session = Depends(sessao), _: Usuario = Depends(supervisao)):
    parametros.garantir_padroes(s)
    return [serializar(p) for p in s.scalars(select(Parametro).order_by(Parametro.chave))]


@r.put("/parametros/{chave}")
def alterar_parametro(chave: str, dados: ValorTexto, s: Session = Depends(sessao), u: Usuario = Depends(admin)):
    p = s.get(Parametro, chave)
    if p is None:
        raise HTTPException(404, "parâmetro desconhecido")
    valor = dados.valor.strip()
    problema = parametros.problema(chave, valor)
    if problema:
        raise HTTPException(422, problema)
    antes = auditoria.foto(p)
    p.valor = valor
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
    if not dados.valor.strip():
        raise HTTPException(422, "o texto não pode ficar vazio")
    faltando = set(textos.variaveis(dados.valor)) - set(textos.variaveis(textos.PADROES.get(chave, ""))) - SEMPRE
    if faltando:
        raise HTTPException(422, f"variáveis desconhecidas: {', '.join(sorted(faltando))}")
    return _gravar_texto(s, t, dados.valor, u, "alterar")


def _gravar_texto(s: Session, t: Texto, novo: str, u: Usuario, acao: str) -> dict:
    # a versão anterior vai inteira para a auditoria: é dela que o "voltar" recupera o texto
    auditoria.registrar(s, "texto", t.chave, acao, {"texto": t.texto}, {"texto": novo}, u.id, "painel")
    t.texto = novo
    return serializar(t)


@r.post("/textos/{chave}/voltar", summary="Volta o texto à versão anterior (ou ao texto original)")
def voltar_texto(chave: str, original: bool = False, s: Session = Depends(sessao),
                 u: Usuario = Depends(supervisao)):
    t = s.get(Texto, chave)
    if t is None:
        raise HTTPException(404, "texto desconhecido")
    anterior = textos.PADROES.get(chave) if original else None
    if not original:
        ultima = s.scalars(select(Auditoria).where(Auditoria.entidade == "texto", Auditoria.entidade_id == chave)
                           .order_by(Auditoria.id.desc()).limit(1)).first()
        anterior = (ultima.antes or {}).get("texto") if ultima else None
    if not anterior or anterior == t.texto:
        raise HTTPException(409, "não há versão anterior diferente da atual")
    return _gravar_texto(s, t, anterior, u, "voltar")


@r.post("/textos/previa")
def previa(dados: Previa, _: Usuario = Depends(supervisao)):
    exemplo = {"paciente": "Maria", "data": "ter 10/11", "horario": "08:00", "empresa": "Empresa Exemplo",
               "tipo": "Periódico", "lista": "ter 10/11: 07:30 às 09:00", "exemplo": "10/11 08:00",
               "opcoes": "1 - Opção A\n2 - Opção B", "problema": "exemplo.", "dica": "Responda 1 ou 2.",
               "exames": "EEG", "orientacoes": "Traga documento com foto.", "horario_atendimento": "seg a sex",
               "resto": ""}
    return {"texto": textos.renderizar(dados.texto, **exemplo)}


@r.get("/auditoria", response_model=list[AuditoriaSaida])
def listar_auditoria(entidade: str | None = None, entidade_id: str | None = None, limite: int = 200,
                     s: Session = Depends(sessao), _: Usuario = Depends(supervisao)):
    consulta = select(Auditoria).order_by(Auditoria.id.desc())
    if entidade:
        consulta = consulta.where(Auditoria.entidade == entidade)
    if entidade_id:
        consulta = consulta.where(Auditoria.entidade_id == entidade_id)
    return list(s.scalars(consulta.limit(max(1, min(limite, 1000)))))
