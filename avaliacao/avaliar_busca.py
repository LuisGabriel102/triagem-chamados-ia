"""Mede a busca da base de conhecimento com perguntas de lojista que têm gabarito.

Uso:
    python -m avaliacao.avaliar_busca              # avalia as 48 perguntas
    python -m avaliacao.avaliar_busca --calibrar   # escolhe os limiares (outras 20 perguntas)

Mede três jeitos de buscar: só por palavras (BM25), só por sentido (embeddings do Gemini) e
os dois juntos (híbrida). Sem acesso ao Google, só a busca por palavras roda; as outras
aparecem como "não rodou". Com acesso, o script primeiro atualiza base/indice.json (só o
artigo que mudou) e manda cada pergunta ao Google uma vez só.

Os limiares de "nada encontrado" saem das perguntas de calibração
(avaliacao/perguntas_calibracao.jsonl), nunca das perguntas da avaliação. Se a busca por
sentido roda e o LIMIAR_SIMILARIDADE ainda está vazio, ele é calibrado na hora.

Ressalva: as perguntas foram escritas junto com a base.

Os relatórios ficam em avaliacao/resultados/: busca.md e calibracao.md (e um .json de cada).
"""

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.base_conhecimento import Artigo, carregar_artigos
from app.busca import (
    ARQUIVO_LIMIARES,
    Busca,
    Modo,
    escolher_limiar,
    escolher_limiares,
    ler_limiares,
)
from app.busca_sentido import (
    ARQUIVO_INDICE,
    ErroSentido,
    GeradorVetores,
    acesso_ao_google,
    atualizar_indice,
    carregar_indice_memoria,
    criar_gerador,
)
from app.config import Configuracao
from avaliacao.avaliar import dado_sobrou

PASTA = Path(__file__).parent
ARQUIVO_PERGUNTAS = PASTA / "perguntas_busca.jsonl"
ARQUIVO_CALIBRACAO = PASTA / "perguntas_calibracao.jsonl"
PASTA_RESULTADOS = PASTA / "resultados"
MODOS: tuple[Modo, ...] = ("palavras", "sentido", "hibrida")
NOMES_DOS_MODOS = {"palavras": "Por palavras", "sentido": "Por sentido", "hibrida": "Híbrida"}
SEM_ACESSO = "falta a GEMINI_API_KEY ou o GOOGLE_CLOUD_PROJECT no .env"
RESSALVA = (
    "As perguntas foram escritas junto com a base, pela mesma pessoa que escreveu os "
    "artigos. Com perguntas de lojistas de verdade, o resultado tende a ser pior."
)


class GeradorGravador:
    """Fica entre a busca e o gerador de verdade: guarda o texto de cada pergunta enviada
    (para contar dados pessoais) e reaproveita o vetor de uma pergunta já enviada."""

    def __init__(self, gerador: GeradorVetores) -> None:
        self._gerador = gerador
        self.modelo = gerador.modelo
        self.dimensoes = gerador.dimensoes
        self.enviados: list[str] = []
        self.chamadas = 0
        self._vetores: dict[str, list[float]] = {}

    def vetor_documento(self, titulo: str, texto: str) -> list[float]:
        return self._gerador.vetor_documento(titulo, texto)

    def vetor_pergunta(self, texto: str) -> list[float]:
        self.enviados.append(texto)
        if texto not in self._vetores:
            self.chamadas += 1
            self._vetores[texto] = self._gerador.vetor_pergunta(texto)
        return self._vetores[texto]


def carregar_perguntas(caminho: Path) -> list[dict[str, Any]]:
    linhas = caminho.read_text("utf-8").splitlines()
    return [json.loads(linha) for linha in linhas if linha.strip()]


def artigos_certos(pergunta: dict[str, Any]) -> list[str]:
    """Os artigos aceitos. Nas perguntas da busca, o gabarito é um artigo (ou None);
    nas do agente, é um dicionário com a lista de artigos aceitos, o principal primeiro."""
    gabarito = pergunta["gabarito"]
    if isinstance(gabarito, dict):
        return list(gabarito.get("artigos") or [])
    return [gabarito] if gabarito else []


