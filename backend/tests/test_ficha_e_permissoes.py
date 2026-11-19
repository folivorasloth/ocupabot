"""Ficha numa mensagem só, conversa mais tolerante, permissão por pessoa, contatos, teste e PCMSO."""

from datetime import date, datetime, time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from ocupabot import db, relogio
from ocupabot.api.app import criar_app
from ocupabot.bot import intencoes as it
from ocupabot.bot import rajadas
from ocupabot.dominio import ficha
from ocupabot.enums import EstadoConversa, StatusAgendamento, TipoAprovacao
from ocupabot.modelos import (
    Agendamento,
    Aprovacao,
    Auditoria,
    Contato,
    Conversa,
    Exame,
    Mensagem,
    Notificacao,
    Paciente,
)
from ocupabot.seeds import gerar_cpf
from ocupabot.servicos import parametros

from .conftest import AGORA
from .test_api import cliente
from .test_bot import CPF
from .test_novidades import _agendar, _chegou, _conversa
from .util import TEL_RH
from .util import Conversa as Fala

HOJE = date(2026, 11, 5)
OUTRO_CPF = gerar_cpf("111444777")
BOA = "uma-senha-boa-2026"


@pytest.fixture
def app():
    return criar_app(inicializar=False)


# --- ficha ----------------------------------------------------------------------------------------------

@pytest.mark.parametrize("texto, esperado", [
    (f"Nome: Ana Souza Lima\nCPF: {CPF}\nNascimento: 14/05/1990\nFunção: Auxiliar de produção",
     {"nome": "Ana Souza Lima", "cpf": CPF, "nascimento": "1990-05-14", "cargo": "Auxiliar de produção"}),
    (f"ana souza lima {CPF[:3]}.{CPF[3:6]}.{CPF[6:9]}-{CPF[9:]} 14/05/1990 sem função",
     {"nome": "Ana Souza Lima", "cpf": CPF, "nascimento": "1990-05-14"}),
    (f"Candidato: Sr. Rui Alves / CPF: {CPF} / Nasc.: 01/02/85 / Cargo: Motorista",
     {"nome": "Rui Alves", "cpf": CPF, "nascimento": "1985-02-01", "cargo": "Motorista"}),
    (f"Ana Souza {CPF} e Rui Alves {OUTRO_CPF}", {}),  # dois pacientes: um não fica com o CPF do outro
    ("Auxiliar de produção, setor 2", {}),
    ("boa tarde, quero agendar um exame", {}),
])
def test_ler_ficha(texto, esperado):
    assert ficha.ler(texto, HOJE) == esperado


def test_ficha_numa_mensagem_pergunta_so_o_que_faltou():
    f = Fala(TEL_RH)
    f.diz("oi")
    f.diz("1")
    assert "Nome completo" in f.diz("2")  # periódico
    r = f.diz(f"Paciente Ficticio Silva, {CPF}, 10/02/1990")
    assert "Quais exames" in r and "CPF" not in r  # foi direto aos exames
    assert "mais próximo para Paciente Ficticio Silva" in f.diz("1")
    with db.sessao() as s:
        textos = [m.texto for m in s.scalars(select(Mensagem))]
    assert "[FICHA DO PACIENTE]" in textos and not any("1990" in t or CPF in t for t in textos)


def test_ficha_sem_passar_pelo_menu_e_faltando_o_nascimento():
    f = Fala(TEL_RH)
    r = f.diz(f"Nome: Paciente Ficticio Silva\nCPF: {CPF}")
    assert "Alfa Fictícia" in r and "tipo de exame" in r  # já é um agendamento
    assert "nascimento" in f.diz("2")  # só o que faltou
    assert "Quais exames" in f.diz("10/02/1990")
    assert "nascimento" in f.diz("voltar")  # voltar apaga e pergunta de novo o passo anterior
    assert "Quais exames" in f.diz("11/02/1990")


# --- conversa mais tolerante ----------------------------------------------------------------------------

def test_oi_e_obrigado_no_meio_da_conversa_nao_contam_erro():
    f = Fala(TEL_RH)
    f.diz("oi")
    f.diz("1")
    f.diz("2")
    for _ in range(4):
        assert "Nome completo" in f.diz("oi")  # refaz a pergunta de onde parou
        assert f.diz("obrigado") == "" and f.diz("👍") == ""
    conv = _conversa(TEL_RH)
    assert conv.estado == EstadoConversa.BOT and conv.etapa == "NOME" and conv.erros_seguidos == 0


