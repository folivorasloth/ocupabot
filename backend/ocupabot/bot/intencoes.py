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
_CORTESIA = {"obrigado", "obrigada", "obg", "brigado", "brigada", "valeu", "vlw", "kkk", "kkkk", "rs", "rsrs",
             "muito obrigado", "muito obrigada", "agradeco", "legal", "show", "perfeito", "otimo"}
# Resposta ao lembrete com frase de quem não vai ("não vou poder ir", "não vai dar", "vou faltar"). Só no
# lembrete, onde a pergunta é "confirma a presença?". "Não vou faltar" é o contrário.
_AUSENCIA = re.compile(
    r"\bnao (?:vou|vai|vamos|posso|poderei|podemos|consigo|consegue|conseguimos|irei|tem como)"
    r"(?: (?:mais|mesmo))?(?: (?:poder|conseguir))? (?:ir|comparecer|estar ai|estar la)\b"
    r"|\bnao (?:vai|va) (?:dar|rolar)\b|\bnao irei\b|\bnao comparecerei\b|\b(?:vou|vai|vamos) faltar\b")
_NAO_FALTA = re.compile(r"\bnao (?:vou|vai|vamos) faltar\b")
_RESSALVA = {"mas", "porem", "talvez", "depende", "sei", "entendi", "entendo", "se"}
_PARA_MIM = re.compile(r"\b(pra mim|para mim|particular|pessoa fisica|eu mesm[oa]|sou eu)\b")
_NAO_SEI = re.compile(r"\bnao (sei|tenho|lembro|conheco)\b")
# "recepção" sozinha não chama a equipe: aparece em pergunta comum ("a recepção abre que horas?")
_ATENDENTE = re.compile(r"\b(atendente|humano|falar com (uma pessoa|alguem|a equipe|voces|a recepcao)|ajuda humana)\b")
_RESULTADO = re.compile(r"\b(resultado|laudo|diagnostico)s?\b")
_MUDAR = re.compile(r"\b(cancelar|cancela|cancelamento|desmarcar|desmarca|remarcar|remarca|remarcacao|"
                    r"reagendar|reagenda|mudar o horario|trocar o horario)\b")
_PRECO = re.compile(r"\b(preco|precos|valor|valores|quanto custa|quanto fica|quanto e|orcamento|tabela)\b")


def eh_sim(t: str) -> bool:
    """Pergunta não é SIM: "pode ser à tarde?" pede outro horário, não confirma."""
    n = normalizar(t)
    return "?" not in t and (n in _SIM or n.startswith("sim "))


def eh_nao(t: str) -> bool:
    n = normalizar(t)
    return n in _NAO or n.startswith("nao ")


def eh_nao_ao_lembrete(t: str) -> bool:
    """O NÃO de sempre, ou uma frase de ausência sem pergunta nem ressalva. "Não vou faltar" não é."""
    n = normalizar(t)
    if _NAO_FALTA.search(n) or "?" in t or set(n.split()) & _RESSALVA:
        return False  # "não sei se vou poder ir", "não vou, mas mando outro": continua pedindo SIM ou NÃO
    return n in _NAO or bool(_AUSENCIA.search(n)) or (n.startswith("nao ") and len(n.split()) <= 3)


def eh_cortesia(t: str) -> bool:
    """Obrigado, kkk, um emoji: não é resposta, mas também não é erro."""
    n = normalizar(t)
    return n in _CORTESIA or (not n and bool(t.strip()))


def eh_para_mim(t: str) -> bool:
    return bool(_PARA_MIM.search(normalizar(t)))


def nao_sabe(t: str) -> bool:
    return bool(_NAO_SEI.search(normalizar(t)))


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