def avaliar_modo(
    busca: Busca,
    perguntas: list[dict[str, Any]],
    modo: Modo,
    gravador: GeradorGravador | None = None,
) -> list[dict[str, Any]]:
    linhas = []
    for pergunta in perguntas:
        antes = len(gravador.enviados) if gravador else 0
        resultado = busca.buscar(pergunta["pergunta"], modo)
        enviados = gravador.enviados[antes:] if gravador else []
        candidatos = [achado.artigo.id for achado in resultado.candidatos]
        aceitos = artigos_certos(pergunta)
        gabarito = aceitos[0] if aceitos else None
        certo_entre_os_3 = any(id_artigo in aceitos for id_artigo in candidatos)
        dados = pergunta.get("dados_pessoais", [])
        linhas.append(
            {
                "id": pergunta["id"],
                "gabarito": gabarito,
                "aceitos": aceitos,
                "modo_que_rodou": resultado.modo,
                "candidatos": candidatos,
                "criterio": resultado.criterio,
                "melhor_nota": round(resultado.melhor_nota, 4),
                "nada_encontrado": resultado.nada_encontrado,
                "acerto_1": bool(candidatos) and candidatos[0] in aceitos,
                "acerto_3": certo_entre_os_3,
                # O que importa para o agente: passou do limiar E o artigo certo está
                # entre os 3 que ele vai ler.
                "respondida_certa": certo_entre_os_3 and not resultado.nada_encontrado,
                "dados_pessoais": len(dados),
                "dados_enviados": sum(any(dado_sobrou(d, t) for t in enviados) for d in dados),
                "dados_no_texto_mascarado": sum(
                    dado_sobrou(d, resultado.pergunta_mascarada) for d in dados
                ),
                "avisos": resultado.avisos,
            }
        )
    return linhas


def resumir(linhas: list[dict[str, Any]], modo: Modo) -> dict[str, Any]:
    com = [linha for linha in linhas if linha["gabarito"]]
    sem = [linha for linha in linhas if not linha["gabarito"]]
    return {
        "perguntas": len(linhas),
        "com_resposta": len(com),
        "sem_resposta": len(sem),
        "acerto_1": sum(linha["acerto_1"] for linha in com),
        "acerto_3": sum(linha["acerto_3"] for linha in com),
        "respondidas_certas": sum(linha["respondida_certa"] for linha in com),
        "com_resposta_em_nada_encontrado": sum(linha["nada_encontrado"] for linha in com),
        "sem_resposta_em_nada_encontrado": sum(linha["nada_encontrado"] for linha in sem),
        "dados_pessoais": sum(linha["dados_pessoais"] for linha in linhas),
        "dados_enviados": sum(linha["dados_enviados"] for linha in linhas),
        "dados_no_texto_mascarado": sum(linha["dados_no_texto_mascarado"] for linha in linhas),
        "quedas_para_palavras": sum(linha["modo_que_rodou"] != modo for linha in linhas),
    }


# --- Calibração dos limiares ---


def notas_de_calibracao(
    busca: Busca, perguntas: list[dict[str, Any]], modo: Modo
) -> list[dict[str, Any]] | None:
    """A melhor nota de cada pergunta (BM25 no modo palavras, cosseno no modo sentido).

    Devolve None se o modo não rodar (por exemplo, o Google caiu no meio).
    """
    linhas = []
    for pergunta in perguntas:
        resultado = busca.buscar(pergunta["pergunta"], modo)
        if resultado.modo != modo:
            return None
        topo = resultado.candidatos[0] if resultado.candidatos else None
        nota = 0.0
        if topo is not None:
            nota = (topo.nota_bm25 if modo == "palavras" else topo.similaridade) or 0.0
        linhas.append(
            {
                "id": pergunta["id"],
                "com_resposta": bool(pergunta["gabarito"]),
                "nota": round(nota, 4),
                "primeiro": topo.artigo.id if topo else None,
                "primeiro_certo": bool(topo) and topo.artigo.id == pergunta["gabarito"],
            }
        )
    return linhas


