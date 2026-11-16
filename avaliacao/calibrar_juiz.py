"""Calibração do juiz: uma pessoa marca 30 respostas, e o código mede quanto o juiz concorda.

Por que existe: todos os números de "resposta certa" vêm do juiz (Claude Sonnet 5.5). Se o juiz
erra muito, os números erram junto. A única régua de fora é uma pessoa. Até 16/11/2026, o juiz
só tinha sido conferido em amostras de 10, lidas por quem escreveu o código.

Como funciona (sem gastar nada com IA):

1. `montar` sorteia 30 respostas já julgadas (semente fixa): 15 que o juiz aprovou e 15 que
   reprovou, sem repetir pergunta. Metade e metade porque, com quase todas aprovadas, um juiz
   que aprova tudo pareceria ótimo. Grava uma página (`marcar.html`) com, para cada caso, o
   mesmo material que o juiz recebeu: a pergunta, o gabarito, os artigos, os dados da loja e a
   resposta. O veredito do juiz NÃO entra na página; fica em `casos.json`.
2. A pessoa abre a página no navegador, marca os 4 critérios de cada caso (os mesmos da
   rubrica do juiz) e baixa o arquivo `marcacoes_juiz.json`.
3. `comparar` lê as marcações e grava o relatório: a concordância em "certa", o kappa de
   Cohen (a concordância descontado o acaso), a concordância em cada critério e cada caso em
   que os dois discordam, com o comentário do juiz ao lado do da pessoa.

Uso:
    python -m avaliacao.calibrar_juiz montar
    python -m avaliacao.calibrar_juiz comparar caminho/marcacoes_juiz.json
"""

import argparse
import html
import json
import random
import sys
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

from app.base_conhecimento import Artigo, carregar_artigos
from app.ferramentas import DadosLojistas
from avaliacao.avaliar_agente import (
    AGORA,
    NOTA_MENSAGEM_FIXA,
    PASTA_RESULTADOS,
    tem_mensagem_fixa,
)
from avaliacao.margem import faixa_em_texto

PASTA = Path(__file__).parent / "calibracao_juiz"
# As rodadas com o código final (versão 2): as 60 de desenvolvimento e as 3 da prova 2.
RODADAS = ["dev_v2_mudanca3.json", "prova2_1.json", "prova2_2.json", "prova2_3.json"]
CRITERIOS = ["correta", "completa", "fiel_a_fonte", "sem_inventar"]
SEMENTE = 20261116
POR_LADO = 15  # 15 aprovadas e 15 reprovadas pelo juiz

EXPLICACAO_DOS_CRITERIOS = {
    "correta": "Responde ao que o lojista perguntou, sem erro em relação aos artigos e aos "
    "dados. Só encaminhar para uma pessoa, sem responder, não conta, a não ser que o gabarito "
    "diga que a base não cobre o assunto. Em tema urgente ou de segurança, dar o primeiro "
    "passo certo e avisar que uma pessoa continua conta como correta.",
    "completa": "Traz o passo principal do artigo esperado e, se o gabarito tiver um fato "
    "esperado, traz esse fato. Faltar o principal é incompleta; faltar um detalhe secundário "
    "não.",
    "fiel_a_fonte": "Tudo o que a resposta afirma está nos artigos ou nos dados da loja. "
    'Cortesia e "uma pessoa vai continuar" não contam.',
    "sem_inventar": "Não inventa prazo, valor, preço, caminho no app, promessa ou recurso que "
    "não esteja nas fontes.",
}


# --- O sorteio ---


def carregar_linhas(nomes: Iterable[str] = RODADAS) -> list[dict[str, Any]]:
    """As linhas julgadas pelo juiz (não as mensagens fixas), com a rodada de origem."""
    linhas = []
    for nome in nomes:
        dados = json.loads((PASTA_RESULTADOS / nome).read_text("utf-8"))
        for linha in dados["linhas"]:
            juiz = linha.get("juiz") or {}
            if juiz.get("julgou") and juiz.get("pelo_juiz"):
                linhas.append({**linha, "rodada": nome.removesuffix(".json")})
    return linhas


