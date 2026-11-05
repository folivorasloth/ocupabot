"""Tabelas do OcupaBot (SQLAlchemy 2)."""

from datetime import date, datetime, time
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    Time,
    UniqueConstraint,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base, ComDatas
from .enums import (
    Autor,
    EstadoConversa,
    Origem,
    Perfil,
    StatusAgendamento,
    StatusAprovacao,
    StatusEnvio,
    StatusNotificacao,
    TipoAprovacao,
    TipoContato,
    TipoExcecao,
    TipoNotificacao,
    Turno,
)
from .relogio import agora


def _enum(e):
    return SAEnum(e, native_enum=False, length=30, validate_strings=True)


# --- Acesso -----------------------------------------------------------------------------------------

class Usuario(ComDatas, Base):
    __tablename__ = "usuarios"
    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(120))
    login: Mapped[str] = mapped_column(String(80), unique=True)
    senha_hash: Mapped[str] = mapped_column(String(200))
    perfil: Mapped[Perfil] = mapped_column(_enum(Perfil))
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    versao_sessao: Mapped[int] = mapped_column(Integer, default=1)


class Auditoria(Base):
    __tablename__ = "auditoria"
    id: Mapped[int] = mapped_column(primary_key=True)
    em: Mapped[datetime] = mapped_column(DateTime, default=agora, index=True)
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))
    ator: Mapped[str] = mapped_column(String(40))
    entidade: Mapped[str] = mapped_column(String(40), index=True)
    entidade_id: Mapped[str] = mapped_column(String(40))
    acao: Mapped[str] = mapped_column(String(40))
    antes: Mapped[Any | None] = mapped_column(JSON)
    depois: Mapped[Any | None] = mapped_column(JSON)
    ip: Mapped[str | None] = mapped_column(String(45))


class Parametro(ComDatas, Base):
    __tablename__ = "parametros"
    chave: Mapped[str] = mapped_column(String(60), primary_key=True)
    valor: Mapped[str] = mapped_column(Text)
    descricao: Mapped[str] = mapped_column(Text, default="")


class Texto(ComDatas, Base):
    __tablename__ = "textos"
    chave: Mapped[str] = mapped_column(String(60), primary_key=True)
    texto: Mapped[str] = mapped_column(Text)
    descricao: Mapped[str] = mapped_column(Text, default="")
    variaveis: Mapped[str] = mapped_column(String(200), default="")


# --- Cadastros --------------------------------------------------------------------------------------

class Empresa(ComDatas, Base):
    __tablename__ = "empresas"
    id: Mapped[int] = mapped_column(primary_key=True)
    razao_social: Mapped[str] = mapped_column(String(200))
    nome_fantasia: Mapped[str | None] = mapped_column(String(200))
    cnpj: Mapped[str | None] = mapped_column(String(14), index=True)
    usa_sistema_externo: Mapped[bool] = mapped_column(Boolean, default=False)
    codigo_externo: Mapped[str | None] = mapped_column(String(30))
    rh_nome: Mapped[str | None] = mapped_column(String(120))
    rh_telefone: Mapped[str | None] = mapped_column(String(20))
    ativa: Mapped[bool] = mapped_column(Boolean, default=True)


class Contato(ComDatas, Base):
    __tablename__ = "contatos"
    id: Mapped[int] = mapped_column(primary_key=True)
    telefone: Mapped[str] = mapped_column(String(20), unique=True)
    nome: Mapped[str | None] = mapped_column(String(120))
    tipo: Mapped[TipoContato] = mapped_column(_enum(TipoContato), default=TipoContato.DESCONHECIDO)
    empresa_id: Mapped[int | None] = mapped_column(ForeignKey("empresas.id"))
    optout_em: Mapped[datetime | None] = mapped_column(DateTime)

    empresa: Mapped[Empresa | None] = relationship()


