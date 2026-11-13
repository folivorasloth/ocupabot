"""Bot: voltar um passo, várias empresas, mídia, texto livre, rajadas e comandos da equipe."""

from datetime import date, datetime, time

import pytest
from sqlalchemy import select

from ocupabot import db, relogio
from ocupabot.bot import rajadas
from ocupabot.enums import EstadoConversa, Origem, StatusAgendamento, StatusNotificacao, TipoNotificacao
from ocupabot.modelos import (
    Agendamento,
    Aprovacao,
    Auditoria,
    Contato,
    Conversa,
    EntradaPendente,
    Exame,
    Mensagem,
    Notificacao,
    Paciente,
    Usuario,
)
from ocupabot.seeds import gerar_cpf
from ocupabot.servicos import agenda, aprovacoes, parametros

from .conftest import AGORA
from .test_bot import CPF, agendar_periodico_rh
from .util import TEL_RH
from .util import Conversa as Fala

TEL_CONTABILIDADE = "5511900000002"  # agenda pela Beta e pela Gama (seed)
TEL_EQUIPE = "5511900000050"


def _conversa(tel):
    with db.sessao() as s:
        c = s.scalar(select(Contato).where(Contato.telefone == tel))
        return s.scalar(select(Conversa).where(Conversa.contato_id == c.id))


def _agendar(s, nome="Ana Ficticia Souza", d=date(2026, 11, 5), h=time(14, 0), contato=TEL_RH):
    pac = Paciente(nome=nome)
    s.add(pac)
    s.flush()
    c = s.scalar(select(Contato).where(Contato.telefone == contato))
    clinico = s.scalar(select(Exame).where(Exame.codigo == "CLINICO"))
    return agenda.criar(s, paciente_id=pac.id, exame_ids=[clinico.id], data=d, horario=h, origem=Origem.PAINEL,
                        contato_id=c.id)


# --- conversa -----------------------------------------------------------------------------------------

def test_voltar_um_passo_e_corrigir():
    f = Fala(TEL_RH)
    f.diz("oi")
    f.diz("1")
    assert "Nome completo" in f.diz("2")
    assert "CPF" in f.diz("Paciente Erado Silva")
    assert "Nome completo" in f.diz("voltar")  # corrige o nome
    assert "CPF" in f.diz("Paciente Certo Silva")
    assert "nascimento" in f.diz(CPF)
    assert "CPF" in f.diz("corrigir")
    assert "Nome completo" in f.diz("voltar")
    assert "tipo de exame" in f.diz("voltar")
    assert "1 - Agendar" in f.diz("voltar")  # acabou a trilha: menu
    f.diz("1")
    f.diz("2")
    f.diz("Paciente Certo Silva")
    f.diz(CPF)
    f.diz("10/02/1990")
    assert "mais próximo para Paciente Certo Silva" in f.diz("1")


def test_contabilidade_escolhe_a_empresa():
    f = Fala(TEL_CONTABILIDADE)
    f.diz("oi")
    r = f.diz("1")
    assert "Para qual empresa" in r and "1 - Beta Inventada" in r and "2 - Gama Imaginária" in r
    assert "Empresa: Gama Imaginária" in f.diz("2")
    r = f.diz("voltar")
    assert "Para qual empresa" in r
    assert "CNPJ" in f.diz("0")  # outra empresa: procura no cadastro
    assert "Empresa: Alfa Fictícia" in f.diz("alfa")
    f.diz("2")
    f.diz("Funcionario Da Alfa Ficticio")
    f.diz(gerar_cpf("291417776"))
    f.diz("03/03/1988")
    f.diz("1")
    f.diz("sim")
    with db.sessao() as s:
        ap = s.scalar(select(Aprovacao))
        # a contabilidade não é confirmada para a Alfa: a recepção confere antes de aprovar
        assert aprovacoes.MARCADOR_RH in aprovacoes.marcadores(s, ap)


def test_midia_recebe_aviso_sem_contar_erro():
    f = Fala(TEL_RH)
    f.diz("oi")
    for _ in range(4):
        assert "Não consigo ouvir áudio" in f.diz("[mídia]")
    assert _conversa(TEL_RH).estado == EstadoConversa.BOT


def test_oi_repetido_no_menu_nao_deixa_o_bot_mudo():
    f = Fala(TEL_RH)
    for _ in range(5):
        assert "1 - Agendar" in f.diz("oi")
    assert _conversa(TEL_RH).estado == EstadoConversa.BOT


