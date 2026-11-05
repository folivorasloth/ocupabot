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


def test_aprovar_com_alteracao(ambiente):
    _pedido()
    with db.sessao() as s:
        ap = s.scalar(select(Aprovacao))
        novo = aprovacoes.aprovar(s, ap, ADMIN, Perfil.RECEPCAO, nova_data=date(2026, 11, 12),
                                  novo_horario=time(9, 0))
        assert novo.data == date(2026, 11, 12) and ap.alterada
        assert ap.agendamento.status == StatusAgendamento.CANCELADO
        assert s.scalar(select(Notificacao).where(Notificacao.tipo == TipoNotificacao.LEMBRETE_D1))


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
