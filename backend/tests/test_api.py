from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from ocupabot import db, relogio
from ocupabot.api.app import criar_app
from ocupabot.bot import rajadas
from ocupabot.modelos import Auditoria, Exame
from ocupabot.seeds import gerar_cpf

from .conftest import AGORA


@pytest.fixture
def app():
    return criar_app(inicializar=False)


def cliente(app, login="recepcao") -> TestClient:
    c = TestClient(app)
    r = c.post("/api/auth/login", json={"login": login, "senha": "senha-teste"})
    assert r.status_code == 200, r.text
    return c


def _exame(codigo):
    with db.sessao() as s:
        return s.scalar(select(Exame.id).where(Exame.codigo == codigo))


def test_sem_login_401(app):
    assert TestClient(app).get("/api/agenda").status_code == 401


def test_login_errado_e_limite(app):
    c = TestClient(app)
    for _ in range(5):
        assert c.post("/api/auth/login", json={"login": "x", "senha": "y"}).status_code == 401
    assert c.post("/api/auth/login", json={"login": "x", "senha": "y"}).status_code == 429


def test_cookie_httponly_e_cabecalhos(app):
    c = TestClient(app)
    r = c.post("/api/auth/login", json={"login": "admin", "senha": "senha-teste"})
    assert "httponly" in r.headers["set-cookie"].lower()
    assert r.headers["x-frame-options"] == "DENY"


def test_criar_agendamento_e_vagas(app):
    c = cliente(app)
    audio = _exame("AUDIO")
    r = c.get("/api/vagas", params={"data": "2026-11-10", "exames": [audio]})
    assert "08:00" in r.json()["horarios"]
    corpo = {"paciente_nome": "Ana Ficticia", "paciente_cpf": gerar_cpf("111444777"), "exame_ids": [audio],
             "data": "2026-11-10", "horario": "08:00", "contato_telefone": "11900000005"}
    r = c.post("/api/agendamentos", json=corpo)
    assert r.status_code == 201, r.text
    ag = r.json()
    assert ag["paciente"]["cpf"].startswith("***") and ag["exames"][0]["profissional"]
    # mesma vaga de novo, mesma fono: ocupado
    corpo["paciente_cpf"] = gerar_cpf("222555888")
    assert c.post("/api/agendamentos", json=corpo).status_code == 409
    # presença e falta só a partir do dia do exame
    assert c.post(f"/api/agendamentos/{ag['id']}/falta").status_code == 422
    relogio.fixar(datetime(2026, 11, 10, 12, 0))
    assert c.post(f"/api/agendamentos/{ag['id']}/falta").status_code == 200
    assert c.get("/api/agenda", params={"de": "2026-11-10"}).json()[0]["status"] == "FALTOU"
    with db.sessao() as s:
        assert s.scalar(select(Auditoria).where(Auditoria.entidade == "agendamento", Auditoria.acao == "falta"))


def test_encaixe_exige_supervisao(app):
    c = cliente(app)
    corpo = {"paciente_nome": "Encaixe Ficticio", "exame_ids": [_exame("CLINICO")], "data": "2026-11-10",
             "horario": "12:00", "forcar": True}
    assert c.post("/api/agendamentos", json=corpo).status_code == 403
    assert cliente(app, "supervisao").post("/api/agendamentos", json=corpo).status_code == 201


def test_perfis(app):
    c = cliente(app)  # recepção
    assert c.get("/api/agenda").status_code == 200
    assert c.get("/api/usuarios").status_code == 403
    assert c.get("/api/auditoria").status_code == 403
    assert cliente(app, "supervisao").get("/api/auditoria").status_code == 200
    # o perfil LEITURA não existe mais
    r = cliente(app, "admin").post("/api/usuarios", json={"nome": "Sem Perfil", "login": "semperfil",
                                                          "senha": "uma-senha-boa", "perfil": "LEITURA"})
    assert r.status_code == 422


