"""Ficha do paciente mandada numa mensagem só.

Muitas empresas mandam tudo de uma vez, com ou sem rótulos:

    Nome: Ana Souza / CPF: 529.982.247-25 / Nascimento: 14/05/1990 / Função: Auxiliar
    Ana Souza 52998224725 14/05/1990 auxiliar de produção

O bot lê o que veio e pergunta só o que faltou. Mensagem com dois CPFs são dois pacientes: não é lida
como ficha, para um não ser gravado com o documento do outro.
"""

from __future__ import annotations

import re
from datetime import date

from .datas import ler_nascimento
from .documentos import _CPF_NO_TEXTO, cpf_valido, so_digitos
from .texto import normalizar

_DATA = re.compile(r"(?<!\d)\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4}(?!\d)")
_ROTULOS = {
    "nome": r"nome(?: completo)?(?: d[oa] (?:paciente|funcionari[oa]|candidat[oa]|colaborador[a]?))?|paciente|"
            r"funcionari[oa]|candidat[oa]|colaborador[a]?",
    "cpf": r"cpf",
    "nascimento": r"(?:data de )?nasc(?:imento)?\.?|dn",
    "cargo": r"funcao|cargo|funcao ?/ ?cargo",
}
_ROTULO = re.compile(r"^\s*(" + "|".join(f"(?P<{k}>{v})" for k, v in _ROTULOS.items()) + r")\s*[:\-=]\s*(?P<valor>.+)$",
                     re.IGNORECASE)
_OUTRO_ROTULO = re.compile(r"^\s*[\w /]{2,25}:\s*\S")  # "Assunto: ...", "Nome da mãe: ...": não é da ficha
_SO_ROTULO = re.compile(r"(?i)\b(cpf|rg|dn|data de nasc\w*|nasc\w*)\b[:.]*")
_SEM_CARGO = {"sem funcao", "sem cargo", "nao tem", "nao sei", "nao informado"}
_TRATAMENTO = re.compile(r"^(sr|sra|senhor|senhora|dona|seu)\.? ", re.IGNORECASE)


def _nome(texto: str) -> str | None:
    nome = _TRATAMENTO.sub("", " ".join(texto.split()).strip(" ,;.-"))
    palavras = nome.split()
    if not 2 <= len(palavras) <= 8 or len(nome) > 160 or any(c.isdigit() for c in nome) or "?" in nome:
        return None
    return nome.title()


def _cargo(texto: str) -> str | None:
    cargo = " ".join(texto.split()).strip(" ,;.-")
    if not 2 <= len(cargo) <= 120 or "?" in cargo or normalizar(cargo) in _SEM_CARGO:
        return None
    return cargo


_SEPARA = re.compile(r"\n|\||;| / | - ")  # entre os campos de uma ficha com rótulos (a barra da data não separa)


def _letra(c: str) -> str:
    n = normalizar(c) if c.isalpha() else c
    return n if len(n) == 1 else c


def _sem_acento(linha: str) -> str:
    """Só para achar o rótulo ("Função:" = "Funcao:"); o valor é lido da linha original, na mesma posição."""
    return "".join(_letra(c) for c in linha)


def ler(texto: str, hoje: date) -> dict[str, str]:
    """Os campos achados: nome, cpf (só dígitos), nascimento (ISO) e cargo. Vazio se não parece uma ficha."""
    cpfs = {so_digitos(m.group(1)) for m in _CPF_NO_TEXTO.finditer(texto) if cpf_valido(m.group(1))}
    if len(cpfs) > 1:
        return {}
    achado: dict[str, str] = {}
    soltas: list[str] = []
    for linha in _SEPARA.split(texto.replace("\r", "")) if _tem_rotulo(texto) else [texto]:
        m = _ROTULO.match(_sem_acento(linha))
        if m is None:
            if not _OUTRO_ROTULO.match(linha):
                soltas.append(linha)
            continue
        campo = next(k for k in _ROTULOS if m.group(k))
        valor = linha[m.start("valor"):]
        if campo == "nome" and _nome(valor):
            achado["nome"] = _nome(valor)
        elif campo == "cargo" and _cargo(valor):
            achado["cargo"] = _cargo(valor)
        else:
            soltas.append(valor)  # CPF e nascimento são achados pelo formato, com ou sem rótulo
    resto = " \n ".join(soltas)
    if cpfs:
        achado["cpf"] = cpfs.pop()
        resto = _CPF_NO_TEXTO.sub(lambda m: " \n " if cpf_valido(m.group(1)) else m.group(0), resto)
    data = _DATA.search(resto)
    nasc = ler_nascimento(data.group(0), hoje) if data else None
    if nasc is not None:
        achado["nascimento"] = nasc.isoformat()
        resto = resto.replace(data.group(0), " \n ", 1)
    if not {"cpf", "nascimento"} & set(achado):
        return achado if len(achado) >= 2 else {}  # "Nome: ... / Função: ..." vale; texto solto não
    # sem rótulo: o CPF e a data separam os pedaços; o primeiro é o nome e o texto curto depois é a função
    resto = _SO_ROTULO.sub(" ", resto)  # "CPF 529..." sem dois-pontos: a palavra que sobrou não é nome nem função
    pedacos = [p for p in (x.strip(" ,;.-:") for x in re.split(r"[\n,]", resto)) if p]
    for p in pedacos:
        if "nome" not in achado and _nome(p):
            achado["nome"] = _nome(p)
        elif "nome" in achado and "cargo" not in achado and _cargo(p) and p.title() != achado["nome"]:
            achado["cargo"] = _cargo(p)
    return achado


def _tem_rotulo(texto: str) -> bool:
    return any(_ROTULO.match(_sem_acento(parte)) for parte in _SEPARA.split(texto))
