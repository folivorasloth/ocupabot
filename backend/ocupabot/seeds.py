"""Dados iniciais e um cenário 100% fictício para demonstração e testes."""

from __future__ import annotations

from datetime import time

from sqlalchemy import select
from sqlalchemy.orm import Session

from .dominio.documentos import _dv
from .enums import Perfil, TipoContato, Turno
from .modelos import (
    Contato,
    Empresa,
    Exame,
    Expediente,
    Funcao,
    Grade,
    Profissional,
    TipoAso,
    Usuario,
)
from .seguranca import hash_senha
from .servicos import parametros, textos

TIPOS_ASO = [
    ("ADMISSIONAL", "Admissional", True),
    ("PERIODICO", "Periódico", False),
    ("DEMISSIONAL", "Demissional", False),
    ("RETORNO", "Retorno ao trabalho", False),
    ("MUDANCA_FUNCAO", "Mudança de função", False),
    ("COMPLEMENTAR", "Só exames complementares", False),
]

FUNCOES = [
    # codigo, nome, capacidade/h, requer humano
    ("CLINICO", "Exame clínico", 6, False),
    ("AUDIOMETRIA", "Audiometria", 4, False),
    ("ENFERMAGEM", "Enfermagem (coletas e testes)", 6, False),
    ("ESPECIALISTA", "Especialistas (agenda própria)", None, True),
]

EXAMES = [
    ("CLINICO", "Exame clínico", "CLINICO"),
    ("ACUIDADE", "Acuidade visual", "ENFERMAGEM"),
    ("ESPIRO", "Espirometria", "ENFERMAGEM"),
    ("AUDIO", "Audiometria", "AUDIOMETRIA"),
    ("ECG", "Eletrocardiograma", "ENFERMAGEM"),
    ("LAB", "Exames laboratoriais", "ENFERMAGEM"),
    ("EEG", "Eletroencefalograma", "ESPECIALISTA"),
    ("PSICO", "Avaliação psicológica", "ESPECIALISTA"),
]


def gerar_cnpj(base12: str) -> str:
    d1 = _dv(base12, [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2])
    d2 = _dv(base12 + str(d1), [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2])
    return f"{base12}{d1}{d2}"


def gerar_cpf(base9: str) -> str:
    d1 = _dv(base9, list(range(10, 1, -1)))
    d2 = _dv(base9 + str(d1), list(range(11, 1, -1)))
    return f"{base9}{d1}{d2}"


def essenciais(s: Session) -> None:
    """Parâmetros, textos, tipos de ASO, funções, exames e expediente padrão (idempotente)."""
    parametros.garantir_padroes(s)
    textos.garantir_padroes(s)
    if not s.scalar(select(TipoAso.id).limit(1)):
        for i, (cod, nome, exige) in enumerate(TIPOS_ASO):
            s.add(TipoAso(codigo=cod, nome=nome, ordem=i, exige_cadastro_completo=exige))
    if not s.scalar(select(Funcao.id).limit(1)):
        for cod, nome, cap, humano in FUNCOES:
            s.add(Funcao(codigo=cod, nome=nome, capacidade_por_hora=cap, requer_humano=humano))
        s.flush()
        ids = {f.codigo: f.id for f in s.scalars(select(Funcao))}
        for i, (cod, nome, funcao) in enumerate(EXAMES):
            s.add(Exame(codigo=cod, nome=nome, funcao_id=ids[funcao], ordem=i))
    if not s.scalar(select(Expediente.id).limit(1)):
        for dia in range(5):
            s.add(Expediente(dia_semana=dia, turno=Turno.MANHA, inicio=time(7, 30), fim=time(11, 30)))
            s.add(Expediente(dia_semana=dia, turno=Turno.TARDE, inicio=time(13, 30), fim=time(16, 30)))
    s.flush()


def demonstracao(s: Session, senha_admin: str = "admin123") -> None:
    """Cenário fictício: 3 profissionais, 2 empresas, usuários de cada perfil."""
    essenciais(s)
    if s.scalar(select(Profissional.id).limit(1)):
        return
    f = {x.codigo: x.id for x in s.scalars(select(Funcao))}
    dra = Profissional(nome="Dra. Fictícia Clínica")
    fono = Profissional(nome="Fono Inventada")
    enf = Profissional(nome="Enf. Exemplo")
    s.add_all([dra, fono, enf])
    s.flush()
    for dia in range(5):
        for turno in (Turno.MANHA, Turno.TARDE):
            s.add(Grade(profissional_id=dra.id, funcao_id=f["CLINICO"], dia_semana=dia, turno=turno))
            s.add(Grade(profissional_id=enf.id, funcao_id=f["ENFERMAGEM"], dia_semana=dia, turno=turno))
            # a enfermeira também faz clínico de apoio: recurso único entre as duas funções
            if dia in (0, 2):
                s.add(Grade(profissional_id=enf.id, funcao_id=f["CLINICO"], dia_semana=dia, turno=turno))
        # audiometria só seg, ter e qui de manhã
        if dia in (0, 1, 3):
            s.add(Grade(profissional_id=fono.id, funcao_id=f["AUDIOMETRIA"], dia_semana=dia, turno=Turno.MANHA))
    alfa = Empresa(razao_social="Alfa Indústria Fictícia Ltda", nome_fantasia="Alfa Fictícia",
                   cnpj=gerar_cnpj("112223330001"), usa_sistema_externo=True, codigo_externo="1001")
    beta = Empresa(razao_social="Beta Serviços Inventados S.A.", nome_fantasia="Beta Inventada",
                   cnpj=gerar_cnpj("445556660001"))
    s.add_all([alfa, beta])
    s.flush()
    s.add(Contato(telefone="5511900000001", nome="RH Alfa (fictício)", tipo=TipoContato.RH, empresa_id=alfa.id))
    for login, nome, perfil in [
        ("admin", "Administração", Perfil.ADMIN),
        ("supervisao", "Supervisão", Perfil.SUPERVISAO),
        ("recepcao", "Recepção", Perfil.RECEPCAO),
        ("consulta", "Consulta", Perfil.LEITURA),
    ]:
        if not s.scalar(select(Usuario).where(Usuario.login == login)):
            s.add(Usuario(login=login, nome=nome, perfil=perfil, senha_hash=hash_senha(senha_admin)))
    s.flush()