def calibrar(busca: Busca, perguntas: list[dict[str, Any]], modo: Modo) -> dict[str, Any] | None:
    linhas = notas_de_calibracao(busca, perguntas, modo)
    if linhas is None:
        return None
    com = [linha["nota"] for linha in linhas if linha["com_resposta"]]
    sem = [linha["nota"] for linha in linhas if not linha["com_resposta"]]
    limiar = round(escolher_limiar(com, sem), 4)
    return {
        "limiar": limiar,
        "com_resposta": len(com),
        "sem_resposta": len(sem),
        "com_resposta_que_passam": sum(nota >= limiar for nota in com),
        "sem_resposta_barradas": sum(nota < limiar for nota in sem),
        "linhas": linhas,
    }


def relatorio_calibracao(
    quando: str, bm25: dict[str, Any], similaridade: dict[str, Any] | None, motivo: str
) -> str:
    def linha_da_tabela(nome: str, dados: dict[str, Any] | None) -> str:
        if dados is None:
            return f"| {nome} | não rodou ({motivo}) | — | — |"
        return (
            f"| {nome} | {dados['limiar']:g} | "
            f"{dados['com_resposta_que_passam']}/{dados['com_resposta']} | "
            f"{dados['sem_resposta_barradas']}/{dados['sem_resposta']} |"
        )

    partes = [
        '# Calibração dos limiares de "nada encontrado"',
        "",
        f"Rodada em {quando}.",
        f"Perguntas: {bm25['com_resposta'] + bm25['sem_resposta']} "
        f"(`avaliacao/perguntas_calibracao.jsonl`), {bm25['com_resposta']} com resposta na base "
        f"e {bm25['sem_resposta']} sem. São outras perguntas, não as da avaliação.",
        "",
        "Regra: para cada pergunta, pega a nota do artigo mais parecido. O limiar escolhido é "
        "o que deixa passar o maior número de perguntas com resposta e barra o maior número "
        "das sem resposta, pesando os dois grupos igualmente. No empate, fica o do meio.",
        "",
        f"> Ressalva: {RESSALVA} Com tão poucas perguntas, o limiar é uma primeira estimativa.",
        "",
        "| Critério | Limiar | Com resposta que passam | Sem resposta barradas |",
        "|---|---|---|---|",
        linha_da_tabela("Nota do BM25 (busca por palavras)", bm25),
        linha_da_tabela("Similaridade (busca por sentido)", similaridade),
        "",
        "## Nota de cada pergunta",
        "",
        "| Pergunta | Tem resposta | Nota do BM25 | Similaridade |",
        "|---|---|---|---|",
    ]
    por_id = {linha["id"]: linha for linha in (similaridade or {}).get("linhas", [])}
    for linha in bm25["linhas"]:
        outra = por_id.get(linha["id"])
        partes.append(
            f"| {linha['id']} | {'sim' if linha['com_resposta'] else 'não'} | "
            f"{linha['nota']:g} | {f'{outra["nota"]:g}' if outra else '—'} |"
        )
    return "\n".join(partes) + "\n"


# --- Relatório da avaliação ---


