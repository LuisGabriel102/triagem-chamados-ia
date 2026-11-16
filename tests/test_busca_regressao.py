"""Trava de regressão da busca: roda a cada envio, no CI, sem chave e sem gastar nada.

A busca por palavras roda direto. A busca por sentido usa os vetores dos artigos
(base/indice.json) e os das perguntas (avaliacao/vetores_perguntas_busca.json), guardados uma
vez. O teste falha se qualquer mudança (no mascaramento, nos artigos, nos limiares, no código
da busca) fizer a busca piorar em relação à última avaliação (avaliacao/resultados/busca.md).

Os números mínimos são os da avaliação de 13/11/2026. Se a busca melhorar de propósito, suba o
mínimo aqui junto com o relatório novo.
"""

import pytest

from app.base_conhecimento import carregar_artigos
from app.busca import Busca, escolher_limiares
from app.busca_sentido import ARQUIVO_INDICE, carregar_indice_memoria
from app.config import Configuracao
from avaliacao.avaliar_busca import ARQUIVO_PERGUNTAS, avaliar_modo, carregar_perguntas, resumir
from avaliacao.vetores_guardados import ARQUIVO_VETORES, GeradorDeArquivo

# Mínimos de 13/11/2026 (avaliacao/resultados/busca.md), em 40 perguntas com resposta e 8 sem.
MINIMOS = {
    "palavras": {"respondidas_certas": 23, "acerto_3": 32, "sem_resposta_em_nada_encontrado": 7},
    "sentido": {"respondidas_certas": 37, "acerto_3": 40, "sem_resposta_em_nada_encontrado": 8},
}


@pytest.fixture(scope="module")
def busca():
    artigos = carregar_artigos()
    gerador = GeradorDeArquivo(ARQUIVO_VETORES)
    config = Configuracao(_env_file=None, limiar_bm25=None, limiar_similaridade=None)
    limiares = escolher_limiares(config, gerador.modelo, gerador.dimensoes)
    indice = carregar_indice_memoria(artigos, gerador.modelo, gerador.dimensoes, ARQUIVO_INDICE)
    return Busca(
        artigos,
        gerador,
        indice,
        limiar_bm25=limiares.bm25,
        limiar_similaridade=limiares.similaridade,
    )


@pytest.mark.parametrize("modo", ["palavras", "sentido"])
def test_a_busca_nao_piorou(busca, modo):
    resumo = resumir(avaliar_modo(busca, carregar_perguntas(ARQUIVO_PERGUNTAS), modo), modo)
    # Nenhuma pergunta pode ter caído para a busca por palavras por falta de vetor.
    assert resumo["quedas_para_palavras"] == 0
    for medida, minimo in MINIMOS[modo].items():
        assert resumo[medida] >= minimo, f"{modo}: {medida} caiu para {resumo[medida]}"
    # E nenhum dado pessoal de teste sobra no texto que iria ao Google.
    assert resumo["dados_no_texto_mascarado"] == 0