class Paciente(ComDatas, Base):
    __tablename__ = "pacientes"
    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(160))
    cpf: Mapped[str | None] = mapped_column(String(11), unique=True)
    nascimento: Mapped[date | None] = mapped_column(Date)
    rg: Mapped[str | None] = mapped_column(String(20))
    telefone: Mapped[str | None] = mapped_column(String(20))
    empresa_id: Mapped[int | None] = mapped_column(ForeignKey("empresas.id"))
    setor: Mapped[str | None] = mapped_column(String(120))
    cargo: Mapped[str | None] = mapped_column(String(120))

    empresa: Mapped[Empresa | None] = relationship()


class Funcao(ComDatas, Base):
    """Quem executa um exame: clínico, audiometria, laboratório... Um profissional pode ter várias."""

    __tablename__ = "funcoes"
    id: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[str] = mapped_column(String(30), unique=True)
    nome: Mapped[str] = mapped_column(String(80))
    capacidade_por_hora: Mapped[int | None] = mapped_column(Integer)
    requer_humano: Mapped[bool] = mapped_column(Boolean, default=False)
    ativa: Mapped[bool] = mapped_column(Boolean, default=True)


class Exame(ComDatas, Base):
    __tablename__ = "exames"
    id: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[str] = mapped_column(String(30), unique=True)
    nome: Mapped[str] = mapped_column(String(120))
    funcao_id: Mapped[int | None] = mapped_column(ForeignKey("funcoes.id"))
    ordem: Mapped[int] = mapped_column(Integer, default=0)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)

    funcao: Mapped[Funcao | None] = relationship()


class TipoAso(Base):
    __tablename__ = "tipos_aso"
    id: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[str] = mapped_column(String(30), unique=True)
    nome: Mapped[str] = mapped_column(String(80))
    ordem: Mapped[int] = mapped_column(Integer, default=0)
    exige_cadastro_completo: Mapped[bool] = mapped_column(Boolean, default=False)


class Profissional(ComDatas, Base):
    __tablename__ = "profissionais"
    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(120))
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)


