"""Configuração lida do ambiente (prefixo OCUPABOT_) ou do arquivo .env."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

# Valores que estão no repositório (padrão do código e .env.example): não servem fora do desenvolvimento
SEGREDOS_PUBLICOS = {"dev-inseguro-troque", "troque-este-valor"}


class Config(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="OCUPABOT_", env_file=".env", extra="ignore")

    segredo: str = "dev-inseguro-troque"
    banco_url: str = "sqlite:///./data/ocupabot.db"
    nome_clinica: str = "Clínica Exemplo"
    cookie_seguro: bool = False
    docs_ativo: bool = False
    painel_dir: str = "../frontend/dist"

    canal: str = "console"
    waha_url: str = "http://waha:3000"
    waha_sessao: str = "default"
    waha_api_key: str = ""
    webhook_token: str = ""

    bot_ativo: bool = False
    modo_teste: bool = True
    numeros_teste: str = ""
    simulador_ativo: bool = False

    agenda_externa: str = "nenhum"

    @property
    def lista_numeros_teste(self) -> set[str]:
        return {n.strip() for n in self.numeros_teste.split(",") if n.strip()}


@lru_cache
def config() -> Config:
    return Config()