def test_particular_por_extenso_e_empresa_sem_saber_o_cnpj():
    f = Fala()
    f.diz("oi")
    f.diz("1")
    assert "tipo de exame" in f.diz("é pra mim mesmo")
    g = Fala("5511900000011")
    g.diz("oi")
    g.diz("1")
    g.diz("1")
    assert "nome da empresa" in g.diz("não sei o CNPJ")
    assert "Empresa: Beta Inventada" in g.diz("beta")
    assert not it.quer_atendente("a recepção abre que horas?") and it.quer_atendente("quero falar com a recepção")


@pytest.mark.parametrize("texto, eh_nao", [
    ("não vou poder ir", True), ("infelizmente não vai dar", True), ("ele vai faltar", True), ("Não", True),
    ("não vou faltar", False), ("não sei se vou poder ir", False), ("não vou poder ir mas mando outro", False),
    ("posso ir mais tarde?", False),
])
def test_resposta_ao_lembrete(texto, eh_nao):
    assert it.eh_nao_ao_lembrete(texto) is eh_nao
    assert not it.eh_sim("pode ser à tarde?")


def test_lembrete_com_frase_de_ausencia_vira_pedido_de_cancelamento(ambiente):
    from ocupabot.worker import rodada

    with db.sessao() as s:
        s.get(parametros.Parametro, "envios_automaticos").valor = "true"
        ag_id = _agendar(s, d=date(2026, 11, 10), h=time(8, 0)).id
    relogio.fixar(datetime(2026, 11, 9, 16, 5))
    rodada()
    f = Fala(TEL_RH)
    assert "1 - Agendar" in f.diz("não vou faltar")  # não é resposta ao lembrete: nada é cancelado
    assert "pedi o cancelamento" in f.diz("não vou poder ir")
    with db.sessao() as s:
        ap = s.scalar(select(Aprovacao))
        assert ap.tipo == TipoAprovacao.CANCELAMENTO and ap.agendamento_id == ag_id
    relogio.fixar(AGORA)


def test_rajada_nao_confirma_o_que_a_pessoa_nao_viu(ambiente):
    f = Fala(TEL_RH)
    f.diz("oi")
    f.diz("1")
    f.diz("2")
    f.diz(f"Paciente Ficticio Silva, {CPF}, 10/02/1990")
    _chegou(TEL_RH, "1,4", "ok")  # o "ok" chegou antes de a pessoa ver o horário sugerido
    relogio.fixar(datetime(2026, 11, 5, 9, 0, 20))
    assert rajadas.responder_vencidas() == 1
    assert "Posso agendar?" in ambiente.enviadas[-1][1]
    with db.sessao() as s:
        assert s.scalar(select(Agendamento)) is None  # nada foi agendado
        assert s.scalar(select(Conversa)).etapa == "SUGESTAO"
    relogio.fixar(AGORA)


# --- permissão por pessoa e Supervisão em Usuários -----------------------------------------------------------

def test_supervisao_cuida_so_da_recepcao(app):
    sup, adm = cliente(app, "supervisao"), cliente(app, "admin")
    assert [u["login"] for u in sup.get("/api/usuarios").json()] == ["recepcao"]
    assert len(adm.get("/api/usuarios").json()) == 3
    novo = {"nome": "Fulana Ficticia", "login": "fulana", "senha": BOA, "perfil": "RECEPCAO"}
    assert sup.post("/api/usuarios", json={**novo, "perfil": "SUPERVISAO"}).status_code == 403
    criado = sup.post("/api/usuarios", json=novo).json()
    assert criado["trocar_senha"] is True and criado["pode_externo"] is False
    assert sup.patch(f"/api/usuarios/{criado['id']}", json={"perfil": "ADMIN"}).status_code == 403
    r = sup.patch(f"/api/usuarios/{criado['id']}", json={"pode_externo": True, "senha": "outra-senha-boa"})
    assert r.status_code == 200 and r.json()["pode_externo"] is True
    eu = sup.get("/api/auth/eu").json()
    admin_id = adm.get("/api/auth/eu").json()["id"]
    assert sup.patch(f"/api/usuarios/{eu['id']}", json={"nome": "Outra"}).status_code == 404  # nem a si mesma
    assert sup.patch(f"/api/usuarios/{admin_id}", json={"ativo": False}).status_code == 404
    assert cliente(app).get("/api/usuarios").status_code == 403