def relatorio_busca(quando: str, contexto: dict[str, Any], resultados: dict[str, Any]) -> str:
    def fracao(parte: int, todo: int) -> str:
        return f"{parte}/{todo} ({parte / todo:.0%})" if todo else "—"

    modos = contexto.get("modos", list(MODOS))

    def celulas(chave: str) -> str:
        valores = []
        for modo in modos:
            resultado = resultados[modo]
            if not resultado["rodou"]:
                valores.append("não rodou")
                continue
            resumo = resultado["resumo"]
            if chave == "dados_enviados":
                valores.append(
                    "não se aplica (nada vai para o Google)"
                    if modo == "palavras"
                    else f"{resumo['dados_enviados']} de {resumo['dados_pessoais']}"
                )
            elif chave == "sem_resposta_em_nada_encontrado":
                valores.append(fracao(resumo[chave], resumo["sem_resposta"]))
            elif chave == "quedas_para_palavras":
                valores.append(str(resumo[chave]))
            else:
                valores.append(fracao(resumo[chave], resumo["com_resposta"]))
        return " | ".join(valores)

    palavras = next(resultados[modo]["resumo"] for modo in modos if resultados[modo]["rodou"])
    arquivo = contexto.get("arquivo", "avaliacao/perguntas_busca.jsonl")
    partes = [
        "# Avaliação da busca na base de conhecimento",
        "",
        f"Rodada em {quando}. Base: {contexto['artigos']} artigos (`base/artigos/`). "
        f"Perguntas: {palavras['perguntas']} (`{arquivo}`), "
        f"{palavras['com_resposta']} com o artigo certo no gabarito e "
        f"{palavras['sem_resposta']} sem resposta na base.",
        "",
        f"> **Ressalva:** {contexto.get('ressalva') or RESSALVA}",
        "",
        f"- Busca por sentido: {contexto['sentido']}.",
        f"- Limiar do BM25: {contexto['limiar_bm25']:g} ({contexto['origem_limiar_bm25']}).",
        f"- Limiar da similaridade: {contexto['limiar_similaridade']}.",
        "",
        f"| Medida | {' | '.join(NOMES_DOS_MODOS[modo] for modo in modos)} |",
        "|---" * (len(modos) + 1) + "|",
        f"| **Respondidas e certas** (acima do limiar e com o artigo certo entre os 3) | "
        f"{celulas('respondidas_certas')} |",
        f"| Acerto no 1º lugar | {celulas('acerto_1')} |",
        f"| Acerto entre os 3 primeiros | {celulas('acerto_3')} |",
        f'| Sem resposta que ficaram em "nada encontrado" | '
        f"{celulas('sem_resposta_em_nada_encontrado')} |",
        f'| Com resposta que viraram "nada encontrado" por engano | '
        f"{celulas('com_resposta_em_nada_encontrado')} |",
        f"| Dados pessoais enviados para os embeddings | {celulas('dados_enviados')} |",
        f"| Perguntas que caíram para a busca por palavras | {celulas('quedas_para_palavras')} |",
        "",
        "Conferência que não depende do Google: dados pessoais que sobraram no texto "
        "mascarado, que é o texto que vai para os embeddings: "
        f"{palavras['dados_no_texto_mascarado']} de {palavras['dados_pessoais']}.",
        "",
        'Como ler: "respondidas e certas" é a medida que importa para o agente: a busca '
        "passou do limiar e entregou o artigo certo entre os 3 que ele vai ler. "
        "O acerto no 1º lugar e entre os 3 primeiros olha a ordem dos artigos antes "
        'do limiar, só nas perguntas com resposta. As duas linhas de "nada encontrado" '
        "mostram o efeito do limiar: barrar as sem resposta é o certo; barrar uma com resposta "
        "faz o agente chamar uma pessoa sem precisar.",
    ]
    if any(not resultados[modo]["rodou"] for modo in modos):
        partes += ["", "Por que não rodou:"]
        for modo in modos:
            if not resultados[modo]["rodou"]:
                partes.append(f"- {NOMES_DOS_MODOS[modo]}: {resultados[modo]['motivo']}.")
    for modo in modos:
        if not resultados[modo]["rodou"]:
            continue
        erros = [
            linha
            for linha in resultados[modo]["linhas"]
            if (linha["gabarito"] and not linha["acerto_1"])
            or (linha["gabarito"] is None) != linha["nada_encontrado"]
        ]
        partes += ["", f"## Onde errou: {NOMES_DOS_MODOS[modo].lower()}", ""]
        if not erros:
            partes.append("Nenhum erro.")
            continue
        partes += [
            "| Pergunta | Gabarito | 1º lugar | Nota | Nada encontrado |",
            "|---|---|---|---|---|",
        ]
        for linha in erros:
            primeiro = linha["candidatos"][0] if linha["candidatos"] else "—"
            partes.append(
                f"| {linha['id']} | {linha['gabarito'] or '(sem resposta)'} | {primeiro} | "
                f"{linha['melhor_nota']:g} | {'sim' if linha['nada_encontrado'] else 'não'} |"
            )
    return "\n".join(partes) + "\n"


