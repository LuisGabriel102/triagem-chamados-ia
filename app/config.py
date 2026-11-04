"""Configuração lida das variáveis de ambiente ou do arquivo .env."""

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Configuracao(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Sem chave da Anthropic, o serviço funciona só com o plano B por regras.
    anthropic_api_key: SecretStr | None = None
    modelo_llm: str = "claude-haiku-5-5"
    database_url: str = "sqlite:///./triagem.db"
    # Chave que quem chama a API envia no cabeçalho X-API-Key. Vazia = API aberta (só local).
    chave_api_app: SecretStr | None = None
    # Abaixo deste valor de confiança, o chamado vai para revisão humana.
    limite_confianca: float = Field(default=0.75, ge=0, le=1)
    # Preço do modelo em dólar por milhão de tokens. Confira na página de preços da Anthropic.
    preco_entrada_usd_mtok: float = Field(default=0.10, ge=0)
    preco_saida_usd_mtok: float = Field(default=0.50, ge=0)
    timeout_llm_s: float = Field(default=20.0, gt=0)
