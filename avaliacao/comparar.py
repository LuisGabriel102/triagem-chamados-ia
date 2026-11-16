"""Junta as avaliações com IA numa tabela só, para comparar os modelos.

Uso (depois de rodar a avaliação de cada modelo):
    python -m avaliacao.comparar

Lê avaliacao/resultados/ia*.json e grava avaliacao/resultados/comparacao.md.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any

PASTA_RESULTADOS = Path(__file__).parent / "resultados"
ORDEM_DOS_PROVEDORES = {"anthropic": 0, "gemini": 1}


def carregar(pasta: Path) -> list[dict[str, Any]]:
    avaliacoes = [json.loads(p.read_text("utf-8")) for p in sorted(pasta.glob("ia*.json"))]
    # Rodadas antigas não gravavam o provedor: eram todas do Claude.
    for avaliacao in avaliacoes:
        avaliacao["provedor"] = avaliacao.get("provedor") or "anthropic"
    return sorted(
        avaliacoes,
        key=lambda a: (ORDEM_DOS_PROVEDORES.get(a["provedor"], 9), a.get("modelo") or ""),
    )


def _porcentagem(parte: int, todo: int) -> str:
    return f"{parte / todo:.0%}" if todo else "—"


def _dolar(valor: float) -> str:
    return "US$ " + f"{valor:.6f}".replace(".", ",")


def _segundos(milissegundos: float) -> str:
    return f"{milissegundos / 1000:.1f} s".replace(".", ",")


def tabela(avaliacoes: list[dict[str, Any]]) -> str:
    linhas = [
        "# Comparação dos modelos no mesmo gabarito",
        "",
        "Os mesmos 40 chamados de teste, com as mesmas regras e as mesmas conferências.",
        "O conjunto é pequeno e foi escrito junto com os critérios do prompt: serve para "
        "comparar os modelos entre si, não para prometer acerto em produção.",
        "",
        "| Modelo | Categoria | Prioridade | Sentimento | Pedido | Os 4 campos | Urgentes "
        "| Revisão humana | Quedas para o plano B | Custo por chamado | Tempo médio | Rodada |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for avaliacao in avaliacoes:
        r = avaliacao["resumo"]
        total = r["total_chamados"]
        acertos = r["acertos"]
        linhas.append(
            f"| `{avaliacao.get('modelo')}` "
            f"| {_porcentagem(acertos['categoria'], total)} "
            f"| {_porcentagem(acertos['prioridade'], total)} "
            f"| {_porcentagem(acertos['sentimento'], total)} "
            f"| {_porcentagem(acertos['numero_pedido'], total)} "
            f"| {_porcentagem(r['todos_os_campos_certos'], total)} "
            f"| {r['urgentes_reconhecidos']} de {r['urgentes']} "
            f"| {_porcentagem(r['enviados_para_revisao'], total)} "
            f"| {r['quedas_para_o_plano_b']} "
            f"| {_dolar(r['custo_medio_usd'])} "
            f"| {_segundos(r['tempo_medio_ms'])} "
            f"| {avaliacao.get('quando', '—')} |"
        )
    return "\n".join(linhas) + "\n"


def main(argumentos: list[str] | None = None) -> int:
    leitor = argparse.ArgumentParser(description="Compara as avaliações com IA numa tabela.")
    leitor.add_argument("--pasta", type=Path, default=PASTA_RESULTADOS)
    args = leitor.parse_args(argumentos)

    avaliacoes = carregar(args.pasta)
    if len(avaliacoes) < 2:
        print(
            "Preciso de pelo menos duas avaliações com IA em "
            f"{args.pasta} (ia.json, ia_<modelo>.json).",
            file=sys.stderr,
        )
        return 1
    texto = tabela(avaliacoes)
    (args.pasta / "comparacao.md").write_text(texto, "utf-8")
    print(texto)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