# --- Execução ---


def _preparar_sentido(
    config: Configuracao, artigos: list[Artigo], caminho_indice: Path
) -> tuple[GeradorGravador | None, Any, str]:
    """O gerador (com gravador) e o índice, ou o motivo de a busca por sentido não rodar."""
    gerador = criar_gerador(config)
    if gerador is None:
        return None, None, SEM_ACESSO
    try:
        relatorio = atualizar_indice(artigos, gerador, caminho_indice)
        if relatorio.refeitos:
            print(f"Índice atualizado: {len(relatorio.refeitos)} artigo(s) refeito(s).")
        indice = carregar_indice_memoria(artigos, gerador.modelo, gerador.dimensoes, caminho_indice)
    except ErroSentido as erro:
        return None, None, str(erro)
    return GeradorGravador(gerador), indice, ""


def gravar_limiares(
    caminho: Path,
    data: str,
    bm25: dict[str, Any],
    similaridade: dict[str, Any] | None,
    modelo: str | None,
    dimensoes: int | None,
) -> None:
    """Grava base/limiares.json. Sem a busca por sentido nesta rodada, o limiar da
    similaridade que já estava no arquivo fica como estava."""

    def resumo(dados: dict[str, Any]) -> dict[str, Any]:
        return {
            "limiar": dados["limiar"],
            "calibrado_em": data,
            "com_resposta_que_passam": dados["com_resposta_que_passam"],
            "com_resposta": dados["com_resposta"],
            "sem_resposta_barradas": dados["sem_resposta_barradas"],
            "sem_resposta": dados["sem_resposta"],
        }

    anterior = ler_limiares(caminho)
    conteudo: dict[str, Any] = {
        "conjunto_de_calibracao": "avaliacao/perguntas_calibracao.jsonl",
        "regra": "o limiar que mais separa as perguntas com resposta das sem resposta, "
        "pesando os dois grupos igualmente (app/busca.py, escolher_limiar)",
        "sobrescrever": "LIMIAR_BM25 e LIMIAR_SIMILARIDADE no ambiente, se existirem",
        "bm25": resumo(bm25),
        "similaridade": anterior.get("similaridade"),
    }
    if similaridade is not None:
        conteudo["similaridade"] = {
            "modelo": modelo,
            "dimensoes": dimensoes,
            **resumo(similaridade),
        }
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(json.dumps(conteudo, ensure_ascii=False, indent=2) + "\n", "utf-8")


def _gravar(pasta: Path, nome: str, texto: str, dados: dict[str, Any]) -> None:
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / f"{nome}.md").write_text(texto, "utf-8")
    (pasta / f"{nome}.json").write_text(
        json.dumps(dados, ensure_ascii=False, indent=2) + "\n", "utf-8"
    )