def sortear(linhas: Sequence[dict[str, Any]], por_lado: int = POR_LADO) -> list[dict[str, Any]]:
    """Metade aprovada e metade reprovada pelo juiz, sem repetir pergunta, em ordem embaralhada.

    A ordem final é embaralhada para a pessoa não adivinhar o veredito pela posição.
    """
    sorteio = random.Random(SEMENTE)
    embaralhadas = list(linhas)
    sorteio.shuffle(embaralhadas)
    escolhidas: list[dict[str, Any]] = []
    perguntas: set[str] = set()
    for aprovada in (True, False):
        lado = 0
        for linha in embaralhadas:
            chave = f"{linha['rodada'].split('_')[0]}:{linha['id']}"
            if bool(linha["juiz"]["certa"]) != aprovada or chave in perguntas:
                continue
            escolhidas.append(linha)
            perguntas.add(chave)
            lado += 1
            if lado == por_lado:
                break
    sorteio.shuffle(escolhidas)
    return escolhidas


# --- A página para marcar ---


def _caso_para_a_pagina(
    numero: int, linha: dict[str, Any], artigos: dict[str, Artigo], dados: DadosLojistas
) -> dict[str, Any]:
    """O mesmo material que o juiz recebeu (montar_pedido_ao_juiz), sem o veredito."""
    gabarito = linha["gabarito"]
    ids = list(dict.fromkeys([*gabarito["artigos"], *linha["fontes"]]))
    lojista = gabarito["lojista"]
    return {
        "caso": f"c{numero:02d}",
        "pergunta": linha["pergunta_mascarada"],
        "gabarito": {
            "artigos_esperados": gabarito["artigos"] or "nenhum: a base não cobre o assunto",
            "deve_chamar_pessoa": gabarito["chamar_pessoa"],
            "por_que": gabarito["por_que"],
            "fato_esperado": gabarito["fato"],
        },
        "artigos": [
            {"id": i, "titulo": artigos[i].titulo, "texto": artigos[i].texto}
            for i in ids
            if i in artigos
        ],
        "dados_da_loja": {
            "consultar_recebimentos": dados.consultar_recebimentos(lojista),
            "status_maquininha": dados.status_maquininha(lojista),
        },
        "resposta": linha["resposta"],
        "nota_mensagem_fixa": tem_mensagem_fixa(linha["resposta"]),
    }


def _e(texto: Any) -> str:
    return html.escape(str(texto), quote=True)


def montar_pagina(casos: Sequence[dict[str, Any]]) -> str:
    """Uma página só, sem nada de fora. Todo texto entra escapado."""
    criterios_html = "".join(
        f"<li><b>{_e(nome)}</b>: {_e(texto)}</li>"
        for nome, texto in EXPLICACAO_DOS_CRITERIOS.items()
    )
    blocos = []
    for caso in casos:
        artigos = (
            "".join(
                f"<details><summary>{_e(a['titulo'])} ({_e(a['id'])})</summary>"
                f"<pre>{_e(a['texto'])}</pre></details>"
                for a in caso["artigos"]
            )
            or "<p>Nenhum artigo.</p>"
        )
        nota = f'<p class="nota">{_e(NOTA_MENSAGEM_FIXA)}</p>' if caso["nota_mensagem_fixa"] else ""
        marcas = "".join(
            f"<fieldset><legend>{_e(c)}</legend>"
            f'<label><input type="radio" name="{caso["caso"]}-{c}" value="sim"> sim</label>'
            f'<label><input type="radio" name="{caso["caso"]}-{c}" value="nao"> não</label>'
            "</fieldset>"
            for c in CRITERIOS
        )
        gabarito = json.dumps(caso["gabarito"], ensure_ascii=False, indent=2)
        dados_da_loja = json.dumps(caso["dados_da_loja"], ensure_ascii=False, indent=2)
        comentario = f"{caso['caso']}-comentario"
        blocos.append(
            f'<section class="caso" data-caso="{caso["caso"]}">'
            f"<h2>Caso {_e(caso['caso'])}</h2>"
            f"<h3>Pergunta</h3><pre>{_e(caso['pergunta'])}</pre>"
            f"<h3>Gabarito</h3><pre>{_e(gabarito)}</pre>"
            f"<h3>Artigos</h3>{artigos}"
            f"<details><summary>Dados da loja</summary><pre>{_e(dados_da_loja)}</pre></details>"
            f'<h3>Resposta dada</h3>{nota}<pre class="resposta">{_e(caso["resposta"])}</pre>'
            f"{marcas}"
            '<label class="comentario">Comentário (opcional)'
            f'<textarea name="{comentario}" rows="2"></textarea></label>'
            "</section>"
        )
    return PAGINA.replace("{{CRITERIOS}}", criterios_html).replace("{{CASOS}}", "".join(blocos))


