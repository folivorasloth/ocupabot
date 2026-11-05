from ocupabot import db
from ocupabot.bot.maquina import processar

TEL_RH = "5511900000001"  # RH da Alfa (seed)
TEL_NOVO = "5511900000009"


class Conversa:
    """Conversa de teste: cada fala roda numa transação própria, como no webhook."""

    def __init__(self, telefone: str = TEL_NOVO) -> None:
        self.tel = telefone
        self.n = 0

    def diz(self, texto: str) -> str:
        self.n += 1
        with db.sessao() as s:
            respostas = processar(s, self.tel, texto, id_externo=f"{self.tel}-{self.n}")
        return "\n".join(respostas)
