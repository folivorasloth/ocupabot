"""Modelos de entrada e saída da API (Pydantic)."""

from __future__ import annotations

from datetime import date, datetime, time
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, model_validator

from ..dominio.documentos import tem_documento
from ..dominio.texto import normalizar_telefone
from ..enums import Perfil, TipoExcecao, Turno
from ..seguranca import problema_senha


def _sem_documento(v: str | None) -> str | None:
    """Texto livre não é lugar de CPF ou RG: fica legível para quem não precisa ver."""
    if tem_documento(v):
        raise ValueError("não escreva CPF ou RG neste campo")
    return v


def _senha_forte(v: str | None) -> str | None:
    problema = problema_senha(v) if v is not None else None
    if problema:
        raise ValueError(problema)
    return v


def _whatsapp(v: str | None) -> str | None:
    if not v:
        return None
    numero = normalizar_telefone(v)
    if not 12 <= len(numero) <= 13:
        raise ValueError("WhatsApp incompleto: informe DDD e número")
    return numero


TextoLivre = Annotated[str, AfterValidator(_sem_documento)]
Senha = Annotated[str, Field(max_length=200), AfterValidator(_senha_forte)]
WhatsApp = Annotated[str | None, Field(max_length=20), AfterValidator(_whatsapp)]


class Base(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Login(BaseModel):
    login: str = Field(max_length=80)
    senha: str = Field(max_length=200)


class TrocarSenha(BaseModel):
    atual: str = Field(max_length=200)
    nova: Senha


class UsuarioNovo(BaseModel):
    nome: str = Field(min_length=2, max_length=120)
    login: str = Field(min_length=3, max_length=80, pattern=r"^[a-z0-9._-]+$")
    senha: Senha
    perfil: Perfil
    whatsapp: WhatsApp = None

    @model_validator(mode="after")
    def _senha_sem_login(self) -> UsuarioNovo:
        problema = problema_senha(self.senha, self.login)
        if problema:
            raise ValueError(problema)
        return self


class UsuarioAlterar(BaseModel):
    nome: str | None = Field(default=None, min_length=2, max_length=120)
    perfil: Perfil | None = None
    ativo: bool | None = None
    senha: Senha | None = None
    whatsapp: WhatsApp = None


class AgendamentoNovo(BaseModel):
    paciente_id: int | None = None
    paciente_nome: str | None = Field(default=None, max_length=160)
    paciente_cpf: str | None = Field(default=None, max_length=20)
    paciente_nascimento: date | None = None
    empresa_id: int | None = None
    contato_telefone: str | None = Field(default=None, max_length=30)
    tipo_aso_id: int | None = None
    exame_ids: list[int] = Field(min_length=1, max_length=30)
    data: date
    horario: time
    observacao: TextoLivre | None = Field(default=None, max_length=2000)
    forcar: bool = False


class Remarcar(BaseModel):
    data: date
    horario: time


class Motivo(BaseModel):
    motivo: TextoLivre = Field(min_length=2, max_length=300)


class MotivoOpcional(BaseModel):
    motivo: TextoLivre | None = Field(default=None, max_length=300)


class Responder(BaseModel):
    texto: TextoLivre = Field(min_length=1, max_length=4000)


class SimuladorEntrada(BaseModel):
    telefone: str = Field(default="5500000000000", pattern=r"^\d{10,15}$")
    texto: str = Field(min_length=1, max_length=2000)


class ExcecaoNova(BaseModel):
    profissional_id: int | None = None
    tipo: TipoExcecao
    data_inicio: date
    data_fim: date
    turno: Turno | None = None
    motivo: TextoLivre | None = Field(default=None, max_length=200)
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
