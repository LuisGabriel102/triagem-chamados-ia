"""Configuração lida das variáveis de ambiente ou do arquivo .env."""

from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Configuracao(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Qual IA classifica: o Claude, da Anthropic (padrão), ou o Gemini, do Google, no Vertex AI.
    provedor_ia: Literal["anthropic", "gemini"] = "anthropic"

    # Claude. Sem a chave, o serviço funciona só com o plano B por regras.
    anthropic_api_key: SecretStr | None = None
    modelo_llm: str = "claude-haiku-5-5"
    # Preço do Claude em dólar por milhão de tokens. Confira na página de preços da Anthropic.
    preco_entrada_usd_mtok: float = Field(default=0.10, ge=0)
    preco_saida_usd_mtok: float = Field(default=0.50, ge=0)

    # Gemini no Vertex AI. Não usa chave: vale o login do Google Cloud no computador
    # (gcloud auth application-default login). O preço vem da tabela em app/precos.py.
    google_cloud_project: str = ""
    google_cloud_location: str = "global"
    modelo_gemini: str = "gemini-3.5-flash-lite"
    # Quanto o Gemini pensa antes de responder. Classificar texto curto pede pouco.
    # "padrao" deixa o modelo decidir (use se algum modelo recusar o nível).
    raciocinio_gemini: Literal["padrao", "low", "medium", "high"] = "low"

    # Busca na base de conhecimento do atendimento (docs/ATENDIMENTO.md).
    # Embeddings do Gemini pela chave do Google AI Studio. Sem ela, vale o Vertex AI
    # (GOOGLE_CLOUD_PROJECT). Sem nenhum dos dois, a busca roda só por palavras.
    gemini_api_key: SecretStr | None = None
    modelo_embedding: str = "gemini-embedding-2"
    dimensoes_embedding: int = Field(default=768, ge=128, le=3072)
    # Abaixo do limiar, a busca devolve "nada encontrado" e o agente chama uma pessoa.
    # Com a busca por sentido, vale o da similaridade; sem ela, o do BM25. Os dois saem
    # das perguntas de calibração (python -m avaliacao.avaliar_busca --calibrar).
    limiar_bm25: float = Field(default=0.0, ge=0)
    # Vazio até ser calibrado com a busca por sentido rodando (precisa do acesso ao Google).
    limiar_similaridade: float | None = Field(default=None, ge=-1, le=1)

    database_url: str = "sqlite:///./triagem.db"
    # Chave que quem chama a API envia no cabeçalho X-API-Key. Vazia = API aberta (só local).
    chave_api_app: SecretStr | None = None
    # Abaixo deste valor de confiança, o chamado vai para revisão humana.
    limite_confianca: float = Field(default=0.75, ge=0, le=1)
    timeout_llm_s: float = Field(default=20.0, gt=0)
    # Página de demonstração aberta ao público: não grava nada e tem limite de uso.
    demo_ativa: bool = True
    demo_limite_por_hora: int = Field(default=10, ge=1)  # por pessoa (endereço IP)
    demo_limite_por_dia: int = Field(default=200, ge=1)  # somando todo mundo
    # Endereço público da página (ex.: https://triagem.up.railway.app). Serve para a
    # prévia do link no LinkedIn. Vazio = sem prévia.
    url_publica: str = ""

    @field_validator("limiar_similaridade", mode="before")
    @classmethod
    def _vazio_e_sem_limiar(cls, valor: object) -> object:
        """LIMIAR_SIMILARIDADE= (vazio) no .env quer dizer "ainda não calibrado"."""
        return None if isinstance(valor, str) and not valor.strip() else valor