def test_simulador_e_aprovacao(app):
    c = cliente(app)
    for t in ["oi", "1", "1", "Beta", "2", "Rui Ficticio Alves", gerar_cpf("341672110"), "01/04/1985", "1"]:
        r = c.post("/api/simulador/mensagem", json={"telefone": "5500000000077", "texto": t})
        assert r.status_code == 200, r.text
    assert "mais próximo" in r.json()["respostas"][-1]
    c.post("/api/simulador/mensagem", json={"telefone": "5500000000077", "texto": "sim"})
    pend = c.get("/api/aprovacoes").json()
    assert len(pend) == 1 and pend[0]["tipo"] == "NOVO"
    assert "RH não confirmado" in pend[0]["marcadores"]  # quem pediu não é RH confirmado da Beta
    # a equipe não agenda outro horário por conta própria: propõe, e só o 1 da pessoa agenda
    r = c.post(f"/api/aprovacoes/{pend[0]['id']}/propor", json={"data": "2026-11-12", "horario": "09:00"})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "AGUARDANDO_CLIENTE" and c.get("/api/aprovacoes").json() == []
    assert len(c.get("/api/aprovacoes", params={"status": "AGUARDANDO_CLIENTE"}).json()) == 1
    conv = c.get("/api/conversas").json()[0]
    msgs = c.get(f"/api/conversas/{conv['id']}").json()["mensagens"]
    assert msgs[-1]["autor"] == "EQUIPE" and "qui 12/11 às 09:00" in msgs[-1]["texto"]
    r = c.post("/api/simulador/mensagem", json={"telefone": "5500000000077", "texto": "1"})
    assert "Agendado!" in r.json()["respostas"][-1] and r.json()["conversa"]["estado"] == "BOT"
    assert c.get("/api/agenda", params={"de": "2026-11-12"}).json()[0]["status"] == "AGENDADO"
    assert len(c.get("/api/aprovacoes", params={"status": "APROVADA"}).json()) == 1


def test_assumir_responder_devolver(app):
    c = cliente(app)
    c.post("/api/simulador/mensagem", json={"telefone": "5500000000088", "texto": "oi"})
    cid = c.get("/api/conversas").json()[0]["id"]
    assert c.post(f"/api/conversas/{cid}/assumir").json()["estado"] == "HUMANO"
    r = c.post("/api/simulador/mensagem", json={"telefone": "5500000000088", "texto": "1"})
    assert r.json()["respostas"] == []  # bot calado
    assert c.post(f"/api/conversas/{cid}/responder", json={"texto": "Olá, aqui é a recepção"}).status_code == 200
    assert c.post(f"/api/conversas/{cid}/devolver").json()["estado"] == "BOT"


def test_webhook_token(app):
    c = TestClient(app)
    corpo = {"event": "message", "payload": {"id": "w1", "from": "5511900000001@c.us", "body": "oi"}}
    assert c.post("/api/webhook/whatsapp", json=corpo).status_code == 401
    fora_do_ascii = {"X-Webhook-Token": "tökén".encode("latin-1")}
    assert c.post("/api/webhook/whatsapp", json=corpo, headers=fora_do_ascii).status_code == 401
    with db.sessao() as s:  # as recusas ficam na auditoria
        assert len(s.scalars(select(Auditoria).where(Auditoria.acao == "webhook_recusado")).all()) == 2
    cab = {"X-Webhook-Token": "token-teste"}
    assert c.post("/api/webhook/whatsapp", json=corpo, headers=cab).json() == {"guardada": True}
    assert c.post("/api/webhook/whatsapp", json=corpo, headers=cab).json() == {"guardada": False}  # repetida
    corpo["payload"] = {"id": "w2", "from": "5511900000001@c.us", "body": "bom dia"}
    c.post("/api/webhook/whatsapp", json=corpo, headers=cab)
    assert rajadas.responder_vencidas() == 0 and canal_teste().enviadas == []  # ainda dentro da janela
    relogio.fixar(datetime(2026, 11, 5, 9, 0, 30))
    assert rajadas.responder_vencidas() == 1
    assert len(canal_teste().enviadas) == 1 and "1 - Agendar" in canal_teste().enviadas[0][1]  # UMA resposta
    relogio.fixar(AGORA)