@pytest.mark.parametrize("texto", ["quero cancelar meu exame", "preciso remarcar", "quanto custa o admissional?"])
def test_cancelar_remarcar_e_preco_vao_para_a_equipe(texto):
    f = Fala(TEL_RH)
    f.diz("oi")
    assert "equipe" in f.diz(texto)
    assert _conversa(TEL_RH).estado == EstadoConversa.AGUARDANDO_HUMANO


def test_sim_de_volta_vale_com_a_conversa_esperando_a_equipe():
    f = Fala(TEL_RH)
    f.diz("oi")
    f.diz("atendente")
    assert "não vai mais receber" in f.diz("sair")
    assert f.diz("oi") == ""  # a conversa está com a equipe (e já foi avisado)
    assert "voltou a receber" in f.diz("sim")
    with db.sessao() as s:
        assert s.scalar(select(Contato).where(Contato.telefone == TEL_RH)).optout_em is None
        acoes = [a.acao for a in s.scalars(select(Auditoria).where(Auditoria.entidade == "contato"))]
    assert acoes == ["sair", "voltar"]  # SAIR e a volta pelo WhatsApp ficam na auditoria


def test_numero_com_e_sem_o_nove_e_o_mesmo_contato():
    com_nove, sem_nove = "5511987650001", "551187650001"
    assert "não vai mais receber" in Fala(com_nove).diz("sair")
    assert "Quer voltar" in Fala(sem_nove).diz("oi")  # o SAIR vale para as duas formas do número
    with db.sessao() as s:
        assert len(s.scalars(select(Contato).where(Contato.telefone.in_([com_nove, sem_nove]))).all()) == 1


def test_cpf_ja_cadastrado_segue_a_mesma_conversa_e_vira_marcador():
    with db.sessao() as s:
        s.add(Paciente(nome="Paciente Antigo Silva", cpf=CPF, nascimento=date(1980, 1, 1)))
    f = Fala(TEL_RH)
    r = agendar_periodico_rh(f)  # nascimento 10/02/1990: diferente do cadastro, mas a conversa é a mesma
    assert "mais próximo para Paciente Ficticio Silva" in r
    assert "Recebi o pedido: Paciente" in f.diz("sim")
    with db.sessao() as s:
        ap = s.scalar(select(Aprovacao))
        assert ap.divergencia_cadastro and aprovacoes.MARCADOR_CADASTRO in aprovacoes.marcadores(s, ap)
        pac = s.scalar(select(Paciente).where(Paciente.cpf == CPF))
        assert pac.nome == "Paciente Antigo Silva" and pac.nascimento == date(1980, 1, 1)  # cadastro intacto


def test_cpf_nascimento_e_rg_nao_ficam_no_historico_nem_nos_dados():
    f = Fala()
    f.diz("oi")
    f.diz("1")
    f.diz("2")
    f.diz("1")  # admissional: pede RG
    f.diz("Joana Particular Inventada")
    f.diz("529 982 247 25")
    f.diz("03/03/1988")
    f.diz("12.345.678-9")
    f.diz("Produção")
    f.diz("Operadora")
    f.diz("1")
    f.diz("sim")
    with db.sessao() as s:
        textos = [m.texto for m in s.scalars(select(Mensagem))]
        assert {"[CPF]", "[NASCIMENTO]", "[RG]"} <= set(textos)
        assert not any("1988" in t or "529" in t or "345" in t for t in textos)
        fotos = str([a.depois for a in s.scalars(select(Auditoria))])
        assert "529" not in fotos and "1988" not in fotos and "12345678" not in fotos  # nem na auditoria
    assert _conversa(f.tel).dados == {}  # depois do pedido, nada sensível fica na conversa


def test_data_falada_e_antecedencia_minima():
    f = Fala(TEL_RH)
    agendar_periodico_rh(f)
    r = f.diz("não")
    assert "qui 05/11: 10:10" in r  # às 9h o bot não oferece antes das 10h (antecedência de 60 min)
    assert "Confere" in f.diz("segunda 8h")
    r = f.diz("voltar")
    assert "Horários livres" in r
    assert "seg 09/11 às 08:00" in f.diz("dia 9 às 8:00")