class Expediente(Base):
    __tablename__ = "expediente"
    __table_args__ = (UniqueConstraint("dia_semana", "turno"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    dia_semana: Mapped[int] = mapped_column(Integer)  # 0 = segunda
    turno: Mapped[Turno] = mapped_column(_enum(Turno))
    inicio: Mapped[time] = mapped_column(Time)
    fim: Mapped[time] = mapped_column(Time)


class Grade(ComDatas, Base):
    """Profissional X atende a função Y no dia da semana Z, turno W."""

    __tablename__ = "grade"
    __table_args__ = (UniqueConstraint("profissional_id", "funcao_id", "dia_semana", "turno"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    profissional_id: Mapped[int] = mapped_column(ForeignKey("profissionais.id"))
    funcao_id: Mapped[int] = mapped_column(ForeignKey("funcoes.id"))
    dia_semana: Mapped[int] = mapped_column(Integer)
    turno: Mapped[Turno] = mapped_column(_enum(Turno))
    confirmada: Mapped[bool] = mapped_column(Boolean, default=True)


class Excecao(ComDatas, Base):
    """Férias, folga ou ausência de um profissional; sem profissional, vale para a clínica (feriado)."""

    __tablename__ = "excecoes"
    id: Mapped[int] = mapped_column(primary_key=True)
    profissional_id: Mapped[int | None] = mapped_column(ForeignKey("profissionais.id"))
    tipo: Mapped[TipoExcecao] = mapped_column(_enum(TipoExcecao))
    data_inicio: Mapped[date] = mapped_column(Date)
    data_fim: Mapped[date] = mapped_column(Date)
    turno: Mapped[Turno | None] = mapped_column(_enum(Turno))
    motivo: Mapped[str | None] = mapped_column(String(200))


# --- Agenda -----------------------------------------------------------------------------------------

class Agendamento(ComDatas, Base):
    __tablename__ = "agendamentos"
    id: Mapped[int] = mapped_column(primary_key=True)
    paciente_id: Mapped[int] = mapped_column(ForeignKey("pacientes.id"))
    empresa_id: Mapped[int | None] = mapped_column(ForeignKey("empresas.id"))
    contato_id: Mapped[int | None] = mapped_column(ForeignKey("contatos.id"))
    tipo_aso_id: Mapped[int | None] = mapped_column(ForeignKey("tipos_aso.id"))
    data: Mapped[date] = mapped_column(Date, index=True)
    horario: Mapped[time] = mapped_column(Time)
    turno: Mapped[Turno] = mapped_column(_enum(Turno))
    status: Mapped[StatusAgendamento] = mapped_column(_enum(StatusAgendamento), index=True)
    origem: Mapped[Origem] = mapped_column(_enum(Origem))
    remarcado_de_id: Mapped[int | None] = mapped_column(ForeignKey("agendamentos.id"))
    motivo_cancelamento: Mapped[str | None] = mapped_column(String(200))
    observacao: Mapped[str | None] = mapped_column(Text)
    no_sistema_externo: Mapped[bool] = mapped_column(Boolean, default=False)
    codigo_externo: Mapped[str | None] = mapped_column(String(40))

    paciente: Mapped[Paciente] = relationship()
    empresa: Mapped[Empresa | None] = relationship()
    contato: Mapped[Contato | None] = relationship()
    tipo_aso: Mapped[TipoAso | None] = relationship()
    itens: Mapped[list["ItemAgendamento"]] = relationship(
        back_populates="agendamento", cascade="all, delete-orphan"
    )


class ItemAgendamento(Base):
    __tablename__ = "agendamento_itens"
    id: Mapped[int] = mapped_column(primary_key=True)
    agendamento_id: Mapped[int] = mapped_column(ForeignKey("agendamentos.id", ondelete="CASCADE"))
    exame_id: Mapped[int] = mapped_column(ForeignKey("exames.id"))
    profissional_id: Mapped[int | None] = mapped_column(ForeignKey("profissionais.id"))

    agendamento: Mapped[Agendamento] = relationship(back_populates="itens")
    exame: Mapped[Exame] = relationship()
    profissional: Mapped[Profissional | None] = relationship()


class Aprovacao(ComDatas, Base):
    __tablename__ = "aprovacoes"
    id: Mapped[int] = mapped_column(primary_key=True)
    tipo: Mapped[TipoAprovacao] = mapped_column(_enum(TipoAprovacao))
    status: Mapped[StatusAprovacao] = mapped_column(
        _enum(StatusAprovacao), default=StatusAprovacao.PENDENTE, index=True
    )
    # NOVO/REMARCACAO: o agendamento pedido (segurando a vaga). CANCELAMENTO: o que será cancelado.
    agendamento_id: Mapped[int] = mapped_column(ForeignKey("agendamentos.id"))
    # REMARCACAO: o agendamento que será substituído
    original_id: Mapped[int | None] = mapped_column(ForeignKey("agendamentos.id"))
    contato_id: Mapped[int | None] = mapped_column(ForeignKey("contatos.id"))
    decidida_em: Mapped[datetime | None] = mapped_column(DateTime)
    decidida_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))
    alterada: Mapped[bool] = mapped_column(Boolean, default=False)
    motivo: Mapped[str | None] = mapped_column(String(300))

    agendamento: Mapped[Agendamento] = relationship(foreign_keys=[agendamento_id])
    original: Mapped[Agendamento | None] = relationship(foreign_keys=[original_id])
    contato: Mapped[Contato | None] = relationship()


# --- Conversas e envios -----------------------------------------------------------------------------

class Conversa(ComDatas, Base):
    __tablename__ = "conversas"
    id: Mapped[int] = mapped_column(primary_key=True)
    contato_id: Mapped[int] = mapped_column(ForeignKey("contatos.id"), unique=True)
    estado: Mapped[EstadoConversa] = mapped_column(_enum(EstadoConversa), default=EstadoConversa.BOT)
    fluxo: Mapped[str | None] = mapped_column(String(40))
    etapa: Mapped[str | None] = mapped_column(String(40))
    dados: Mapped[dict] = mapped_column(JSON, default=dict)
    erros_seguidos: Mapped[int] = mapped_column(Integer, default=0)
    motivo_humano: Mapped[str | None] = mapped_column(String(200))
    atendente_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))
    simulada: Mapped[bool] = mapped_column(Boolean, default=False)  # criada pelo simulador do painel
    ultima_entrada_em: Mapped[datetime | None] = mapped_column(DateTime)

    contato: Mapped[Contato] = relationship()


