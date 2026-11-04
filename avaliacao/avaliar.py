"""Mede o acerto da triagem nos chamados de teste com gabarito.

Uso:
    python -m avaliacao.avaliar --modo regras   # plano B, sem IA, roda em qualquer lugar
    python -m avaliacao.avaliar --modo ia       # precisa de ANTHROPIC_API_KEY no .env

O relatório aparece na tela e fica salvo em avaliacao/resultados/.
"""

import argparse
import json
import re
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.classificador import criar_classificador
from app.config import Configuracao
from app.esquemas import Canal
from app.servico import ServicoTriagem

PASTA = Path(__file__).parent
ARQUIVO_CHAMADOS = PASTA / "chamados_teste.jsonl"
PASTA_RESULTADOS = PASTA / "resultados"
CAMPOS = ("categoria", "prioridade", "sentimento", "numero_pedido")
NOMES = {
    "categoria": "categoria",
    "prioridade": "prioridade",
    "sentimento": "sentimento",
    "numero_pedido": "número do pedido",
}


def carregar_chamados(caminho: Path = ARQUIVO_CHAMADOS) -> list[dict[str, Any]]:
    linhas = caminho.read_text("utf-8").splitlines()
    return [json.loads(linha) for linha in linhas if linha.strip()]


def dado_sobrou(dado: str, texto_mascarado: str) -> bool:
    """O dado pessoal continua no texto que iria para a IA?"""
    if "@" in dado:
        return dado in texto_mascarado
    return re.sub(r"\D", "", dado) in re.sub(r"\D", "", texto_mascarado)


def avaliar(servico: ServicoTriagem, chamados: list[dict[str, Any]]) -> list[dict[str, Any]]:
    linhas = []
    for chamado in chamados:
        resultado = servico.triar(chamado["texto"], Canal(chamado["canal"]))
        triagem, uso = resultado.triagem, resultado.uso
        previsto = {
            "categoria": triagem.categoria.value,
            "prioridade": triagem.prioridade.value,
            "sentimento": triagem.sentimento.value,
            "numero_pedido": triagem.numero_pedido,
        }
        gabarito = chamado["gabarito"]
        dados_pessoais = chamado.get("dados_pessoais", [])
        linhas.append(
            {
                "id": chamado["id"],
                "gabarito": gabarito,
                "previsto": previsto,
                "acertos": {campo: previsto[campo] == gabarito[campo] for campo in CAMPOS},
                "origem": resultado.origem.value,
                "revisao_humana": resultado.revisao_humana,
                "motivos_revisao": resultado.motivos_revisao,
                "confianca": triagem.confianca,
                "dados_pessoais": len(dados_pessoais),
                "dados_que_sobraram": sum(
                    dado_sobrou(d, resultado.texto_mascarado) for d in dados_pessoais
                ),
                "tokens_entrada": uso.tokens_entrada
                + uso.tokens_cache_escrita
                + uso.tokens_cache_leitura,
                "tokens_cache_leitura": uso.tokens_cache_leitura,
                "tokens_saida": uso.tokens_saida,
                "custo_usd": resultado.custo_usd,
                "tempo_ms": resultado.tempo_ms,
            }
        )
    return linhas


def _taxa(parte: int, total: int) -> float | None:
    return round(parte / total, 4) if total else None


