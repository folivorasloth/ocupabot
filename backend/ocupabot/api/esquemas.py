"""Modelos de entrada e saída da API (Pydantic)."""

from __future__ import annotations

from datetime import date, datetime, time

from pydantic import BaseModel, ConfigDict, Field

from ..enums import Perfil, TipoExcecao, Turno


class Base(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Login(BaseModel):
    login: str = Field(max_length=80)
    senha: str = Field(max_length=200)


class UsuarioSaida(Base):
    id: int
    nome: str
    login: str
    perfil: Perfil
    ativo: bool


class UsuarioNovo(BaseModel):
    nome: str = Field(min_length=2, max_length=120)
    login: str = Field(min_length=3, max_length=80, pattern=r"^[a-z0-9._-]+$")
    senha: str = Field(min_length=8, max_length=200)
    perfil: Perfil


class UsuarioAlterar(BaseModel):
    nome: str | None = None
    perfil: Perfil | None = None
    ativo: bool | None = None
    senha: str | None = Field(default=None, min_length=8, max_length=200)


class AgendamentoNovo(BaseModel):
    paciente_id: int | None = None
    paciente_nome: str | None = Field(default=None, max_length=160)
    paciente_cpf: str | None = None
    paciente_nascimento: date | None = None
    empresa_id: int | None = None
    contato_telefone: str | None = None
    tipo_aso_id: int | None = None
    exame_ids: list[int] = Field(min_length=1)
    data: date
    horario: time
    observacao: str | None = Field(default=None, max_length=2000)
    forcar: bool = False


class Remarcar(BaseModel):
    data: date
    horario: time


class Motivo(BaseModel):
    motivo: str = Field(min_length=2, max_length=300)


class Aprovar(BaseModel):
    data: date | None = None
    horario: time | None = None


class Responder(BaseModel):
    texto: str = Field(min_length=1, max_length=4000)


class SimuladorEntrada(BaseModel):
    telefone: str = Field(default="5500000000000", pattern=r"^\d{10,15}$")
    texto: str = Field(min_length=1, max_length=2000)


class ExcecaoNova(BaseModel):
    profissional_id: int | None = None
    tipo: TipoExcecao
    data_inicio: date
    data_fim: date
    turno: Turno | None = None
    motivo: str | None = Field(default=None, max_length=200)
    avisar_afetados: bool = False


class GradeNova(BaseModel):
    profissional_id: int
    funcao_id: int
    dia_semana: int = Field(ge=0, le=6)
    turno: Turno
    confirmada: bool = True


class ValorTexto(BaseModel):
    valor: str = Field(max_length=4000)


class Previa(BaseModel):
    texto: str = Field(max_length=4000)


class AuditoriaSaida(Base):
    id: int
    em: datetime
    usuario_id: int | None
    ator: str
    entidade: str
    entidade_id: str
    acao: str
    antes: dict | None
    depois: dict | None
