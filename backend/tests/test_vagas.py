from datetime import date, datetime, time

from ocupabot.dominio.vagas import Indisponibilidade, Ocupacao, Retrato, agrupar_faixas

SEG = date(2026, 11, 9)  # segunda
TER = date(2026, 11, 10)
CLINICO, AUDIO = 1, 2
ANA, BETO = 10, 20


def retrato(**kw) -> Retrato:
    base = dict(
        expediente={(0, "MANHA"): (time(7, 30), time(8, 30)), (1, "MANHA"): (time(7, 30), time(8, 30))},
        # Ana faz clínico e audiometria; Beto só clínico
        grade={
            (0, "MANHA", CLINICO): {ANA, BETO},
            (0, "MANHA", AUDIO): {ANA},
            (1, "MANHA", CLINICO): {BETO},
        },
        capacidade={CLINICO: 6, AUDIO: 6},
    )
    base.update(kw)
    return Retrato(**base)


def test_horarios_respeitam_expediente():
    r = retrato()
    assert [t for t, _ in r.horarios_do_dia(SEG)] == [time(7, 30), time(7, 40), time(7, 50),
                                                       time(8, 0), time(8, 10), time(8, 20)]
    assert r.horarios_do_dia(date(2026, 11, 11)) == []  # quarta sem expediente


def test_varias_funcoes_exigem_pessoas_diferentes():
    r = retrato()
    # clínico + audiometria: Ana precisa ficar na audiometria e Beto no clínico
    assert r.atribuir(SEG, time(7, 30), [CLINICO, AUDIO]) == {CLINICO: BETO, AUDIO: ANA}
    # terça não tem audiometria
    assert r.atribuir(TER, time(7, 30), [CLINICO, AUDIO]) is None


def test_profissional_e_recurso_unico_entre_funcoes():
    # Ana ocupada no clínico às 7:30 => não pode fazer audiometria às 7:30
    r = retrato(ocupacoes=[Ocupacao(SEG, time(7, 30), CLINICO, ANA)])
    assert r.atribuir(SEG, time(7, 30), [AUDIO]) is None
    assert r.atribuir(SEG, time(7, 30), [CLINICO]) == {CLINICO: BETO}
    assert r.atribuir(SEG, time(7, 40), [AUDIO]) == {AUDIO: ANA}


def test_ocupacao_sem_profissional_consome_alguem_da_funcao():
    r = retrato(ocupacoes=[Ocupacao(SEG, time(7, 30), CLINICO, None)])
    # ainda cabe 1 clínico (Ana ou Beto) além do antigo, mas não clínico + audiometria
    assert r.atribuir(SEG, time(7, 30), [CLINICO]) is not None
    assert r.atribuir(SEG, time(7, 30), [CLINICO, AUDIO]) is None


def test_capacidade_por_hora():
    ocup = [Ocupacao(SEG, time(7, 30), AUDIO, ANA), Ocupacao(SEG, time(7, 40), AUDIO, ANA)]
    r = retrato(capacidade={CLINICO: 6, AUDIO: 2}, ocupacoes=ocup)
    assert r.atribuir(SEG, time(7, 50), [AUDIO]) is None  # 2 por hora já usados às 7h
    assert r.atribuir(SEG, time(8, 0), [AUDIO]) == {AUDIO: ANA}  # nova hora


def test_excecoes():
    ferias = Indisponibilidade(ANA, SEG, SEG, None)
    r = retrato(excecoes=[ferias])
    assert r.atribuir(SEG, time(7, 30), [AUDIO]) is None
    assert r.atribuir(SEG, time(7, 30), [CLINICO]) == {CLINICO: BETO}
    feriado = Indisponibilidade(None, TER, TER, None)
    assert retrato(excecoes=[feriado]).livres_no_dia(TER, [CLINICO]) == []


def test_bloqueio_externo_e_nao_antes():
    r = retrato(bloqueios={(SEG, time(7, 30))})
    assert r.atribuir(SEG, time(7, 30), [CLINICO]) is None
    assert r.atribuir(SEG, time(7, 30), [CLINICO], bloquear_externos=False) is not None
    livres = r.livres_no_dia(SEG, [CLINICO], nao_antes=datetime(2026, 11, 9, 8, 0))
    assert livres == [time(8, 10), time(8, 20)]


def test_agrupar_faixas():
    hs = [time(7, 30), time(7, 40), time(7, 50), time(9, 0)]
    assert agrupar_faixas(hs, 10) == [(time(7, 30), time(7, 50)), (time(9, 0), time(9, 0))]
