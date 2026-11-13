from datetime import date, datetime, time

import pytest
from sqlalchemy import select

from ocupabot import db, relogio
from ocupabot.enums import (
    Autor,
    EstadoConversa,
    Origem,
    Perfil,
    StatusAgendamento,
    StatusAprovacao,
    StatusNotificacao,
    TipoAprovacao,
    TipoNotificacao,
)
from ocupabot.modelos import Agendamento, Aprovacao, Contato, Conversa, Exame, Mensagem, Notificacao, Paciente
from ocupabot.servicos import agenda, aprovacoes, parametros
from ocupabot.worker import rodada

from .test_bot import agendar_periodico_rh
from .util import TEL_RH
from .util import Conversa as Fala

ADMIN = 1


def _pedido():
    f = Fala(TEL_RH)
    agendar_periodico_rh(f)
    f.diz("sim")
    return f


def test_aprovar_avisa_e_programa_lembrete(ambiente):
    _pedido()
    with db.sessao() as s:
        ap = s.scalar(select(Aprovacao))
        ag = aprovacoes.aprovar(s, ap, ADMIN, Perfil.RECEPCAO)
        assert ag.status == StatusAgendamento.AGENDADO
        tipos = {n.tipo for n in s.scalars(select(Notificacao))}
        assert tipos == {TipoNotificacao.LEMBRETE_D1} or tipos == set()  # exame hoje: sem lembrete
        equipe = s.scalars(select(Mensagem).where(Mensagem.autor == Autor.EQUIPE)).all()
        assert "Agendado!" in equipe[-1].texto
    rodada()
    assert any("Agendado!" in t for _, t in ambiente.enviadas)


def _propor(d=date(2026, 11, 12), h=time(9, 0)):
    with db.sessao() as s:
        ap = s.scalar(select(Aprovacao))
        pedido_id = ap.agendamento_id
        aprovacoes.propor(s, ap, ADMIN, Perfil.RECEPCAO, d, h)
        assert ap.status == StatusAprovacao.AGUARDANDO_CLIENTE and ap.alterada
        assert s.get(Agendamento, pedido_id).status == StatusAgendamento.CANCELADO  # a vaga pedida foi liberada
        assert ap.agendamento.status == StatusAgendamento.AGUARDANDO_APROVACAO  # a proposta segura a vaga
        assert h not in agenda.livres(s, d, [i.exame_id for i in ap.agendamento.itens])


def test_proposta_confirmada_pelo_cliente(ambiente):
    f = _pedido()
    _propor()
    rodada()
    assert any("Podemos em qui 12/11 às 09:00" in t for _, t in ambiente.enviadas)
    assert "não entendi" in f.diz("talvez")
    assert "Agendado! Paciente, qui 12/11 às 09:00" in f.diz("1")
    with db.sessao() as s:
        ap = s.scalar(select(Aprovacao))
        assert ap.status == StatusAprovacao.APROVADA and ap.decidida_por_id == ADMIN
        assert ap.agendamento.status == StatusAgendamento.AGENDADO
        assert s.scalar(select(Notificacao).where(Notificacao.tipo == TipoNotificacao.LEMBRETE_D1))
    assert "1 - Agendar" in f.diz("oi")  # a conversa voltou ao normal


def test_proposta_recusada_pelo_cliente_libera_a_vaga():
    f = _pedido()
    _propor()
    assert "combinar outro horário" in f.diz("2")
    with db.sessao() as s:
        ap = s.scalar(select(Aprovacao))
        assert ap.status == StatusAprovacao.RECUSADA
        assert ap.agendamento.status == StatusAgendamento.CANCELADO
        assert s.scalar(select(Conversa)).estado == EstadoConversa.AGUARDANDO_HUMANO


def test_proposta_vence_sem_resposta(ambiente):
    f = _pedido()
    _propor()
    relogio.fixar(datetime(2026, 11, 6, 9, 30))  # mais de 24 h depois
    assert rodada()["propostas"] == "1"
    with db.sessao() as s:
        ap = s.scalar(select(Aprovacao))
        assert ap.status == StatusAprovacao.EXPIRADA and ap.agendamento.status == StatusAgendamento.CANCELADO
        assert s.scalar(select(Conversa)).estado == EstadoConversa.AGUARDANDO_HUMANO
    assert not any("expirou" in t for _, t in ambiente.enviadas)  # nada sai sozinho para a pessoa
    assert "está com a nossa equipe" in f.diz("1")  # avisa uma vez
    assert f.diz("oi?") == ""
    relogio.fixar(datetime(2026, 11, 5, 9, 0))