def test_recepcao_com_permissao_mexe_no_que_esta_no_externo(app):
    with db.sessao() as s:
        ag = _agendar(s, d=date(2026, 11, 10), h=time(8, 0))
        ag.no_sistema_externo = True
        ag_id = ag.id
    c = cliente(app)
    assert c.post(f"/api/agendamentos/{ag_id}/cancelar", json={"motivo": "pediu por telefone"}).status_code == 403
    sup = cliente(app, "supervisao")
    recepcao = sup.get("/api/usuarios").json()[0]
    assert sup.patch(f"/api/usuarios/{recepcao['id']}", json={"pode_externo": True}).status_code == 200
    assert c.get("/api/auth/eu").json()["pode_externo"] is True  # mudar a permissão não derruba a sessão
    assert c.post(f"/api/agendamentos/{ag_id}/cancelar", json={"motivo": "pediu por telefone"}).status_code == 200


# --- quem agenda pela empresa e contato desativado ------------------------------------------------------------

def test_whatsapp_do_rh_cadastrado_pela_empresa_e_contato_desativado(app):
    c = cliente(app)
    beta = next(e for e in c.get("/api/empresas").json() if e["nome_fantasia"] == "Beta Inventada")
    r = c.post(f"/api/empresas/{beta['id']}/contatos", json={"telefone": "(11) 98765-0007", "nome": "RH da Beta"})
    assert r.status_code == 201 and r.json()["tipo"] == "RH" and r.json()["empresas"][0]["nome"] == "Beta Inventada"
    novo = r.json()
    # número que já existe só liga (aqui, o RH da Alfa passa a agendar também pela Beta)
    r = c.post(f"/api/empresas/{beta['id']}/contatos", json={"telefone": TEL_RH})
    assert [e["nome"] for e in r.json()["empresas"]] == ["Alfa Fictícia", "Beta Inventada"]
    assert c.post(f"/api/empresas/{beta['id']}/contatos", json={"telefone": "123"}).status_code == 422
    # desativado: o bot trata como um número qualquer e não dá para ligar a outra empresa
    assert c.patch(f"/api/contatos/{novo['id']}", json={"ativo": False}).json()["ativo"] is False
    f = Fala("5511987650007")
    f.diz("oi")
    assert "empresa ou particular" in f.diz("1")
    r = c.post(f"/api/empresas/{beta['id']}/contatos", json={"telefone": "11987650007"})
    assert r.status_code == 409
    with db.sessao() as s:
        assert s.scalar(select(Contato).where(Contato.telefone == "5511987650007")) is not None  # nada é apagado
        assert s.scalar(select(Auditoria).where(Auditoria.acao == "criar_pela_empresa"))


# --- agenda: teste, CPF e contagem de exames -------------------------------------------------------------------

def _exame(codigo):
    with db.sessao() as s:
        return s.scalar(select(Exame.id).where(Exame.codigo == codigo))


def test_agendamento_de_teste(app, ambiente):
    from ocupabot.worker import rodada

    corpo = {"paciente_nome": "Teste Da Recepcao", "exame_ids": [_exame("CLINICO")], "data": "2026-11-10",
             "horario": "08:00", "contato_telefone": "11987650008"}
    assert cliente(app).post("/api/agendamentos", json=corpo).status_code == 403  # só Admin e Supervisão
    sup = cliente(app, "supervisao")
    ag = sup.post("/api/agendamentos", json=corpo).json()
    assert ag["teste"] is True and ag["contato"] is None
    with db.sessao() as s:
        s.get(parametros.Parametro, "envios_automaticos").valor = "true"
        assert s.scalar(select(Notificacao)) is None
    rodada()
    assert ambiente.enviadas == []  # teste não manda WhatsApp
    vagas = sup.get("/api/vagas", params={"data": "2026-11-10", "exames": [_exame("CLINICO")]}).json()["horarios"]
    assert "08:10" in vagas  # ocupa a vaga de um dos dois clínicos de terça... e a capacidade segue valendo
    assert sup.get("/api/agenda/exames", params={"de": "2026-11-10"}).json() == []  # e não conta nos números
    assert cliente(app).delete(f"/api/agendamentos/{ag['id']}/teste").status_code == 403
    assert sup.delete(f"/api/agendamentos/{ag['id']}/teste").status_code == 204
    with db.sessao() as s:
        assert s.scalar(select(Agendamento)) is None
        real = _agendar(s, d=date(2026, 11, 10), h=time(8, 0))
        real_id = real.id
    assert sup.delete(f"/api/agendamentos/{real_id}/teste").status_code == 422  # o de verdade é cancelado, não apagado


