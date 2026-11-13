"""Painel: senha, perfis, proteções da API, dados pessoais, quem agenda e PCMSO."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from ocupabot import db
from ocupabot.api.app import criar_app
from ocupabot.modelos import Auditoria, Contato, Exame, Parametro
from ocupabot.seeds import gerar_cpf

from .test_api import cliente

BOA = "uma-senha-boa-2026"


@pytest.fixture
def app():
    return criar_app(inicializar=False)


def _novo(adm, login="fulana", **extra):
    return adm.post("/api/usuarios", json={"nome": "Fulana Ficticia", "login": login, "senha": BOA,
                                           "perfil": "RECEPCAO", **extra})


# --- senha e usuários -----------------------------------------------------------------------------------

@pytest.mark.parametrize("senha", ["curta123", "12345678901234", "senha12345", "a-fulana-2026"])
def test_politica_de_senha(app, senha):
    r = cliente(app, "admin").post("/api/usuarios", json={"nome": "Fulana Ficticia", "login": "fulana",
                                                          "senha": senha, "perfil": "RECEPCAO"})
    assert r.status_code == 422 and senha not in r.text  # o erro não devolve o que foi digitado


def test_senha_dada_pelo_admin_e_trocada_no_primeiro_acesso(app):
    adm = cliente(app, "admin")
    assert _novo(adm).json()["trocar_senha"] is True
    c = TestClient(app)
    assert c.post("/api/auth/login", json={"login": "Fulana", "senha": BOA}).json()["trocar_senha"]  # sem maiúscula
    assert c.get("/api/agenda").status_code == 403  # nada funciona antes de trocar
    assert c.post("/api/auth/senha", json={"atual": "errada", "nova": "outra-senha-boa"}).status_code == 403
    assert c.post("/api/auth/senha", json={"atual": BOA, "nova": BOA}).status_code == 422
    assert c.post("/api/auth/senha", json={"atual": BOA, "nova": "fulana-senha-boa"}).status_code == 422
    r = c.post("/api/auth/senha", json={"atual": BOA, "nova": "outra-senha-boa"})
    assert r.status_code == 200 and r.json()["trocar_senha"] is False
    assert c.get("/api/agenda").status_code == 200  # a sessão continua com o cookie novo
    assert TestClient(app).post("/api/auth/login", json={"login": "fulana", "senha": BOA}).status_code == 401


def test_admin_e_o_ultimo_administrador(app):
    adm = cliente(app, "admin")
    eu = adm.get("/api/auth/eu").json()
    assert adm.patch(f"/api/usuarios/{eu['id']}", json={"perfil": "RECEPCAO"}).status_code == 409
    assert adm.patch(f"/api/usuarios/{eu['id']}", json={"ativo": False}).status_code == 409
    assert adm.patch(f"/api/usuarios/{eu['id']}", json={"senha": BOA}).status_code == 422  # a própria: pelo menu
    assert adm.patch(f"/api/usuarios/{eu['id']}", json={"nome": None, "perfil": None}).status_code == 200
    assert adm.patch("/api/usuarios/99999999999999999999999", json={"ativo": True}).status_code in (404, 422)
    outro = _novo(adm, "outroadmin").json()
    assert adm.patch(f"/api/usuarios/{outro['id']}", json={"perfil": "ADMIN"}).status_code == 200
    assert adm.patch(f"/api/usuarios/{eu['id']}", json={"perfil": "SUPERVISAO"}).status_code == 200
    assert adm.get("/api/usuarios").status_code == 401  # mudar o perfil derruba a sessão aberta


def test_whatsapp_do_usuario(app):
    adm = cliente(app, "admin")
    u = _novo(adm, whatsapp="(11) 98765-0001").json()
    assert u["whatsapp"] == "5511987650001"
    assert _novo(adm, "beltrana", whatsapp="11987650001").status_code == 409  # o número é de uma pessoa só
    assert _novo(adm, "beltrana", whatsapp="123").status_code == 422
    assert adm.patch(f"/api/usuarios/{u['id']}", json={"whatsapp": None}).json()["whatsapp"] is None


# --- proteções da API ---------------------------------------------------------------------------------

def test_recusas_de_login_vao_para_a_auditoria_e_viram_alerta_do_admin(app):
    c = TestClient(app)
    for _ in range(6):
        c.post("/api/auth/login", json={"login": "admin", "senha": "errada"})
    with db.sessao() as s:
        acoes = [a.acao for a in s.scalars(select(Auditoria).where(Auditoria.entidade == "seguranca"))]
        assert acoes == ["login_recusado"] * 5 + ["login_bloqueado"]
        s.get(Parametro, "alerta_seguranca_limite").valor = "5"
    # o limite é por login + máquina: os outros logins continuam entrando
    assert not any("recusadas" in a["texto"] for a in cliente(app).get("/api/painel/hoje").json()["alertas"])
    alertas = cliente(app, "supervisao").get("/api/painel/hoje").json()["alertas"]
    assert not any("recusadas" in a["texto"] for a in alertas)  # só o admin vê


def test_alerta_de_seguranca_aparece_para_o_admin(app):
    adm = cliente(app, "admin")
    c = TestClient(app)
    for i in range(3):
        c.post("/api/auth/login", json={"login": f"ninguem{i}", "senha": "errada"})
    assert adm.put("/api/parametros/alerta_seguranca_limite", json={"valor": "2"}).status_code == 200
    assert any("3 tentativas de acesso recusadas" in a["texto"] for a in adm.get("/api/painel/hoje").json()["alertas"])


def test_escrita_com_cookie_so_vale_vinda_do_proprio_painel(app):
    c = cliente(app)
    de_fora = {"Origin": "https://outro-site.example"}
    assert c.post("/api/conversas/1/assumir", headers=de_fora).status_code == 403
    assert c.post("/api/conversas/1/assumir", headers={"Sec-Fetch-Site": "cross-site"}).status_code == 403
    assert c.get("/api/agenda", headers=de_fora).status_code == 200  # leitura não muda nada
    assert c.post("/api/conversas/1/assumir", headers={"Origin": "http://testserver"}).status_code == 404


def test_ambiente_e_cache(app):
    r = TestClient(app).get("/api/ambiente")
    assert r.status_code == 200 and r.json()["clinica"] and r.headers["cache-control"] == "no-store"


def test_segredo_publicado_nao_sobe_com_whatsapp(monkeypatch):
    from ocupabot.config import config

    monkeypatch.setenv("OCUPABOT_SEGREDO", "troque-este-valor")
    monkeypatch.setenv("OCUPABOT_CANAL", "waha")
    config.cache_clear()
    with pytest.raises(RuntimeError, match="OCUPABOT_SEGREDO"):
        criar_app()


# --- dados pessoais ------------------------------------------------------------------------------------

def test_texto_livre_recusa_cpf_e_erro_nao_repete_o_valor(app):
    c = cliente(app)
    cpf = gerar_cpf("111444777")
    with db.sessao() as s:
        clinico = s.scalar(select(Exame.id).where(Exame.codigo == "CLINICO"))
    corpo = {"paciente_nome": "Ana Ficticia", "exame_ids": [clinico], "data": "2026-11-10", "horario": "08:00",
             "observacao": f"cpf do pai {cpf}"}
    r = c.post("/api/agendamentos", json=corpo)
    assert r.status_code == 422 and "CPF ou RG" in r.json()["detail"] and cpf not in r.text
    corpo["observacao"] = "trazer exames anteriores"
    ag = c.post("/api/agendamentos", json=corpo).json()
    r = c.post(f"/api/agendamentos/{ag['id']}/cancelar", json={"motivo": "pediu, rg 12.345.678-9"})
    assert r.status_code == 422
    r = c.post("/api/pacientes", json={"nome": "Beto Ficticio", "cpf": cpf, "nascimento": "31/12/1990"})
    assert r.status_code == 422 and "1990" not in r.text
    assert c.post("/api/pacientes", json={"nome": "Beto Ficticio", "setor": f"setor {cpf}"}).status_code == 422
    assert c.post("/api/contatos", json={"telefone": "11987650009", "tipo": "INVENTADO"}).status_code == 422
    assert c.get("/api/agenda", params={"status": "<script>"}).json() == {"detail": "status inválido"}
    assert c.get("/api/pacientes/99999999999999999999999").status_code == 404


def test_auditoria_mascara_cpf_rg_e_nascimento(app):
    c = cliente(app)
    cpf = gerar_cpf("111444777")
    r = c.post("/api/pacientes", json={"nome": "Beto Ficticio", "cpf": cpf, "nascimento": "1990-12-31",
                                       "rg": "123456789"})
    assert r.status_code == 201 and r.json()["cpf"].startswith("***")
    with db.sessao() as s:
        foto = s.scalar(select(Auditoria).where(Auditoria.entidade == "paciente")).depois
    assert foto["cpf"] == f"***.{cpf[3:6]}.***-**" and foto["rg"] == foto["nascimento"] == "(informado)"


def test_resposta_da_equipe_sem_cpf_e_sem_quem_pediu_sair(app):
    c = cliente(app)
    c.post("/api/simulador/mensagem", json={"telefone": "5500000000088", "texto": "oi"})
    conv = c.get("/api/conversas").json()[0]
    r = c.post(f"/api/conversas/{conv['id']}/responder", json={"texto": f"seu cpf é {gerar_cpf('111444777')}?"})
    assert r.status_code == 422
    # SAIR registrado pela equipe no painel (a pessoa pediu por telefone)
    with db.sessao() as s:
        contato = s.scalar(select(Contato).where(Contato.telefone == "5511900000001"))
        contato_id = contato.id
    assert c.post(f"/api/contatos/{contato_id}/sair").json()["optout"] is True
    assert c.patch(f"/api/contatos/{contato_id}", json={"optout_em": None}).status_code == 422  # só pela rota própria
    with db.sessao() as s:
        assert s.scalar(select(Auditoria).where(Auditoria.entidade == "contato", Auditoria.acao == "sair"))
    assert c.post(f"/api/contatos/{contato_id}/sair", params={"ativo": False}).json()["optout"] is False


# --- quem agenda e PCMSO --------------------------------------------------------------------------------

def test_quem_agenda_por_varias_empresas(app):
    c = cliente(app)
    quem = {q["nome"]: q for q in c.get("/api/quem-agenda").json()}
    conta = quem["Contabilidade Fictícia"]
    assert [e["nome"] for e in conta["empresas"]] == ["Beta Inventada", "Gama Imaginária"]
    alfa = next(e for e in c.get("/api/empresas").json() if e["nome_fantasia"] == "Alfa Fictícia")
    r = c.put(f"/api/contatos/{conta['id']}/empresas/{alfa['id']}")
    assert len(r.json()["empresas"]) == 3 and r.json()["tipo"] == "CONTABILIDADE"
    beta = conta["empresas"][0]["id"]
    r = c.delete(f"/api/contatos/{conta['id']}/empresas/{beta}")  # tirar a principal: a próxima assume
    assert [e["nome"] for e in r.json()["empresas"]] == ["Alfa Fictícia", "Gama Imaginária"] or \
        [e["nome"] for e in r.json()["empresas"]] == ["Gama Imaginária", "Alfa Fictícia"]
    with db.sessao() as s:
        acoes = {a.acao for a in s.scalars(select(Auditoria).where(Auditoria.entidade == "contato"))}
    assert acoes == {"vincular_empresa", "desvincular_empresa"}
    # número novo confirmado como credenciadora de uma empresa
    novo = c.post("/api/contatos", json={"telefone": "(11) 98765-0002", "nome": "Credenciadora Fictícia"}).json()
    assert novo["telefone"] == "5511987650002"
    r = c.put(f"/api/contatos/{novo['id']}/empresas/{alfa['id']}", params={"tipo": "CREDENCIADORA"})
    assert r.json()["tipo"] == "CREDENCIADORA" and r.json()["empresa_id"] == alfa["id"]
    assert c.put(f"/api/contatos/{novo['id']}/empresas/{alfa['id']}", params={"tipo": "PARTICULAR"}).status_code == 422


def test_particular_com_telefone_ganha_o_contato_dos_avisos(app):
    c = cliente(app)
    r = c.post("/api/pacientes", json={"nome": "Carla Particular Ficticia", "telefone": "11 98765-0003"})
    assert r.status_code == 201 and r.json()["telefone"] == "5511987650003"
    with db.sessao() as s:
        contato = s.scalar(select(Contato).where(Contato.telefone == "5511987650003"))
        assert contato.tipo.value == "PARTICULAR" and contato.nome == "Carla Particular Ficticia"
    assert c.post("/api/pacientes", json={"nome": "Sem Numero Ficticio", "telefone": "123"}).status_code == 422


def test_pcmso_da_empresa_vira_alerta_no_hoje(app):
    c = cliente(app)
    textos = lambda: " | ".join(a["texto"] for a in c.get("/api/painel/hoje").json()["alertas"])  # noqa: E731
    assert "1 empresa ainda não mandou o PCMSO em vigor" in textos()  # a Gama do seed
    empresas = {e["nome_fantasia"]: e for e in c.get("/api/empresas").json()}
    c.patch(f"/api/empresas/{empresas['Gama Imaginária']['id']}", json={"pcmso_recebido": True,
                                                                      "pcmso_vence_em": "2026-11-20"})
    c.patch(f"/api/empresas/{empresas['Alfa Fictícia']['id']}", json={"pcmso_elaborado_por": "CLINICA",
                                                                    "pcmso_vence_em": "2026-10-01"})
    assert "1 empresa com PCMSO vencido" in textos() and "1 empresa com PCMSO vencendo" in textos()
    assert "ainda não mand" not in textos()
    r = c.patch(f"/api/empresas/{empresas['Beta Inventada']['id']}", json={"pcmso_elaborado_por": "OUTRO"})
    assert r.status_code == 422
    assert c.patch(f"/api/empresas/{empresas['Beta Inventada']['id']}", json={"razao_social": None}).status_code == 422