def test_proposta_que_deixou_de_valer_e_cancelada_pela_equipe():
    f = _pedido()
    _propor()
    with db.sessao() as s:  # a fono entra de férias no dia proposto
        from ocupabot.enums import TipoExcecao
        from ocupabot.modelos import Excecao, Profissional

        fono = s.scalar(select(Profissional).where(Profissional.nome.like("Fono%")))
        s.add(Excecao(profissional_id=fono.id, tipo=TipoExcecao.FERIAS, data_inicio=date(2026, 11, 12),
                      data_fim=date(2026, 11, 12)))
    assert "não está mais livre" in f.diz("sim")
    with db.sessao() as s:
        assert s.scalar(select(Aprovacao)).status == StatusAprovacao.RECUSADA


def test_propor_tem_regras():
    _pedido()
    with db.sessao() as s:
        ap = s.scalar(select(Aprovacao))
        with pytest.raises(agenda.OperacaoInvalida):  # o mesmo horário do pedido: é só aprovar
            aprovacoes.propor(s, ap, ADMIN, Perfil.RECEPCAO, ap.agendamento.data, ap.agendamento.horario)
        with pytest.raises(agenda.OperacaoInvalida):  # menos de 2 h: não dá tempo de responder
            aprovacoes.propor(s, ap, ADMIN, Perfil.RECEPCAO, date(2026, 11, 5), time(10, 40))
        with pytest.raises(agenda.VagaIndisponivel):  # quarta não tem audiometria
            aprovacoes.propor(s, ap, ADMIN, Perfil.RECEPCAO, date(2026, 11, 11), time(9, 0))
        aprovacoes.propor(s, ap, ADMIN, Perfil.RECEPCAO, date(2026, 11, 12), time(9, 0))
        aprovacoes.cancelar_proposta(s, ap, ADMIN)
        assert ap.status == StatusAprovacao.RECUSADA and ap.agendamento.status == StatusAgendamento.CANCELADO


def test_cancelamento_nao_e_aprovado_depois_que_o_agendamento_mudou():
    with db.sessao() as s:
        ag = _agendamento_painel(s)
        ap = aprovacoes.pedir(s, TipoAprovacao.CANCELAMENTO, ag)
        agenda.cancelar(s, ag, "a equipe já cancelou por telefone")
        with pytest.raises(agenda.OperacaoInvalida):
            aprovacoes.aprovar(s, ap, ADMIN, Perfil.RECEPCAO)
        aprovacoes.recusar(s, ap, ADMIN)  # o motivo é opcional
        assert ap.status == StatusAprovacao.RECUSADA


def test_recusar_libera_vaga_e_passa_para_equipe():
    _pedido()
    with db.sessao() as s:
        ap = s.scalar(select(Aprovacao))
        ag = ap.agendamento
        exames = [i.exame_id for i in ag.itens]
        assert ag.horario not in agenda.livres(s, ag.data, exames)
        aprovacoes.recusar(s, ap, ADMIN, "Médico ausente")
        assert ap.status == StatusAprovacao.RECUSADA
        assert ag.horario in agenda.livres(s, ag.data, exames)
        conv = s.scalar(select(Conversa))
        assert conv.estado == EstadoConversa.AGUARDANDO_HUMANO


def test_aprovar_confere_vaga_de_novo():
    _pedido()
    with db.sessao() as s:
        ap = s.scalar(select(Aprovacao))
        relogio.fixar(datetime(2026, 11, 6, 9, 0))  # o pedido era para ontem
        with pytest.raises(agenda.VagaIndisponivel):
            aprovacoes.aprovar(s, ap, ADMIN, Perfil.RECEPCAO)
    relogio.fixar(datetime(2026, 11, 5, 9, 0))


