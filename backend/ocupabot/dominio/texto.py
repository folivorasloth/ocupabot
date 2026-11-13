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
    """Só dígitos (ASCII), com DDI 55 quando vier no formato nacional."""
    d = "".join(str(unicodedata.digit(c)) for c in telefone or "" if c.isdigit())
    if len(d) in (10, 11):
        d = "55" + d
    return d


def variantes(telefone: str) -> list[str]:
    """O mesmo celular brasileiro com e sem o nono dígito: no WhatsApp é a mesma linha."""
    d = normalizar_telefone(telefone)
    if d.startswith("55") and len(d) == 13 and d[4] == "9":
        return [d, d[:4] + d[5:]]
    if d.startswith("55") and len(d) == 12 and d[4] in "6789":
        return [d, d[:4] + "9" + d[4:]]
    return [d]
