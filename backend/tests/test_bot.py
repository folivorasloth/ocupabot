from datetime import date, datetime, time

from sqlalchemy import select

from ocupabot import db, relogio
from ocupabot.enums import EstadoConversa, StatusAgendamento, StatusAprovacao, TipoAprovacao
from ocupabot.modelos import Agendamento, Aprovacao, Contato, Conversa, Mensagem
from ocupabot.seeds import gerar_cpf
from ocupabot.servicos import parametros

from .util import TEL_RH
from .util import Conversa as Fala

CPF = gerar_cpf("529982247")


def _conversa(tel):
    with db.sessao() as s:
        c = s.scalar(select(Contato).where(Contato.telefone == tel))
        return s.scalar(select(Conversa).where(Conversa.contato_id == c.id))


def agendar_periodico_rh(f: Fala) -> str:
    assert "1 - Agendar" in f.diz("Bom dia")
    r = f.diz("1")
    assert "Alfa Fictícia" in r and "tipo de exame" in r
    assert "Nome completo" in f.diz("2")  # periódico
    assert "CPF" in f.diz("Paciente Ficticio Silva")
    assert "nascimento" in f.diz(CPF)
    assert "Quais exames" in f.diz("10/02/1990")
    return f.diz("1,4")  # clínico + audiometria


def test_rh_agenda_e_pedido_espera_aprovacao():
    f = Fala(TEL_RH)
    r = agendar_periodico_rh(f)
    # audiometria só seg/ter/qui manhã; quinta 05/11 9h, com 60 min de antecedência -> hoje às 10:10
    assert "qui 05/11 às 10:10" in r
    r = f.diz("sim")
    assert "A equipe vai conferir" in r
    with db.sessao() as s:
        ag = s.scalar(select(Agendamento))
        assert ag.status == StatusAgendamento.AGUARDANDO_APROVACAO
        assert {i.profissional_id for i in ag.itens} and len({i.profissional_id for i in ag.itens}) == 2
        ap = s.scalar(select(Aprovacao))
        assert ap.tipo == TipoAprovacao.NOVO and ap.status == StatusAprovacao.PENDENTE


def test_cpf_e_rg_nao_ficam_nas_mensagens():
    f = Fala(TEL_RH)
    agendar_periodico_rh(f)
    with db.sessao() as s:
        textos = [m.texto for m in s.scalars(select(Mensagem))]
    assert not any(CPF in t for t in textos)
    assert any("[CPF]" in t for t in textos)


def test_recusar_sugestao_lista_e_escolhe():
    f = Fala(TEL_RH)
    agendar_periodico_rh(f)
    r = f.diz("não")
    assert "Horários livres" in r and "seg 09/11" in r
    r = f.diz("10/11 08:00")
    assert "Confere" in r and "ter 10/11 às 08:00" in r
    assert "Recebi o pedido" in f.diz("SIM")


def test_dia_sem_audiometria_e_horario_ocupado():
    f = Fala(TEL_RH)
    agendar_periodico_rh(f)
    r = f.diz("11/11")  # quarta: sem audiometria
    assert "Não tenho vaga em qua 11/11" in r
    r = f.diz("10/11 14:00")  # terça à tarde não tem fono
    assert "não está livre" in r


def test_particular_admissional_pede_rg_setor_cargo():
    f = Fala()
    f.diz("oi")
    assert "Empresa" in f.diz("1")
    assert "tipo de exame" in f.diz("2")  # particular
    f.diz("1")  # admissional
    f.diz("Joana Particular Inventada")
    f.diz(gerar_cpf("291417776"))
    assert "RG" in f.diz("03/03/1988")
    assert "Setor" in f.diz("12.345.678-9")
    assert "Função" in f.diz("Produção")
    assert "Quais exames" in f.diz("Operadora")
    assert "mais próximo" in f.diz("1")


def test_especialista_vai_para_equipe():
    f = Fala(TEL_RH)
    f.diz("oi")
    f.diz("1")
    f.diz("6")
    f.diz("Dono Eeg Ficticio")
    f.diz(CPF)
    f.diz("20/05/1980")
    r = f.diz("7")  # EEG
    assert "especialistas" in r
    assert _conversa(TEL_RH).estado == EstadoConversa.AGUARDANDO_HUMANO
    assert f.diz("alguém aí?") == ""  # com a equipe, o bot não responde


def test_atendente_no_meio_do_fluxo():
    f = Fala(TEL_RH)
    f.diz("oi")
    f.diz("1")
    assert "equipe" in f.diz("quero falar com um atendente")
    conv = _conversa(TEL_RH)
    assert conv.estado == EstadoConversa.AGUARDANDO_HUMANO and conv.motivo_humano == "pedido do contato"


def test_tres_erros_chamam_equipe():
    f = Fala(TEL_RH)
    f.diz("oi")
    assert "não entendi" in f.diz("banana")
    assert "não entendi" in f.diz("abacaxi")
    assert "equipe" in f.diz("uva")
    assert _conversa(TEL_RH).estado == EstadoConversa.AGUARDANDO_HUMANO


def test_sair_e_voltar():
    f = Fala(TEL_RH)
    f.diz("oi")
    assert "não vai mais receber" in f.diz("SAIR")
    assert "Quer voltar" in f.diz("oi")
    assert "voltou a receber" in f.diz("sim")


def test_cnpj_invalido_e_sem_cadastro():
    f = Fala()
    f.diz("oi")
    f.diz("1")
    f.diz("1")  # empresa
    assert "não parece válido" in f.diz("12.345.678/0001-00")
    assert "Não encontrei" in f.diz("11.444.777/0001-61")
    assert _conversa(f.tel).estado == EstadoConversa.AGUARDANDO_HUMANO


def test_empresa_pelo_nome():
    f = Fala()
    f.diz("oi")
    f.diz("1")
    f.diz("1")
    assert "Empresa: Beta Inventada" in f.diz("beta")


def test_pedido_de_resultado():
    f = Fala(TEL_RH)
    assert "não enviamos resultado" in f.diz("quero o resultado do meu exame")


def test_mensagem_repetida_e_ignorada():
    with db.sessao() as s:
        from ocupabot.bot.maquina import processar

        assert processar(s, TEL_RH, "oi", id_externo="x1")
        assert processar(s, TEL_RH, "oi", id_externo="x1") == []


def test_fluxo_largado_recomeca():
    f = Fala(TEL_RH)
    f.diz("oi")
    f.diz("1")
    relogio.fixar(datetime(2026, 11, 6, 9, 0))  # 24 h depois
    r = f.diz("2")
    assert "deixei esse agendamento de lado" in r
    relogio.fixar(datetime(2026, 11, 5, 9, 0))


def test_sem_aprovacao_agenda_direto():
    with db.sessao() as s:
        p = s.get(parametros.Parametro, "aprovacao_equipe")
        p.valor = "false"
    f = Fala(TEL_RH)
    agendar_periodico_rh(f)
    assert "Agendado!" in f.diz("sim")
    with db.sessao() as s:
        assert s.scalar(select(Agendamento)).status == StatusAgendamento.AGENDADO


def test_fora_do_expediente_avisa():
    relogio.fixar(datetime(2026, 11, 5, 21, 0))
    f = Fala(TEL_RH)
    r = f.diz("boa noite")
    assert "Nossa equipe atende" in r and "1 - Agendar" in r
    relogio.fixar(datetime(2026, 11, 5, 9, 0))
    assert date(2026, 11, 5) and time(9)