def resumir(linhas: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(linhas)
    acertos = {campo: sum(linha["acertos"][campo] for linha in linhas) for campo in CAMPOS}
    liberados = [linha for linha in linhas if not linha["revisao_humana"]]
    urgentes = [linha for linha in linhas if linha["gabarito"]["prioridade"] == "urgente"]
    custo_total = sum(linha["custo_usd"] for linha in linhas)
    trocas = Counter(
        f"{linha['gabarito']['categoria']} → {linha['previsto']['categoria']}"
        for linha in linhas
        if not linha["acertos"]["categoria"]
    )
    return {
        "total_chamados": total,
        "acertos": acertos,
        "taxa_acerto": {campo: _taxa(n, total) for campo, n in acertos.items()},
        "todos_os_campos_certos": sum(all(linha["acertos"].values()) for linha in linhas),
        "enviados_para_revisao": total - len(liberados),
        "liberados_sem_revisao": len(liberados),
        # Quando o sistema decide sozinho, quantas vezes acerta categoria e prioridade juntas.
        "liberados_certos": sum(
            linha["acertos"]["categoria"] and linha["acertos"]["prioridade"] for linha in liberados
        ),
        "urgentes": len(urgentes),
        "urgentes_reconhecidos": sum(
            linha["previsto"]["prioridade"] == "urgente" for linha in urgentes
        ),
        "urgentes_sem_olhar_humano": sum(not linha["revisao_humana"] for linha in urgentes),
        "dados_pessoais": sum(linha["dados_pessoais"] for linha in linhas),
        "dados_que_sobraram": sum(linha["dados_que_sobraram"] for linha in linhas),
        "quedas_para_o_plano_b": sum(linha["origem"] == "regras" for linha in linhas),
        "custo_total_usd": round(custo_total, 6),
        "custo_medio_usd": round(custo_total / total, 8) if total else 0.0,
        "tempo_medio_ms": round(sum(linha["tempo_ms"] for linha in linhas) / total, 1)
        if total
        else 0.0,
        "tokens_entrada_medio": round(sum(linha["tokens_entrada"] for linha in linhas) / total)
        if total
        else 0,
        "tokens_saida_medio": round(sum(linha["tokens_saida"] for linha in linhas) / total)
        if total
        else 0,
        "trocas_de_categoria": dict(trocas.most_common()),
    }


def relatorio(modo: str, modelo: str | None, quando: str, resumo: dict, linhas: list) -> str:
    total = resumo["total_chamados"]

    def fracao(parte: int, todo: int) -> str:
        return f"{parte}/{todo} ({parte / todo:.0%})" if todo else "—"

    origem = f"com o modelo `{modelo}`" if modelo else "sem IA, só com o plano B por regras"
    partes = [
        f"# Avaliação: modo `{modo}`",
        "",
        f"Rodada em {quando}, {origem}.",
        f"Conjunto: {total} chamados escritos para teste, com gabarito "
        "(`avaliacao/chamados_teste.jsonl`).",
        "",
        "| Medida | Resultado |",
        "|---|---|",
    ]
    for campo in CAMPOS:
        partes.append(f"| Acerto de {NOMES[campo]} | {fracao(resumo['acertos'][campo], total)} |")
    partes += [
        f"| Os 4 campos certos no mesmo chamado | "
        f"{fracao(resumo['todos_os_campos_certos'], total)} |",
        f"| Urgentes reconhecidos como urgentes | "
        f"{fracao(resumo['urgentes_reconhecidos'], resumo['urgentes'])} |",
        f"| Urgentes liberados sem olhar humano | {resumo['urgentes_sem_olhar_humano']} |",
        f"| Enviados para revisão humana | {fracao(resumo['enviados_para_revisao'], total)} |",
        f"| Liberados sem revisão com categoria e prioridade certas | "
        f"{fracao(resumo['liberados_certos'], resumo['liberados_sem_revisao'])} |",
        f"| Dados pessoais que sobraram no texto enviado à IA | "
        f"{resumo['dados_que_sobraram']} de {resumo['dados_pessoais']} |",
        f"| Quedas para o plano B | {resumo['quedas_para_o_plano_b']} |",
        f"| Custo total | US$ {resumo['custo_total_usd']:.4f} |",
        f"| Custo médio por chamado | US$ {resumo['custo_medio_usd']:.6f} |",
        f"| Tempo médio por chamado | {resumo['tempo_medio_ms']:.0f} ms |",
        "",
        "## Onde errou",
        "",
        "| Chamado | Campo | Gabarito | Resultado |",
        "|---|---|---|---|",
    ]
    for linha in linhas:
        for campo in CAMPOS:
            if not linha["acertos"][campo]:
                esperado = linha["gabarito"][campo] or "—"
                obtido = linha["previsto"][campo] or "—"
                partes.append(f"| {linha['id']} | {NOMES[campo]} | {esperado} | {obtido} |")
    return "\n".join(partes) + "\n"


def main(argumentos: list[str] | None = None) -> int:
    leitor = argparse.ArgumentParser(description="Mede o acerto da triagem com o gabarito.")
    leitor.add_argument("--modo", choices=("regras", "ia"), default="regras")
    leitor.add_argument("--saida", type=Path, default=PASTA_RESULTADOS)
    args = leitor.parse_args(argumentos)

    if args.modo == "ia":
        config = Configuracao()
        classificador = criar_classificador(config)
        if classificador is None:
            print("Defina ANTHROPIC_API_KEY no arquivo .env para avaliar a IA.", file=sys.stderr)
            return 1
        servico = ServicoTriagem(
            classificador,
            limite_confianca=config.limite_confianca,
            preco_entrada=config.preco_entrada_usd_mtok,
            preco_saida=config.preco_saida_usd_mtok,
        )
    else:
        servico = ServicoTriagem()

    linhas = avaliar(servico, carregar_chamados())
    resumo = resumir(linhas)
    quando = datetime.now(UTC).strftime("%d/%m/%Y %H:%M UTC")
    texto = relatorio(args.modo, servico.modelo, quando, resumo, linhas)

    args.saida.mkdir(parents=True, exist_ok=True)
    (args.saida / f"{args.modo}.md").write_text(texto, "utf-8")
    detalhes = {
        "modo": args.modo,
        "modelo": servico.modelo,
        "quando": quando,
        "resumo": resumo,
        "chamados": linhas,
    }
    (args.saida / f"{args.modo}.json").write_text(
        json.dumps(detalhes, ensure_ascii=False, indent=2) + "\n", "utf-8"
    )
    print(texto)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
