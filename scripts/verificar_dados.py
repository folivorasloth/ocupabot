#!/usr/bin/env python3
"""Barra o commit se houver dado sensível no repositório.

Procura, nos arquivos versionados: .env, bancos SQLite, e CPFs/CNPJs com dígito verificador
válido que não estejam na lista de fictícios permitidos (scripts/fictícios_permitidos.txt).

    python scripts/verificar_dados.py          # arquivos no git
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PROIBIDOS = re.compile(r"(^|/)\.env$|\.(db|sqlite3?)$|(^|/)(data|dados_reais)/")
NUMERO = re.compile(r"(?<![\d\w])(\d{3}\.?\d{3}\.?\d{3}-?\d{2}|\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2})(?![\d\w])")
IGNORAR = {"package-lock.json"}


def _dv(d: str, pesos: list[int]) -> int:
    r = sum(int(a) * b for a, b in zip(d, pesos, strict=False)) % 11
    return 0 if r < 2 else 11 - r


def documento_valido(n: str) -> bool:
    d = re.sub(r"\D", "", n)
    if len(set(d)) == 1:
        return False
    if len(d) == 11:
        return d[9:] == f"{_dv(d[:9], list(range(10, 1, -1)))}{_dv(d[:10], list(range(11, 1, -1)))}"
    if len(d) == 14:
        p1 = _dv(d[:12], [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2])
        p2 = _dv(d[:13], [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2])
        return d[12:] == f"{p1}{p2}"
    return False


def main() -> int:
    permitidos_arq = RAIZ / "scripts" / "ficticios_permitidos.txt"
    permitidos = {re.sub(r"\D", "", x) for x in permitidos_arq.read_text().split() if x.strip()} \
        if permitidos_arq.exists() else set()
    arquivos = subprocess.run(["git", "ls-files"], cwd=RAIZ, capture_output=True, text=True, check=True).stdout.split()
    problemas = []
    for nome in arquivos:
        if PROIBIDOS.search(nome):
            problemas.append(f"{nome}: arquivo que não deve ser versionado")
            continue
        if Path(nome).name in IGNORAR:
            continue
        try:
            texto = (RAIZ / nome).read_text(encoding="utf-8")
        except (UnicodeDecodeError, FileNotFoundError):
            continue
        for m in NUMERO.finditer(texto):
            if documento_valido(m.group(1)) and re.sub(r"\D", "", m.group(1)) not in permitidos:
                linha = texto.count("\n", 0, m.start()) + 1
                problemas.append(f"{nome}:{linha}: possível CPF/CNPJ real ({m.group(1)[:3]}...)")
    for p in problemas:
        print(p)
    if problemas:
        print("\nSe for fictício, adicione o número em scripts/ficticios_permitidos.txt.")
        return 1
    print("ok: nenhum dado sensível encontrado")
    return 0


if __name__ == "__main__":
    sys.exit(main())