def test_empresa_do_sistema_externo_pede_o_cpf(app):
    c = cliente(app)
    empresas = {e["nome_fantasia"]: e for e in c.get("/api/empresas").json()}
    with db.sessao() as s:  # paciente antigo, só com o nome
        pac = Paciente(nome="Antigo Sem Cpf Ficticio")
        s.add(pac)
        s.flush()
        pac_id = pac.id
    corpo = {"paciente_id": pac_id, "empresa_id": empresas["Alfa Fictícia"]["id"], "exame_ids": [_exame("CLINICO")],
             "data": "2026-11-10", "horario": "08:00"}
    r = c.post("/api/agendamentos", json=corpo)
    assert r.status_code == 422 and "CPF" in r.json()["detail"]
    assert c.post("/api/agendamentos", json={**corpo, "paciente_cpf": OUTRO_CPF}).status_code == 201
    with db.sessao() as s:
        assert s.get(Paciente, pac_id).cpf == OUTRO_CPF  # ficou no cadastro, com auditoria
        assert s.scalar(select(Auditoria).where(Auditoria.entidade == "paciente", Auditoria.acao == "alterar"))
    # empresa que não é lançada no sistema externo não exige
    corpo = {"paciente_nome": "Outro Sem Cpf Ficticio", "empresa_id": empresas["Beta Inventada"]["id"],
             "exame_ids": [_exame("CLINICO")], "data": "2026-11-10", "horario": "09:00"}
    assert c.post("/api/agendamentos", json=corpo).status_code == 201


def test_quantos_de_cada_exame(app):
    with db.sessao() as s:
        _agendar(s, "Ana Ficticia Souza", d=date(2026, 11, 10), h=time(8, 0))
        _agendar(s, "Bruno Inventado Lima", d=date(2026, 11, 10), h=time(14, 0))
        cancelado = _agendar(s, "Carla Imaginada Reis", d=date(2026, 11, 11), h=time(8, 0))
        cancelado.status = StatusAgendamento.CANCELADO
    r = cliente(app).get("/api/agenda/exames", params={"de": "2026-11-09", "ate": "2026-11-15"}).json()
    assert r == [{"data": "2026-11-10", "turno": "MANHA", "exame": "Exame clínico", "quantos": 1},
                 {"data": "2026-11-10", "turno": "TARDE", "exame": "Exame clínico", "quantos": 1}]


# --- PCMSO ----------------------------------------------------------------------------------------------

def test_situacao_do_pcmso_de_todas_as_empresas(app):
    c = cliente(app)
    empresas = {e["nome_fantasia"]: e for e in c.get("/api/empresas").json()}
    c.patch(f"/api/empresas/{empresas['Alfa Fictícia']['id']}", json={"pcmso_elaborado_por": "CLINICA",
                                                                    "pcmso_vence_em": "2026-11-20"})
    r = c.get("/api/painel/pcmso").json()
    situacao = {e["nome"]: (e["situacao"], e["a_cobrar"]) for e in r["empresas"]}
    assert situacao == {"Alfa Fictícia": ("VENCE", True), "Beta Inventada": ("NAO_ACOMPANHADO", False),
                        "Gama Imaginária": ("NAO_RECEBIDO", True)}
    alerta = next(a for a in c.get("/api/painel/hoje").json()["alertas"] if "PCMSO" in a["texto"])
    assert alerta["para"] == "/cadastros?aba=pcmso"
    assert TestClient(app).get("/api/painel/pcmso").status_code == 401