class Mensagem(Base):
    __tablename__ = "mensagens"
    id: Mapped[int] = mapped_column(primary_key=True)
    conversa_id: Mapped[int] = mapped_column(ForeignKey("conversas.id"), index=True)
    autor: Mapped[Autor] = mapped_column(_enum(Autor))
    texto: Mapped[str] = mapped_column(Text)
    id_externo: Mapped[str | None] = mapped_column(String(120), unique=True)
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))
    status: Mapped[StatusEnvio] = mapped_column(_enum(StatusEnvio), index=True)
    valida_ate: Mapped[datetime | None] = mapped_column(DateTime)
    tentativas: Mapped[int] = mapped_column(Integer, default=0)
    erro: Mapped[str | None] = mapped_column(String(300))
    em: Mapped[datetime] = mapped_column(DateTime)


class Notificacao(ComDatas, Base):
    __tablename__ = "notificacoes"
    id: Mapped[int] = mapped_column(primary_key=True)
    tipo: Mapped[TipoNotificacao] = mapped_column(_enum(TipoNotificacao))
    contato_id: Mapped[int] = mapped_column(ForeignKey("contatos.id"))
    agendamento_id: Mapped[int | None] = mapped_column(ForeignKey("agendamentos.id"))
    enviar_em: Mapped[datetime] = mapped_column(DateTime, index=True)
    status: Mapped[StatusNotificacao] = mapped_column(
        _enum(StatusNotificacao), default=StatusNotificacao.AGENDADA, index=True
    )
    enviada_em: Mapped[datetime | None] = mapped_column(DateTime)
    resposta: Mapped[str | None] = mapped_column(String(200))
    erro: Mapped[str | None] = mapped_column(String(300))

    contato: Mapped[Contato] = relationship()
    agendamento: Mapped[Agendamento | None] = relationship()


# --- Sistema externo e operação ---------------------------------------------------------------------

class LeituraExterna(Base):
    """Cada leitura da agenda oficial. O bot só oferece horário se a última for válida e recente."""

    __tablename__ = "leituras_externas"
    id: Mapped[int] = mapped_column(primary_key=True)
    iniciada_em: Mapped[datetime] = mapped_column(DateTime)
    concluida_em: Mapped[datetime | None] = mapped_column(DateTime)
    ok: Mapped[bool] = mapped_column(Boolean, default=False)
    linhas: Mapped[int] = mapped_column(Integer, default=0)
    erro: Mapped[str | None] = mapped_column(Text)
    ate: Mapped[date | None] = mapped_column(Date)


class OcupacaoExterna(Base):
    """Horário ocupado no sistema externo (foto da última leitura). Do CPF, só o hash."""

    __tablename__ = "ocupacao_externa"
    id: Mapped[int] = mapped_column(primary_key=True)
    data: Mapped[date] = mapped_column(Date, index=True)
    horario: Mapped[time] = mapped_column(Time)
    codigo: Mapped[str] = mapped_column(String(40))
    cpf_hash: Mapped[str | None] = mapped_column(String(64), index=True)


class Batimento(Base):
    __tablename__ = "batimentos"
    nome: Mapped[str] = mapped_column(String(40), primary_key=True)
    em: Mapped[datetime] = mapped_column(DateTime)
    detalhe: Mapped[str | None] = mapped_column(Text)