PAGINA = """<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Calibrar o juiz</title>
<style>
  :root { --fundo: #fbfaf7; --texto: #1d1b16; --borda: #d8d3c7; --destaque: #f1ede3; }
  @media (prefers-color-scheme: dark) {
    :root { --fundo: #1a1916; --texto: #ece8df; --borda: #48443b; --destaque: #2a2823; }
  }
  body { background: var(--fundo); color: var(--texto); font: 16px/1.5 system-ui, sans-serif;
    max-width: 52rem; margin: 0 auto; padding: 1rem; }
  pre { white-space: pre-wrap; word-break: break-word; background: var(--destaque);
    padding: .6rem; border-radius: 6px; }
  .caso { border-top: 2px solid var(--borda); margin-top: 2rem; padding-top: 1rem; }
  .resposta { border-left: 4px solid var(--borda); }
  .nota { font-size: .9rem; opacity: .85; }
  fieldset { display: inline-block; border: 1px solid var(--borda); margin: .3rem; }
  label { margin-right: .6rem; }
  .comentario { display: block; margin-top: .5rem; }
  textarea { width: 100%; box-sizing: border-box; }
  .barra { position: sticky; bottom: 0; background: var(--fundo); padding: .6rem 0;
    border-top: 1px solid var(--borda); }
  button { font: inherit; padding: .5rem 1rem; }
</style>
</head>
<body>
<h1>Calibrar o juiz</h1>
<p>Para cada caso, leia a pergunta, o gabarito, os artigos e os dados da loja, e julgue só a
resposta dada, com os mesmos critérios que o juiz usou. Não procure o veredito do juiz antes de
terminar: ele está em <code>casos.json</code>, de propósito fora desta página.</p>
<ul>{{CRITERIOS}}</ul>
<p>A resposta conta como <b>certa</b> quando os 4 critérios são "sim". As marcações ficam salvas
neste navegador enquanto você marca. No fim, toque em "Baixar marcações".</p>
{{CASOS}}
<div class="barra"><button id="baixar" type="button">Baixar marcações</button>
<span id="faltam"></span></div>
<script>
(function () {
  "use strict";
  var CHAVE = "calibrar-juiz";
  var campos = document.querySelectorAll("input, textarea");
  function ler() {
    var saida = {};
    document.querySelectorAll(".caso").forEach(function (secao) {
      var caso = secao.dataset.caso;
      var marca = { comentario: secao.querySelector("textarea").value };
      ["correta", "completa", "fiel_a_fonte", "sem_inventar"].forEach(function (c) {
        var escolhido = secao.querySelector('input[name="' + caso + "-" + c + '"]:checked');
        marca[c] = escolhido ? escolhido.value === "sim" : null;
      });
      saida[caso] = marca;
    });
    return saida;
  }
  function contarFaltas(marcas) {
    var faltam = 0;
    Object.keys(marcas).forEach(function (caso) {
      ["correta", "completa", "fiel_a_fonte", "sem_inventar"].forEach(function (c) {
        if (marcas[caso][c] === null) faltam += 1;
      });
    });
    document.getElementById("faltam").textContent =
      faltam ? " Faltam " + faltam + " marcações." : " Tudo marcado.";
  }
  function guardar() {
    var marcas = ler();
    contarFaltas(marcas);
    try { localStorage.setItem(CHAVE, JSON.stringify(marcas)); } catch (e) { /* sem espaço */ }
  }
  try {
    var salvas = JSON.parse(localStorage.getItem(CHAVE) || "{}");
    Object.keys(salvas).forEach(function (caso) {
      var marca = salvas[caso];
      Object.keys(marca).forEach(function (c) {
        if (c === "comentario") {
          var caixa = document.querySelector('textarea[name="' + caso + '-comentario"]');
          if (caixa) caixa.value = marca[c] || "";
        } else if (marca[c] !== null) {
          var opcao = document.querySelector(
            'input[name="' + caso + "-" + c + '"][value="' + (marca[c] ? "sim" : "nao") + '"]');
          if (opcao) opcao.checked = true;
        }
      });
    });
  } catch (e) { /* começa vazio */ }
  campos.forEach(function (campo) {
    campo.addEventListener("change", guardar);
    campo.addEventListener("input", guardar);
  });
  contarFaltas(ler());
  document.getElementById("baixar").addEventListener("click", function () {
    var arquivo = new Blob([JSON.stringify(ler(), null, 2)], { type: "application/json" });
    var link = document.createElement("a");
    link.href = URL.createObjectURL(arquivo);
    link.download = "marcacoes_juiz.json";
    link.click();
  });
})();
</script>
</body>
</html>
"""


