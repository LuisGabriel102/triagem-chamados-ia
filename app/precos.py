"""Preço de cada modelo, para calcular o custo de cada triagem.

Os preços são em dólar por milhão de tokens.
"""

from dataclasses import dataclass
from datetime import date

from app.config import Configuracao

# Claude: ler do cache custa 10% do preço de entrada; gravar nele (validade de 5 minutos)
# custa 25% a mais que a entrada normal.
CACHE_LEITURA_CLAUDE = 0.10
CACHE_ESCRITA_CLAUDE = 1.25

# Gemini no Vertex AI, endpoint global. Fonte: página de preços do Vertex AI, conferida em
# 11/11/2026 (https://cloud.google.com/vertex-ai/generative-ai/pricing).
# Cada modelo tem uma lista de períodos: (último dia do preço, entrada, saída).
# O primeiro período ainda válido vale; None = sem data para acabar.
# No Gemini, os tokens de raciocínio são cobrados como saída.
PRECOS_GEMINI: dict[str, list[tuple[date | None, float, float]]] = {
    "gemini-3.5-flash-lite": [(None, 0.30, 2.50)],
    "gemini-3.5-flash": [(None, 1.50, 9.00)],
    # Preço de lançamento até 31/12/2026. Depois, o preço cheio.
    "gemini-3.8-flash": [(date(2026, 12, 31), 0.75, 3.75), (None, 1.50, 7.50)],
}
# O cache do Gemini é automático: não cobra para gravar, e ler custa 10% da entrada.
CACHE_LEITURA_GEMINI = 0.10
# Fora do endpoint global, o Vertex AI cobra 10% a mais.
ACRESCIMO_FORA_DO_GLOBAL = 1.10


@dataclass(frozen=True)
class Precos:
    entrada: float
    saida: float
    # Frações do preço de entrada cobradas pelos tokens lidos do cache e gravados nele.
    cache_leitura: float
    cache_escrita: float
    # False quando o modelo não está na tabela: aí o custo calculado não vale.
    conhecido: bool = True


def preco_gemini(modelo: str, local: str = "global", hoje: date | None = None) -> Precos:
    periodos = PRECOS_GEMINI.get(modelo)
    if not periodos:
        return Precos(0.0, 0.0, CACHE_LEITURA_GEMINI, 0.0, conhecido=False)
    dia = hoje or date.today()
    entrada, saida = next((e, s) for ate, e, s in periodos if ate is None or dia <= ate)
    fator = 1.0 if local == "global" else ACRESCIMO_FORA_DO_GLOBAL
    return Precos(
        entrada=round(entrada * fator, 6),
        saida=round(saida * fator, 6),
        cache_leitura=CACHE_LEITURA_GEMINI,
        cache_escrita=0.0,
    )


def precos_do_provedor(config: Configuracao, hoje: date | None = None) -> Precos:
    """O preço do modelo que a configuração escolheu."""
    if config.provedor_ia == "gemini":
        return preco_gemini(config.modelo_gemini, config.google_cloud_location, hoje)
    return Precos(
        entrada=config.preco_entrada_usd_mtok,
        saida=config.preco_saida_usd_mtok,
        cache_leitura=CACHE_LEITURA_CLAUDE,
        cache_escrita=CACHE_ESCRITA_CLAUDE,
    )
