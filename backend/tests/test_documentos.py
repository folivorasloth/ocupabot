from datetime import date, time

from ocupabot.dominio.datas import ler_data, ler_hora, ler_nascimento
from ocupabot.dominio.documentos import cnpj_valido, cpf_problema, cpf_valido, mascarar_cpf, redigir


def test_cpf():
    assert cpf_valido("529.982.247-25")
    assert not cpf_valido("529.982.247-24")
    assert "iguais" in cpf_problema("111.111.111-11")
    assert "11 números" in cpf_problema("123")
    assert mascarar_cpf("52998224725") == "***.982.***-**"


def test_cnpj():
    assert cnpj_valido("11.222.333/0001-81")
    assert not cnpj_valido("12.345.678/0001-00")


def test_redigir():
    t = redigir("cpf 529.982.247-25 rg 12.345.678-9 tel 11987654321")
    assert "[CPF]" in t and "[RG]" in t and "529" not in t and "11987654321" in t


def test_datas():
    hoje = date(2026, 11, 5)
    assert ler_data("12/11", hoje) == date(2026, 11, 12)
    assert ler_data("02/01", hoje) == date(2027, 1, 2)
    assert ler_data("31/02", hoje) is None
    assert ler_nascimento("10/02/1995", hoje) == date(1995, 2, 10)
    assert ler_nascimento("10/02/2030", hoje) is None
    assert ler_hora("12/11 07:30") == time(7, 30)
    assert ler_hora("às 13h") == time(13, 0)
    assert ler_hora("12/11") is None