def test_resposta_antiga_a_aviso_nao_remarca_por_cima_da_equipe(ambiente):
    with db.sessao() as s:
        s.get(parametros.Parametro, "envios_automaticos").valor = "true"
        ag = _agendar(s, d=date(2026, 11, 10), h=time(8, 0))
        agenda.avisar_remarcacao(s, [ag])
        ag_id = ag.id
    from ocupabot.worker import rodada

    rodada()
    assert any("precisamos remarcar" in t for _, t in ambiente.enviadas)
    with db.sessao() as s:  # a equipe remarcou por telefone antes de a pessoa responder
        agenda.remarcar(s, s.get(Agendamento, ag_id), date(2026, 11, 12), time(8, 0))
    assert "equipe" in Fala(TEL_RH).diz("1")
    with db.sessao() as s:
        assert s.scalar(select(Aprovacao)) is None


# --- rajadas ------------------------------------------------------------------------------------------

def _chegou(tel, *textos):
    with db.sessao() as s:
        for i, t in enumerate(textos):
            assert rajadas.guardar(s, tel, t, f"{tel}-{relogio.agora():%H%M%S}-{i}")


def test_rajada_vira_uma_resposta_e_ignora_o_que_nao_avanca(ambiente):
    _chegou(TEL_RH, "oi", "bom dia", "1")
    assert rajadas.responder_vencidas() == 0  # a pessoa ainda pode estar escrevendo
    relogio.fixar(datetime(2026, 11, 5, 9, 0, 5))
    _chegou(TEL_RH, "2", "obrigado")  # mensagem nova adia a resposta: a conta é pela última
    relogio.fixar(datetime(2026, 11, 5, 9, 0, 10))
    assert rajadas.responder_vencidas() == 0
    relogio.fixar(datetime(2026, 11, 5, 9, 0, 14))
    assert rajadas.responder_vencidas() == 1
    assert len(ambiente.enviadas) == 1 and "Nome completo" in ambiente.enviadas[0][1]  # e não "não entendi"
    with db.sessao() as s:
        assert s.scalar(select(EntradaPendente)) is None
        recebidas = [m.texto for m in s.scalars(select(Mensagem).where(Mensagem.status == "RECEBIDA"))]
        assert recebidas == ["oi", "bom dia", "1", "2", "obrigado"]  # tudo fica no histórico
    assert _conversa(TEL_RH).etapa == "NOME" and _conversa(TEL_RH).erros_seguidos == 0
    relogio.fixar(AGORA)


