"""Validação de CPF e CNPJ (dígitos verificadores) e máscaras para exibição."""

import re
import unicodedata


def so_digitos(texto: str) -> str:
    """Só os dígitos, sempre em ASCII (dígito de largura cheia ou de outro alfabeto vira 0-9)."""
    return "".join(str(unicodedata.digit(c)) for c in texto or "" if c.isdigit())


def _dv(digitos: str, pesos: list[int]) -> int:
    resto = sum(int(d) * p for d, p in zip(digitos, pesos, strict=False)) % 11
    return 0 if resto < 2 else 11 - resto


def cpf_problema(cpf: str) -> str | None:
    """None se o CPF é válido; senão, uma explicação curta para a pessoa."""
    d = so_digitos(cpf)
    if len(d) != 11:
        return f"o CPF tem 11 números e recebi {len(d)}."
    if d == d[0] * 11:
        return "todos os números são iguais."
    p1 = _dv(d[:9], list(range(10, 1, -1)))
    p2 = _dv(d[:10], list(range(11, 1, -1)))
    if d[9:] != f"{p1}{p2}":
        return "os 2 últimos números não conferem com os 9 primeiros; talvez algum tenha sido trocado."
    return None


def cpf_valido(cpf: str) -> bool:
    return cpf_problema(cpf) is None


def cnpj_valido(cnpj: str) -> bool:
    d = so_digitos(cnpj)
    if len(d) != 14 or d == d[0] * 14:
        return False
    p1 = _dv(d[:12], [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2])
    p2 = _dv(d[:13], [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2])
    return d[12:] == f"{p1}{p2}"


def mascarar_cpf(cpf: str | None) -> str:
    d = so_digitos(cpf or "")
    return f"***.{d[3:6]}.***-**" if len(d) == 11 else ""


def formatar_cnpj(cnpj: str | None) -> str:
    d = so_digitos(cnpj or "")
    if len(d) != 14:
        return cnpj or ""
    return f"{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:]}"


_SEP = r"[-./\s_]{0,3}"  # a pessoa separa o CPF de qualquer jeito: 123 456 789 09, 123/456/789-09...
_CPF_NO_TEXTO = re.compile(rf"(?<!\d)(\d{{3}}{_SEP}\d{{3}}{_SEP}\d{{3}}{_SEP}\d{{2}})(?!\d)")
_RG_NO_TEXTO = re.compile(r"(?<![\d/])(\d{1,2}[.\s]?\d{3}[.\s]?\d{3}[-.\s]?[\dxX])(?![\d/])")


def _ascii(texto: str) -> str:
    return "".join(str(unicodedata.digit(c)) if c.isdigit() and not c.isascii() else c for c in texto or "")


def redigir(texto: str) -> str:
    """Troca CPFs e RGs por marcadores antes de gravar a mensagem."""
    texto = _CPF_NO_TEXTO.sub(lambda m: "[CPF]" if cpf_valido(m.group(1)) else m.group(1), _ascii(texto))
    return _RG_NO_TEXTO.sub("[RG]", texto)


def tem_documento(texto: str | None) -> bool:
    """O texto livre traz CPF ou RG? (observação, motivo e resposta da equipe recusam na entrada)"""
    return bool(texto) and redigir(texto) != _ascii(texto)
