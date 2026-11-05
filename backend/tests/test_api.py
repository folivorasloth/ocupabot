import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from ocupabot import db
from ocupabot.api.app import criar_app
from ocupabot.modelos import Auditoria, Exame
from ocupabot.seeds import gerar_cpf


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


def test_perfil_leitura(app):
    c = cliente(app, "consulta")
    assert c.get("/api/agenda").status_code == 200
    assert c.post("/api/agendamentos", json={}).status_code in (403, 422)
    assert c.get("/api/usuarios").status_code == 403


def test_simulador_e_aprovacao(app):
    c = cliente(app)
    for t in ["oi", "1", "1", "Beta", "2", "Rui Ficticio Alves", gerar_cpf("341672110"), "01/04/1985", "1"]:
        r = c.post("/api/simulador/mensagem", json={"telefone": "5500000000077", "texto": t})
        assert r.status_code == 200, r.text
    assert "mais próximo" in r.json()["respostas"][-1]
    c.post("/api/simulador/mensagem", json={"telefone": "5500000000077", "texto": "sim"})
    pend = c.get("/api/aprovacoes").json()
    assert len(pend) == 1 and pend[0]["tipo"] == "NOVO"
    r = c.post(f"/api/aprovacoes/{pend[0]['id']}/aprovar", json={"data": "2026-11-12", "horario": "09:00"})
    assert r.status_code == 200, r.text
    assert c.get("/api/aprovacoes").json() == []
    conv = c.get("/api/conversas").json()[0]
    msgs = c.get(f"/api/conversas/{conv['id']}").json()["mensagens"]
    assert msgs[-1]["autor"] == "EQUIPE" and "qui 12/11 às 09:00" in msgs[-1]["texto"]
    # consulta não lê mensagens
    assert cliente(app, "consulta").get(f"/api/conversas/{conv['id']}").json()["mensagens"] == []


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
    r = c.post("/api/webhook/whatsapp", json=corpo, headers={"X-Webhook-Token": "token-teste"})
    assert r.status_code == 200 and r.json()["respostas"] == 1
    r = c.post("/api/webhook/whatsapp", json=corpo, headers={"X-Webhook-Token": "token-teste"})
    assert r.json()["respostas"] == 0  # repetida


def test_parametros_e_textos(app):
    adm = cliente(app, "admin")
    assert adm.put("/api/parametros/envios_automaticos", json={"valor": "talvez"}).status_code == 422
    assert adm.put("/api/parametros/envios_automaticos", json={"valor": "true"}).status_code == 200
    assert cliente(app).put("/api/parametros/envios_automaticos", json={"valor": "false"}).status_code == 403
    sup = cliente(app, "supervisao")
    assert sup.put("/api/textos/menu", json={"valor": "Oi {inexistente}"}).status_code == 422
    assert sup.put("/api/textos/menu", json={"valor": "Bem-vindo à {clinica}!\n1 - Agendar"}).status_code == 200
    r = sup.post("/api/textos/previa", json={"texto": "Olá {paciente}"})
    assert r.json()["texto"] == "Olá Maria"


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


def test_saude_e_hoje(app):
    c = cliente(app)
    assert TestClient(app).get("/api/saude").json()["banco"] == "ok"
    h = c.get("/api/painel/hoje").json()
    assert "alertas" in h and h["aprovacoes_pendentes"] == 0