def montar(pasta: Path = PASTA) -> list[dict[str, Any]]:
    """Sorteia os casos e grava a página (sem veredito) e o casos.json (com o veredito)."""
    escolhidas = sortear(carregar_linhas())
    artigos = {a.id: a for a in carregar_artigos()}
    # A mesma "hora de agora" da avaliação: os dados da loja saem iguais aos que o juiz viu.
    dados = DadosLojistas(agora=lambda: AGORA)
    casos = [_caso_para_a_pagina(n, linha, artigos, dados) for n, linha in enumerate(escolhidas, 1)]
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / "marcar.html").write_text(montar_pagina(casos), "utf-8")
    vereditos = [
        {
            "caso": caso["caso"],
            "rodada": linha["rodada"],
            "id": linha["id"],
            "juiz": {c: linha["juiz"][c] for c in [*CRITERIOS, "certa", "comentario"]},
        }
        for caso, linha in zip(casos, escolhidas, strict=True)
    ]
    (pasta / "casos.json").write_text(
        json.dumps(vereditos, ensure_ascii=False, indent=2) + "\n", "utf-8"
    )
    return vereditos


# --- A comparação ---


def kappa_de_cohen(pares: Sequence[tuple[bool, bool]]) -> float | None:
    """A concordância descontado o acaso: 1 é perfeita, 0 é o que se espera por sorte.

    None quando os dois marcaram sempre a mesma coisa (o acaso explicaria tudo e a conta
    divide por zero).
    """
    total = len(pares)
    if not total:
        return None
    observada = sum(a == b for a, b in pares) / total
    sim_a = sum(a for a, _ in pares) / total
    sim_b = sum(b for _, b in pares) / total
    esperada = sim_a * sim_b + (1 - sim_a) * (1 - sim_b)
    if esperada == 1:
        return None
    return (observada - esperada) / (1 - esperada)


def comparar(vereditos: Sequence[dict[str, Any]], marcacoes: dict[str, Any]) -> dict[str, Any]:
    """Junta o juiz e a pessoa. Caso sem as 4 marcações fica de fora (e é contado)."""
    completos = []
    incompletos = []
    for item in vereditos:
        marca = marcacoes.get(item["caso"]) or {}
        if any(marca.get(c) is None for c in CRITERIOS):
            incompletos.append(item["caso"])
            continue
        pessoa = {c: bool(marca[c]) for c in CRITERIOS}
        pessoa["certa"] = all(pessoa.values())
        completos.append({**item, "pessoa": pessoa, "comentario_pessoa": marca.get("comentario")})

    def resumo(campo: str) -> dict[str, Any]:
        pares = [(bool(x["juiz"][campo]), x["pessoa"][campo]) for x in completos]
        iguais = sum(a == b for a, b in pares)
        return {
            "iguais": iguais,
            "total": len(pares),
            "kappa": kappa_de_cohen(pares),
            "juiz_sim_pessoa_nao": sum(a and not b for a, b in pares),
            "juiz_nao_pessoa_sim": sum(b and not a for a, b in pares),
        }

    return {
        "casos": len(vereditos),
        "marcados": len(completos),
        "incompletos": incompletos,
        "certa": resumo("certa"),
        "criterios": {c: resumo(c) for c in CRITERIOS},
        "discordancias": [x for x in completos if bool(x["juiz"]["certa"]) != x["pessoa"]["certa"]],
    }


