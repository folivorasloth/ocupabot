"""Normalização de texto livre vindo do WhatsApp."""

import re
import unicodedata


def normalizar(texto: str) -> str:
    """minúsculas, sem acento, sem pontuação e com espaços simples."""
    t = unicodedata.normalize("NFKD", texto or "")
    t = "".join(c for c in t if not unicodedata.combining(c)).lower()
    t = re.sub(r"[^a-z0-9/:,\s]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def primeiro_nome(nome: str) -> str:
    return (nome or "").strip().split(" ")[0].title() if nome else ""


def normalizar_telefone(telefone: str) -> str:
    """Só dígitos, com DDI 55 quando vier no formato nacional."""
    d = re.sub(r"\D", "", telefone or "")
    if len(d) in (10, 11):
        d = "55" + d
    return d