def main(argumentos: list[str] | None = None) -> int:
    leitor = argparse.ArgumentParser(description="Mede a busca na base de conhecimento.")
    leitor.add_argument(
        "--calibrar", action="store_true", help="escolhe os limiares com as perguntas de calibração"
    )
    leitor.add_argument("--saida", type=Path, default=PASTA_RESULTADOS)
    leitor.add_argument("--indice", type=Path, default=ARQUIVO_INDICE)
    leitor.add_argument("--limiares", type=Path, default=ARQUIVO_LIMIARES)
    leitor.add_argument("--perguntas", type=Path, default=ARQUIVO_PERGUNTAS)
    leitor.add_argument("--nome", default="busca", help="nome do relatório (sem extensão)")
    leitor.add_argument("--modos", nargs="+", choices=MODOS, default=list(MODOS))
    leitor.add_argument("--ressalva", help="troca a ressalva padrão do relatório")
    args = leitor.parse_args(argumentos)

    config = Configuracao()
    artigos = carregar_artigos()
    gravador, indice, motivo = _preparar_sentido(config, artigos, args.indice)
    limiares = escolher_limiares(
        config,
        gravador.modelo if gravador else None,
        gravador.dimensoes if gravador else None,
        args.limiares,
    )
    busca = Busca(
        artigos,
        gravador,
        indice,
        limiar_bm25=limiares.bm25,
        limiar_similaridade=limiares.similaridade,
    )
    agora = datetime.now(UTC)
    quando = agora.strftime("%d/%m/%Y %H:%M UTC")
    calibracao = carregar_perguntas(ARQUIVO_CALIBRACAO)

    if args.calibrar:
        bm25 = calibrar(busca, calibracao, "palavras")
        assert bm25 is not None  # a busca por palavras sempre roda
        similaridade = calibrar(busca, calibracao, "sentido") if gravador else None
        if gravador and similaridade is None:
            motivo = "o Google falhou no meio da calibração"
        texto = relatorio_calibracao(quando, bm25, similaridade, motivo)
        _gravar(
            args.saida,
            "calibracao",
            texto,
            {"quando": quando, "nota_bm25": bm25, "similaridade": similaridade},
        )
        gravar_limiares(
            args.limiares,
            agora.date().isoformat(),
            bm25,
            similaridade,
            gravador.modelo if gravador else None,
            gravador.dimensoes if gravador else None,
        )
        print(texto)
        print(f"Limiares gravados em {args.limiares}.")
        return 0

    contexto: dict[str, Any] = {
        "artigos": len(artigos),
        "arquivo": args.perguntas.resolve().relative_to(PASTA.parent).as_posix()
        if args.perguntas.resolve().is_relative_to(PASTA.parent)
        else str(args.perguntas),
        "modos": list(args.modos),
        "ressalva": args.ressalva,
        "limiar_bm25": limiares.bm25,
        "origem_limiar_bm25": limiares.origem_bm25,
        "sentido": f"pela {acesso_ao_google(config) or 'gerador configurado'}, "
        f"modelo {gravador.modelo}, {gravador.dimensoes} dimensões"
        if gravador
        else f"não rodou ({motivo})",
        "limiar_similaridade": "não se aplica (a busca por sentido não rodou)",
    }
    if gravador:
        if limiares.similaridade is not None:
            contexto["limiar_similaridade"] = (
                f"{limiares.similaridade:g} ({limiares.origem_similaridade})"
            )
        else:
            calibrado = calibrar(busca, calibracao, "sentido")
            if calibrado is not None:
                busca.limiar_similaridade = calibrado["limiar"]
                contexto["limiar_similaridade"] = (
                    f"{calibrado['limiar']:g} (calibrado nesta rodada com as perguntas de "
                    "calibração e não gravado; rode --calibrar para gravar)"
                )

    perguntas = carregar_perguntas(args.perguntas)
    resultados: dict[str, Any] = {}
    for modo in args.modos:
        if modo != "palavras" and gravador is None:
            resultados[modo] = {"rodou": False, "motivo": motivo}
            continue
        # A primeira pergunta vai sozinha: se o Google falhar logo de cara, para aqui.
        linhas = avaliar_modo(busca, perguntas[:1], modo, gravador)
        if linhas[0]["modo_que_rodou"] != modo:
            resultados[modo] = {"rodou": False, "motivo": " ".join(linhas[0]["avisos"])}
            continue
        linhas += avaliar_modo(busca, perguntas[1:], modo, gravador)
        resultados[modo] = {"rodou": True, "resumo": resumir(linhas, modo), "linhas": linhas}
    if gravador:
        contexto["chamadas_ao_google_com_perguntas"] = gravador.chamadas

    texto = relatorio_busca(quando, contexto, resultados)
    _gravar(
        args.saida,
        args.nome,
        texto,
        {"quando": quando, "contexto": contexto, "resultados": resultados},
    )
    print(texto)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