def _kappa(valor: float | None) -> str:
    return "não dá para calcular" if valor is None else f"{valor:.2f}".replace(".", ",")


def relatorio(r: dict[str, Any]) -> str:
    certa = r["certa"]
    faixa = faixa_em_texto(certa["iguais"], certa["total"]) if certa["total"] else "—"
    linhas = [
        "# Calibração do juiz",
        "",
        f"Casos: {r['casos']}. Marcados por inteiro: {r['marcados']}."
        + (
            f" Incompletos (fora da conta): {', '.join(r['incompletos'])}."
            if r["incompletos"]
            else ""
        ),
        "",
        "| | Concordância | Kappa de Cohen | Juiz aprovou, pessoa não | Pessoa aprovou, juiz não |",
        "|---|---|---|---|---|",
        f"| **Certa** | {certa['iguais']}/{certa['total']} ({faixa}) | {_kappa(certa['kappa'])} | "
        f"{certa['juiz_sim_pessoa_nao']} | {certa['juiz_nao_pessoa_sim']} |",
    ]
    for nome, c in r["criterios"].items():
        linhas.append(
            f"| {nome} | {c['iguais']}/{c['total']} | {_kappa(c['kappa'])} | "
            f"{c['juiz_sim_pessoa_nao']} | {c['juiz_nao_pessoa_sim']} |"
        )
    linhas += [
        "",
        "Como ler o kappa: perto de 1, o juiz e a pessoa concordam muito além do acaso; perto "
        "de 0, a concordância é a que se espera por sorte. A amostra tem metade aprovada e "
        "metade reprovada pelo juiz, de propósito; por isso a concordância não é a taxa de acerto "
        "do juiz no conjunto inteiro.",
        "",
        "## Onde discordam",
        "",
    ]
    if not r["discordancias"]:
        linhas.append('Nenhuma discordância em "certa".')
    for x in r["discordancias"]:
        lado = "aprovou" if x["juiz"]["certa"] else "reprovou"
        linhas += [
            f"- **{x['caso']}** ({x['rodada']}, {x['id']}): o juiz {lado}.",
            f"  - Juiz: {x['juiz']['comentario']}",
            f"  - Pessoa: {x.get('comentario_pessoa') or '(sem comentário)'}",
        ]
    return "\n".join(linhas) + "\n"


def main(argumentos: list[str] | None = None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    leitor = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = leitor.add_subparsers(dest="comando", required=True)
    sub.add_parser("montar", help="sorteia os 30 casos e grava a página para marcar")
    comparar_ = sub.add_parser("comparar", help="compara as marcações com o juiz")
    comparar_.add_argument("marcacoes", type=Path)
    args = leitor.parse_args(argumentos)
    if args.comando == "montar":
        vereditos = montar()
        aprovadas = sum(v["juiz"]["certa"] for v in vereditos)
        print(f"{len(vereditos)} casos ({aprovadas} aprovados pelo juiz) em {PASTA}")
        print(f"Abra {PASTA / 'marcar.html'} no navegador.")
        return 0
    vereditos = json.loads((PASTA / "casos.json").read_text("utf-8"))
    marcacoes = json.loads(args.marcacoes.read_text("utf-8"))
    resultado = comparar(vereditos, marcacoes)
    texto = relatorio(resultado)
    (PASTA_RESULTADOS / "calibracao_juiz.md").write_text(texto, "utf-8")
    (PASTA_RESULTADOS / "calibracao_juiz.json").write_text(
        json.dumps(resultado, ensure_ascii=False, indent=2) + "\n", "utf-8"
    )
    print(texto)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
