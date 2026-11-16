"""Monta o exemplo da fila de revisão humana a partir das respostas reais já gravadas. NÃO GASTA.

A página /fila, sem a chave da API, mostra este exemplo: os casos gravados (triagem e
atendimento) que foram para uma pessoa, no mesmo formato que a página monta com os dados ao vivo.

    python scripts/montar_fila_exemplo.py
"""

import json
import sys
from pathlib import Path
from typing import Any

RAIZ = Path(__file__).resolve().parent.parent
TRIAGEM_GRAVADA = RAIZ / "docs" / "exemplos_gravados.json"
ATENDIMENTO_GRAVADO = RAIZ / "docs" / "atendimento_gravado.json"
SAIDA = RAIZ / "app" / "estatico" / "fila_exemplo.json"


def cartao_da_triagem(exemplo: dict[str, Any]) -> dict[str, Any]:
    r = exemplo["resultado"]
    return {
        "tipo": "triagem",
        "titulo": exemplo["nome"],
        "criado_em": None,
        "fila": r["fila"],
        "prioridade": r["prioridade"],
        "motivos": r["motivos_revisao"],
        "texto_mascarado": r["texto_mascarado"],
        "resumo": r["resumo"],
        "resposta": r["resposta_sugerida"],
        "rotulo_resposta": "Resposta sugerida para você revisar",
        "fontes": [],
        "lojista": None,
    }


def cartao_do_atendimento(resposta: dict[str, Any]) -> dict[str, Any]:
    return {
        "tipo": "atendimento",
        "titulo": resposta["nome"],
        "criado_em": None,
        "fila": resposta["fila"],
        "prioridade": resposta["prioridade"],
        "motivos": resposta["motivos_pessoa"],
        "texto_mascarado": resposta["texto_mascarado"],
        "resumo": None,
        "resposta": resposta["resposta"],
        "rotulo_resposta": "O que o lojista já recebeu",
        "fontes": [fonte["titulo"] for fonte in resposta["fontes"]],
        "lojista": resposta["lojista"],
    }


def montar() -> dict[str, Any]:
    triagem = json.loads(TRIAGEM_GRAVADA.read_text("utf-8"))
    atendimento = json.loads(ATENDIMENTO_GRAVADO.read_text("utf-8"))
    cartoes = [
        cartao_da_triagem(e) for e in triagem["exemplos"] if e["resultado"]["revisao_humana"]
    ]
    cartoes += [cartao_do_atendimento(r) for r in atendimento["respostas"] if r["precisa_pessoa"]]
    return {
        "aviso": "Exemplo com respostas reais da IA, gravadas uma vez. Empresa e dados inventados.",
        "cartoes": cartoes,
    }


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    dados = montar()
    SAIDA.write_text(json.dumps(dados, ensure_ascii=False, indent=2) + "\n", "utf-8")
    print(f"{len(dados['cartoes'])} casos em {SAIDA.relative_to(RAIZ)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
