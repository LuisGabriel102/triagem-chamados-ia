"""Fumaça do atendimento com IA de verdade: 10 perguntas da avaliação da busca, de ponta a ponta.

Isto NÃO é a avaliação da etapa 3. Serve só para ver o agente funcionando com o Claude e o
Google de verdade: o que respondeu, a fonte, se chamou uma pessoa, o custo e o tempo.

As 10 perguntas e o lojista de cada uma foram escolhidos antes de rodar (lista abaixo).
Precisa da ANTHROPIC_API_KEY no .env. Cada pergunta faz de 2 a 5 chamadas à IA.

    python scripts/fumaca_atendimento.py
"""

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from app.atendimento import criar_atendimento  # noqa: E402
from app.config import Configuracao  # noqa: E402
from app.esquemas import Canal  # noqa: E402

ARQUIVO_PERGUNTAS = RAIZ / "avaliacao" / "perguntas_busca.jsonl"
SAIDA = RAIZ / "avaliacao" / "resultados" / "fumaca_atendimento"
# (id da pergunta, lojista da sessão). Escolhidos antes de rodar; b44 não tem resposta na base.
ROTEIRO = [
    ("b01", "loja-001"),
    ("b03", "loja-003"),
    ("b10", "loja-001"),
    ("b14", "loja-002"),
    ("b19", "loja-001"),
    ("b23", "loja-003"),
    ("b27", "loja-001"),
    ("b33", "loja-001"),
    ("b38", "loja-001"),
    ("b44", "loja-001"),
]


def _uma_linha(texto: str) -> str:
    return " ".join(texto.replace("|", "/").split())


def main() -> int:
    config = Configuracao()
    if not (config.anthropic_api_key and config.anthropic_api_key.get_secret_value().strip()):
        print("Não rodou: falta a ANTHROPIC_API_KEY no .env.")
        return 1
    atendimento = criar_atendimento(config)
    perguntas = {
        p["id"]: p for p in map(json.loads, ARQUIVO_PERGUNTAS.read_text("utf-8").splitlines()) if p
    }
    linhas = []
    for id_pergunta, lojista in ROTEIRO:
        pergunta = perguntas[id_pergunta]
        resultado = atendimento.atender(pergunta["pergunta"], Canal.CHAT, lojista)
        linhas.append(
            {
                "id": id_pergunta,
                "lojista": lojista,
                "gabarito_da_busca": pergunta["gabarito"],
                "pergunta_mascarada": resultado.texto_mascarado,
                "resposta": resultado.resposta,
                "fontes": [a.id for a in resultado.fontes],
                "precisa_pessoa": resultado.precisa_pessoa,
                "motivos_pessoa": resultado.motivos_pessoa,
                "origem_resposta": resultado.origem_resposta,
                "ferramentas_usadas": resultado.ferramentas_usadas,
                "fila": resultado.fila,
                "modo_busca": resultado.modo_busca,
                "avisos": resultado.avisos,
                "tokens_cache_leitura": resultado.uso_resposta.tokens_cache_leitura,
                "tokens_cache_escrita": resultado.uso_resposta.tokens_cache_escrita,
                "custo_usd": resultado.custo_usd,
                "custo_triagem_usd": resultado.custo_triagem_usd,
                "custo_busca_usd": resultado.custo_busca_usd,
                "custo_resposta_usd": resultado.custo_resposta_usd,
                "tempo_ms": resultado.tempo_ms,
            }
        )
        print(f"{id_pergunta}: {resultado.origem_resposta}, pessoa={resultado.precisa_pessoa}")

    total = len(linhas)
    medio = {
        "custo_usd": sum(linha["custo_usd"] for linha in linhas) / total,
        "custo_triagem_usd": sum(linha["custo_triagem_usd"] for linha in linhas) / total,
        "custo_busca_usd": sum(linha["custo_busca_usd"] for linha in linhas) / total,
        "custo_resposta_usd": sum(linha["custo_resposta_usd"] for linha in linhas) / total,
        "tempo_ms": sum(linha["tempo_ms"] for linha in linhas) / total,
    }
    quando = datetime.now(UTC).strftime("%d/%m/%Y %H:%M UTC")
    partes = [
        "# Fumaça do atendimento (não é a avaliação da etapa 3)",
        "",
        f"Rodada em {quando}, com IA de verdade: triagem com `{atendimento.modelo_triagem}` "
        "(com o negócio da Tapiri), resposta com "
        f"`{config.modelo_agente}`, busca com `{config.modelo_embedding}`. "
        f"{total} perguntas de `avaliacao/perguntas_busca.jsonl`, escolhidas antes de rodar.",
        "",
        "A pergunta aparece mascarada, como foi gravada. O custo da busca usa o preço do plano "
        "pago do Google; no plano gratuito, ela sai de graça.",
        "",
        "| Pergunta | Lojista | O que respondeu | Fonte | Chamou pessoa? | Consultas |",
        "|---|---|---|---|---|---|",
    ]
    for linha in linhas:
        pessoa = "não"
        if linha["precisa_pessoa"]:
            pessoa = "sim: " + "; ".join(linha["motivos_pessoa"])
        partes.append(
            f"| {linha['id']}: {_uma_linha(linha['pergunta_mascarada'])} | {linha['lojista']} | "
            f"{_uma_linha(linha['resposta'])} | {', '.join(linha['fontes']) or '—'} | "
            f"{_uma_linha(pessoa)} | {', '.join(linha['ferramentas_usadas']) or '—'} |"
        )
    partes += [
        "",
        f"Custo médio por mensagem: US$ {medio['custo_usd']:.6f} (triagem "
        f"{medio['custo_triagem_usd']:.6f}, busca {medio['custo_busca_usd']:.8f}, resposta "
        f"{medio['custo_resposta_usd']:.6f}).",
        f"Tempo médio por mensagem: {medio['tempo_ms']:.0f} ms.",
    ]
    texto = "\n".join(partes) + "\n"
    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    SAIDA.with_suffix(".md").write_text(texto, "utf-8")
    SAIDA.with_suffix(".json").write_text(
        json.dumps(
            {"quando": quando, "medias": medio, "linhas": linhas}, ensure_ascii=False, indent=2
        )
        + "\n",
        "utf-8",
    )
    print(texto)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
