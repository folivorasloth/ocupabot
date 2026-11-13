"""Reconhecimento de intenções por palavras-chave — previsível e testável, sem IA."""

import re

from ..dominio.texto import normalizar

_SIM = {"sim", "s", "ss", "isso", "pode", "pode sim", "confirmo", "confirma", "ok", "certo", "claro",
        "sim pode", "pode ser", "confirmado", "beleza", "blz", "yes", "positivo", "isso mesmo"}
_NAO = {"nao", "n", "nao pode", "nao quero", "negativo", "nao obrigado", "nao confirmo", "no", "nops"}
_SAIR = {"sair", "parar", "pare", "stop", "cancelar inscricao", "descadastrar", "nao quero mais mensagens"}
_RECOMECAR = {"menu", "recomecar", "inicio", "comecar de novo", "reiniciar"}
_VOLTAR = {"voltar", "volta", "anterior", "corrigir", "errei", "voltar um passo"}
_SAUDACAO = {"oi", "ola", "oie", "oii", "bom dia", "boa tarde", "boa noite", "opa", "eai", "e ai", "alo", "hello"}
_ATENDENTE = re.compile(r"\b(atendente|humano|pessoa|falar com (alguem|a equipe|voces)|recepcao|ajuda humana)\b")
_RESULTADO = re.compile(r"\b(resultado|laudo|diagnostico)s?\b")
_MUDAR = re.compile(r"\b(cancelar|cancela|cancelamento|desmarcar|desmarca|remarcar|remarca|remarcacao|"
                    r"reagendar|reagenda|mudar o horario|trocar o horario)\b")
_PRECO = re.compile(r"\b(preco|precos|valor|valores|quanto custa|quanto fica|quanto e|orcamento|tabela)\b")


def eh_sim(t: str) -> bool:
    n = normalizar(t)
    return n in _SIM or n.startswith("sim ")


def eh_nao(t: str) -> bool:
    n = normalizar(t)
    return n in _NAO or n.startswith("nao ")


def eh_sair(t: str) -> bool:
    return normalizar(t) in _SAIR


def eh_recomecar(t: str) -> bool:
    return normalizar(t) in _RECOMECAR


def eh_voltar(t: str) -> bool:
    return normalizar(t) in _VOLTAR


def eh_saudacao(t: str) -> bool:
    return normalizar(t) in _SAUDACAO


def quer_atendente(t: str) -> bool:
    return bool(_ATENDENTE.search(normalizar(t)))


def pede_resultado(t: str) -> bool:
    return bool(_RESULTADO.search(normalizar(t)))


def quer_mudar_agendamento(t: str) -> bool:
    """Cancelar ou remarcar em texto livre: o bot não adivinha qual agendamento; vai para a equipe."""
    return bool(_MUDAR.search(normalizar(t)))


def pergunta_preco(t: str) -> bool:
    return bool(_PRECO.search(normalizar(t)))


def opcao(t: str, maximo: int) -> int | None:
    n = normalizar(t)
    if n.isascii() and n.isdigit() and 0 <= int(n) <= maximo:
        return int(n)
    return None


def lista_numeros(t: str, maximo: int) -> list[int] | None:
    partes = [p for p in re.split(r"[,\s;e]+", normalizar(t)) if p]
    if not partes or not all(p.isascii() and p.isdigit() for p in partes):
        return None
    nums = sorted({int(p) for p in partes})
    if any(n < 1 or n > maximo for n in nums):
        return None
    return nums