def canal_teste():
    from ocupabot.integracoes.mensageria import canal

    return canal()


def test_webhook_sem_janela_responde_na_hora(app):
    adm = cliente(app, "admin")
    assert adm.put("/api/parametros/agrupar_mensagens_segundos", json={"valor": "0"}).status_code == 200
    corpo = {"event": "message", "payload": {"id": "w9", "from": "5511900000001@c.us", "hasMedia": True}}
    r = TestClient(app).post("/api/webhook/whatsapp", json=corpo, headers={"X-Webhook-Token": "token-teste"})
    assert r.json() == {"respostas": 1}
    assert "Não consigo ouvir áudio" in canal_teste().enviadas[0][1]


def test_parametros_e_textos(app):
    adm = cliente(app, "admin")
    assert adm.put("/api/parametros/envios_automaticos", json={"valor": "talvez"}).status_code == 422
    assert adm.put("/api/parametros/passo_min", json={"valor": "0"}).status_code == 422  # fora da faixa
    assert adm.put("/api/parametros/lembrete_hora", json={"valor": "25:99"}).status_code == 422
    assert adm.put("/api/parametros/envios_automaticos", json={"valor": "true"}).status_code == 200
    assert cliente(app).put("/api/parametros/envios_automaticos", json={"valor": "false"}).status_code == 403
    sup = cliente(app, "supervisao")
    assert sup.put("/api/textos/menu", json={"valor": "Oi {inexistente}"}).status_code == 422
    assert sup.put("/api/textos/menu", json={"valor": "Bem-vindo à {clinica}!\n1 - Agendar"}).status_code == 200
    r = sup.post("/api/textos/previa", json={"texto": "Olá {paciente} {solta e {0}"})
    assert r.json()["texto"] == "Olá Maria {solta e {0}"  # chave solta não derruba
    # voltar à versão anterior e ao texto original
    assert sup.put("/api/textos/menu", json={"valor": "Segunda versão"}).status_code == 200
    assert sup.post("/api/textos/menu/voltar").json()["texto"].startswith("Bem-vindo")
    assert "1 - Agendar exame" in sup.post("/api/textos/menu/voltar", params={"original": True}).json()["texto"]


def test_excecao_previa_e_aviso(app):
    c = cliente(app)
    audio = _exame("AUDIO")
    c.post("/api/agendamentos", json={"paciente_nome": "Ana Ficticia", "exame_ids": [audio], "data": "2026-11-10",
                                      "horario": "08:00", "contato_telefone": "11900000005"})
    profs = cliente(app, "supervisao").get("/api/profissionais").json()
    fono = next(p for p in profs if p["nome"].startswith("Fono"))
    corpo = {"profissional_id": fono["id"], "tipo": "FERIAS", "data_inicio": "2026-11-10",
             "data_fim": "2026-11-10", "avisar_afetados": True}
    assert len(c.post("/api/excecoes/previa", json=corpo).json()) == 1
    r = c.post("/api/excecoes", json=corpo).json()
    assert r["afetados"] == 1 and r["avisos"] == 1
    assert c.post("/api/excecoes", json=corpo).status_code == 409  # repetida
    corpo.update(turno="MANHA")  # outra exceção no mesmo dia: quem já foi avisado não recebe de novo
    r = c.post("/api/excecoes", json=corpo).json()
    assert r["afetados"] == 1 and r["avisos"] == 0
    assert c.post("/api/excecoes", json={**corpo, "profissional_id": 999999}).status_code == 422


def test_saude_e_hoje(app):
    c = cliente(app)
    assert TestClient(app).get("/api/saude").json()["banco"] == "ok"
    h = c.get("/api/painel/hoje").json()
    assert "alertas" in h and h["aprovacoes_pendentes"] == 0
