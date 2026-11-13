"""Contatos: quem agenda por quais empresas e o pedido de SAIR.

`contatos.empresa_id` é a empresa principal; as demais ficam em `contato_empresas`. Um RH costuma ter
uma empresa só; credenciadora e escritório de contabilidade agendam por várias.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..dominio.texto import normalizar, normalizar_telefone, variantes
from ..enums import AGENDA_PELA_EMPRESA, TipoContato
from ..modelos import Contato, ContatoEmpresa, Empresa, Paciente
from ..relogio import agora
from . import auditoria


def por_telefone(s: Session, telefone: str | None) -> Contato | None:
    """O contato do número, com ou sem o nono dígito (a forma igual primeiro)."""
    if not telefone:
        return None
    achados = list(s.scalars(select(Contato).where(Contato.telefone.in_(variantes(telefone))).order_by(Contato.id)))
    return min(achados, key=lambda c: c.telefone != telefone) if achados else None


def agenda_pela_empresa(c: Contato | None) -> bool:
    return c is not None and c.tipo in AGENDA_PELA_EMPRESA


def empresas_do_contato(s: Session, c: Contato) -> list[Empresa]:
    """Empresas ativas do contato: a principal primeiro, as ligadas em ordem alfabética."""
    ids = c.empresas_ids
    if not ids:
        return []
    achadas = {e.id: e for e in s.scalars(select(Empresa).where(Empresa.id.in_(ids), Empresa.ativa.is_(True)))}
    principal = [achadas[c.empresa_id]] if c.empresa_id in achadas else []
    resto = sorted((e for i, e in achadas.items() if i != c.empresa_id), key=lambda e: normalizar(e.razao_social))
    return principal + resto


def _foto(c: Contato) -> dict:
    return {**auditoria.foto(c), "empresas_ids": c.empresas_ids}


def vincular(s: Session, c: Contato, empresa: Empresa, usuario_id: int | None = None,
             tipo: TipoContato | None = None) -> bool:
    """Liga o contato à empresa (sem principal, ela vira a principal). False se já estava ligado."""
    antes = _foto(c)
    if tipo is not None:
        c.tipo = tipo
    novo = empresa.id not in c.empresas_ids
    if novo and c.empresa_id is None:
        c.empresa_id = empresa.id
    elif novo:
        c.vinculos.append(ContatoEmpresa(empresa_id=empresa.id))
    s.flush()
    if novo or antes["tipo"] != c.tipo.value:
        auditoria.registrar(s, "contato", c.id, "vincular_empresa", antes, _foto(c), usuario_id, "painel")
    return novo


def desvincular(s: Session, c: Contato, empresa_id: int, usuario_id: int | None = None) -> bool:
    """Tira a empresa do contato. Se era a principal, a próxima ligada assume."""
    if empresa_id not in c.empresas_ids:
        return False
    antes = _foto(c)
    for v in [v for v in c.vinculos if v.empresa_id == empresa_id]:
        c.vinculos.remove(v)
    if c.empresa_id == empresa_id:
        c.empresa_id = None
        if c.vinculos:
            c.empresa_id = c.vinculos[0].empresa_id
            c.vinculos.remove(c.vinculos[0])
    s.flush()
    auditoria.registrar(s, "contato", c.id, "desvincular_empresa", antes, _foto(c), usuario_id, "painel")
    return True


def marcar_sair(s: Session, c: Contato, ativo: bool, usuario_id: int | None = None, ator: str = "painel") -> None:
    """Registra (ou desfaz) o pedido de não receber mensagens. Pelo bot ou pela equipe, fica na auditoria."""
    if (c.optout_em is not None) == ativo:
        return
    c.optout_em = agora() if ativo else None
    auditoria.registrar(s, "contato", c.id, "sair" if ativo else "voltar", None,
                        {"optout": ativo}, usuario_id, ator)


def do_particular(s: Session, p: Paciente, usuario_id: int | None = None) -> Contato | None:
    """Paciente particular cadastrado com telefone ganha o contato que recebe confirmação e lembrete.
    Número que já é de alguém (outro paciente, um RH, quem pediu SAIR) fica como está."""
    if p.empresa_id is not None or not p.telefone:
        return None
    p.telefone = normalizar_telefone(p.telefone)
    if por_telefone(s, p.telefone) is not None:
        return None
    c = Contato(telefone=p.telefone, nome=p.nome, tipo=TipoContato.PARTICULAR)
    s.add(c)
    s.flush()
    auditoria.registrar(s, "contato", c.id, "criar_pelo_paciente", None, auditoria.foto(c), usuario_id, "painel")
    return c