def _agendamento_painel(s, data=date(2026, 11, 10), h=time(8, 0)):
    pac = Paciente(nome="Ana Ficticia Souza")
    s.add(pac)
    s.flush()
    contato = s.scalar(select(Contato).where(Contato.telefone == TEL_RH))
    audio = s.scalar(select(Exame).where(Exame.codigo == "AUDIO"))
    return agenda.criar(s, paciente_id=pac.id, exame_ids=[audio.id], data=data, horario=h,
                        origem=Origem.PAINEL, contato_id=contato.id)


def test_lembrete_nao_vira_pedido_de_cancelamento(ambiente):
    with db.sessao() as s:
        parametros.garantir_padroes(s)
        s.get(parametros.Parametro, "envios_automaticos").valor = "true"
        ag = _agendamento_painel(s)
        ag_id = ag.id
    relogio.fixar(datetime(2026, 11, 9, 16, 5))
    rodada()
    assert any("lembrete do exame de Ana" in t for _, t in ambiente.enviadas)
    f = Fala(TEL_RH)
    assert "pedi o cancelamento" in f.diz("Não")
    with db.sessao() as s:
        ap = s.scalar(select(Aprovacao))
        assert ap.tipo == TipoAprovacao.CANCELAMENTO
        assert s.get(Agendamento, ag_id).status == StatusAgendamento.AGENDADO  # ainda vale
        aprovacoes.aprovar(s, ap, ADMIN, Perfil.RECEPCAO)
        assert s.get(Agendamento, ag_id).status == StatusAgendamento.CANCELADO
    # e pode remarcar respondendo 1
    assert "mais próximo" in f.diz("1")
    relogio.fixar(datetime(2026, 11, 5, 9, 0))


def test_falta_oferece_remarcacao(ambiente):
    with db.sessao() as s:
        s.get(parametros.Parametro, "envios_automaticos").valor = "true"
        ag = _agendamento_painel(s)
        ag_id = ag.id
    relogio.fixar(datetime(2026, 11, 10, 12, 0))
    with db.sessao() as s:
        agenda.falta(s, s.get(Agendamento, ag_id))
    rodada()
    assert any("não compareceu" in t for _, t in ambiente.enviadas)
    f = Fala(TEL_RH)
    assert "mais próximo" in f.diz("1")
    assert "Recebi o pedido" in f.diz("sim")
    with db.sessao() as s:
        ap = s.scalar(select(Aprovacao))
        assert ap.tipo == TipoAprovacao.REMARCACAO and ap.original_id == ag_id
        novo = aprovacoes.aprovar(s, ap, ADMIN, Perfil.RECEPCAO)
        assert novo.remarcado_de_id == ag_id
    relogio.fixar(datetime(2026, 11, 5, 9, 0))


def test_supervisao_para_mexer_no_que_esta_no_externo():
    with db.sessao() as s:
        ag = _agendamento_painel(s)
        ag.no_sistema_externo = True
        ap = aprovacoes.pedir(s, TipoAprovacao.CANCELAMENTO, ag)
        with pytest.raises(aprovacoes.SemPermissao):
            aprovacoes.aprovar(s, ap, ADMIN, Perfil.RECEPCAO)
        aprovacoes.aprovar(s, ap, ADMIN, Perfil.SUPERVISAO)
        assert ag.status == StatusAgendamento.CANCELADO


def test_envios_automaticos_desligados_nao_saem(ambiente):
    with db.sessao() as s:
        _agendamento_painel(s)
    rodada()
    with db.sessao() as s:
        assert all(n.status == StatusNotificacao.AGENDADA for n in s.scalars(select(Notificacao)))
    assert ambiente.enviadas == []


def test_excecao_lista_afetados():
    from ocupabot.enums import TipoExcecao
    from ocupabot.modelos import Excecao, Profissional

    with db.sessao() as s:
        ag = _agendamento_painel(s)
        fono = s.scalar(select(Profissional).where(Profissional.nome.like("Fono%")))
        ex = Excecao(profissional_id=fono.id, tipo=TipoExcecao.FERIAS, data_inicio=date(2026, 11, 10),
                     data_fim=date(2026, 11, 10))
        s.add(ex)
        s.flush()
        assert [a.id for a in agenda.afetados_por_excecao(s, ex)] == [ag.id]
        assert agenda.livres(s, date(2026, 11, 10), [ag.itens[0].exame_id]) == []