def test_rajada_que_nao_para_responde_no_teto(ambiente):
    for seg in range(0, 61, 5):  # uma mensagem a cada 5 s: a janela de 8 s nunca fecha
        relogio.fixar(datetime(2026, 11, 5, 9, seg // 60, seg % 60))
        _chegou(TEL_RH, f"mensagem {seg}")
        feitas = rajadas.responder_vencidas()
        if seg < 60:
            assert feitas == 0
    assert feitas == 1 and len(ambiente.enviadas) == 1  # com 60 s de espera, responde mesmo assim
    relogio.fixar(AGORA)


# --- comandos da equipe ---------------------------------------------------------------------------------

@pytest.fixture
def equipe():
    with db.sessao() as s:
        s.scalar(select(Usuario).where(Usuario.login == "recepcao")).whatsapp = TEL_EQUIPE
        _agendar(s, "Ana Ficticia Souza", h=time(14, 0))
        _agendar(s, "Bruno Inventado Lima", h=time(15, 0))
    return Fala(TEL_EQUIPE)


def _status(nome):
    with db.sessao() as s:
        return [a.status.value for a in s.scalars(select(Agendamento).join(Paciente).where(Paciente.nome == nome)
                                                  .order_by(Agendamento.id))]


def test_equipe_ve_a_agenda_e_marca_presenca(equipe):
    r = equipe.diz("agenda")
    assert "qui 05/11 (2)" in r.lower() and "14:00 Ana S. (agendado)" in r and "15:00 Bruno L." in r
    r = equipe.diz("paciente das 14h compareceu")
    assert "Ana S., qui 05/11 às 14:00" in r and "marcar COMPARECEU?" in r
    assert _status("Ana Ficticia Souza") == ["AGENDADO"]  # nada muda sem o SIM
    assert "Feito: Ana S. marcado como COMPARECEU" in equipe.diz("sim")
    assert _status("Ana Ficticia Souza") == ["COMPARECEU"]
    with db.sessao() as s:
        a = s.scalar(select(Auditoria).where(Auditoria.acao == "presenca"))
        assert a.ator == "whatsapp_equipe" and a.usuario_id is not None


def test_equipe_marca_falta_pelo_nome_e_quem_agendou_e_avisado(equipe):
    r = equipe.diz("Bruno Lima não veio")
    assert "marcar FALTA?" in r and "Quem agendou recebe o aviso" in r
    assert "nada foi alterado" in equipe.diz("não")
    equipe.diz("bruno faltou")
    assert "FALTA" in equipe.diz("sim")
    assert _status("Bruno Inventado Lima") == ["FALTOU"]
    with db.sessao() as s:
        n = s.scalar(select(Notificacao).where(Notificacao.tipo == TipoNotificacao.FALTA))
        assert n.status == StatusNotificacao.AGENDADA


def test_equipe_remarca_e_cancela(equipe):
    assert "Para quando?" in equipe.diz("das 14h remarcou")
    r = equipe.diz("das 14h remarcou para 10/11 9h")
    assert "REMARCAR para ter 10/11 às 09:00?" in r
    assert "REMARCADO para ter 10/11 às 09:00" in equipe.diz("sim")
    assert _status("Ana Ficticia Souza") == ["REMARCADO", "AGENDADO"]
    equipe.diz("cancelar o das 15h")
    assert "CANCELADO" in equipe.diz("sim")
    assert _status("Bruno Inventado Lima") == ["CANCELADO"]
    assert "Não achei agendamento ativo" in equipe.diz("das 15h faltou")


def test_equipe_respeita_as_regras_do_painel(equipe):
    with db.sessao() as s:
        s.scalar(select(Agendamento).where(Agendamento.horario == time(14, 0))).no_sistema_externo = True
        _agendar(s, "Carla Imaginada Reis", d=date(2026, 11, 6), h=time(8, 0))
    assert "só com a Supervisão" in equipe.diz("das 14h cancelou")
    equipe.diz("amanhã das 8h compareceu")
    assert "só pode ser marcada a partir do dia" in equipe.diz("sim")
    assert _status("Carla Imaginada Reis") == ["AGENDADO"]


def test_equipe_escolhe_entre_varios_e_o_resto_segue_para_o_bot(equipe):
    with db.sessao() as s:
        _agendar(s, "Ana Outra Ficticia", h=time(14, 10))
    r = equipe.diz("ana chegou")
    assert "Achei mais de um" in r and "1) 14:00 Ana S." in r and "2) 14:10 Ana F." in r
    assert "Ana F., qui 05/11 às 14:10" in equipe.diz("2")
    equipe.diz("sim")
    assert _status("Ana Outra Ficticia") == ["COMPARECEU"]
    assert "1 - Agendar" in equipe.diz("oi")  # o que não é comando segue para o bot de sempre
    assert "Comandos da equipe" in equipe.diz("ajuda")
    assert "1 - Agendar" in Fala(TEL_RH).diz("agenda")  # quem não é da equipe não tem comando


# --- agenda -------------------------------------------------------------------------------------------

def test_lembrete_de_quem_marca_para_amanha_depois_da_hora_do_lembrete():
    relogio.fixar(datetime(2026, 11, 5, 17, 0))  # o lembrete das 16:00 já passou
    with db.sessao() as s:
        ag = _agendar(s, d=date(2026, 11, 6), h=time(8, 0))
        n = s.scalar(select(Notificacao).where(Notificacao.agendamento_id == ag.id,
                                               Notificacao.tipo == TipoNotificacao.LEMBRETE_D1))
        assert n is not None and n.enviar_em == datetime(2026, 11, 5, 17, 0)
    relogio.fixar(datetime(2026, 11, 5, 21, 0))  # tarde da noite: só a confirmação
    with db.sessao() as s:
        ag = _agendar(s, "Outro Ficticio Souza", d=date(2026, 11, 6), h=time(9, 0))
        tipos = {n.tipo for n in s.scalars(select(Notificacao).where(Notificacao.agendamento_id == ag.id))}
        assert tipos == {TipoNotificacao.CONFIRMACAO}
    relogio.fixar(AGORA)


def test_teto_de_data_e_presenca_so_a_partir_do_dia():
    with db.sessao() as s:
        with pytest.raises(agenda.OperacaoInvalida, match="longe demais"):
            _agendar(s, d=date(2028, 11, 6), h=time(8, 0))
        ag = _agendar(s, d=date(2026, 11, 6), h=time(8, 0))
        with pytest.raises(agenda.OperacaoInvalida, match="a partir do dia"):
            agenda.presenca(s, ag)
        assert ag.status == StatusAgendamento.AGENDADO
