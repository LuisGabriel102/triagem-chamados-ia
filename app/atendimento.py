"""O atendimento de uma mensagem do lojista, do começo ao fim. Uma mensagem por vez.

1. Mascara a mensagem (LGPD). Daqui em diante, só o texto mascarado circula.
2. A triagem e a busca na base rodam ao mesmo tempo, para ganhar tempo.
3. Quem responde:
   - tentativa de mandar na IA ou de pedir dado de outra loja: resposta fixa, sem IA;
   - a busca não achou nada parecido: o agente diz que não sabe, sem IA;
   - senão, o Claude responde pela ferramenta, com os artigos achados e as consultas.
4. A conferência: artigo citado que não veio da busca não vale; a resposta passa de novo
   pelo mascaramento; se a IA pede uma pessoa, vai para uma pessoa.
5. O plano B: se a IA falhar, a resposta é o trecho do artigo achado, com "uma pessoa vai
   confirmar". Sem artigo, vai para uma pessoa. O atendimento nunca para.

Vai para uma pessoa quando: a triagem marcou revisão humana (urgente, confiança baixa,
"outros"); a busca deu "nada encontrado"; é reclamação para a Ouvidoria; alguém tenta
mandar na IA ou pedir dado de outra loja; a IA pede uma pessoa ou falha. Mesmo assim, a
resposta leva os primeiros passos seguros do artigo, se houver, e avisa que uma pessoa
vai continuar.
"""

import logging
import re
import time
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Literal

import anthropic

from app.agente import AgenteClaude, ErroAgente, ResultadoAgente
from app.base_conhecimento import (
    TITULO_ESCALONAMENTO,
    Artigo,
    carregar_artigos,
    descricao_do_negocio,
)
from app.busca import Busca, ResultadoBusca, criar_busca
from app.busca_palavras import normalizar
from app.classificador import Uso
from app.config import Configuracao
from app.esquemas import Canal, Categoria, Prioridade
from app.ferramentas import DadosLojistas, LojistaDesconhecido
from app.mascaramento import ResultadoMascaramento, mascarar
from app.servico import ResultadoTriagem, ServicoTriagem, calcular_custo, criar_servico

log = logging.getLogger(__name__)

AVISO_PESSOA = "Uma pessoa da nossa equipe vai continuar o atendimento."
RESPOSTA_NAO_SEI = "Não sei responder isso com segurança. " + AVISO_PESSOA
RESPOSTA_SEGURANCA = "Não posso ajudar com esse pedido por aqui. " + AVISO_PESSOA
FECHO_PLANO_B = "Uma pessoa da nossa equipe vai confirmar."
TAMANHO_DO_TRECHO = 600

OrigemResposta = Literal["ia", "plano_b", "fixa"]

# Tentativa de mandar na IA. O texto chega sem acento e em minúsculas (normalizar).
_INJECAO = re.compile(
    r"\b(ignore|ignora|ignorem|esqueca|esquecam|desconsidere|desconsidera)\b.{0,40}"
    r"\b(instruc\w*|regras?|orientac\w*|prompt|anterior\w*|comandos?)\b"
    r"|\b(prompt|instrucoes)\s+(do|de)\s+sistema\b|\bsystem\s+prompt\b"
    r"|\b(voce agora e|a partir de agora voce|aja como|finja (que|ser))\b"
    r"|\bmodo\s+(desenvolvedor|admin\w*|deus|irrestrito)\b|\bjailbreak\b"
    r"|\b(revele|mostre|repita|imprima)\b.{0,30}\b(suas|tuas|as)\s+(instrucoes|regras)\b"
)
# Pedido de dado de outra loja: precisa citar outra loja E pedir um dado.
_OUTRA_LOJA = re.compile(
    r"\b(loja|lojista|cadastro)[\s-]*0*\d{1,4}\b"
    r"|\b(outr[oa]s?|vizinh[oa]s?|concorrentes?)\s+(lojas?|lojistas?|comerciantes?|"
    r"estabelecimentos?)\b"
    r"|\b(do|da|de)\s+(meu|minha)\s+(vizinh\w*|concorrente|amig[oa]|irma\w*|soci[oa]|"
    r"prim[oa]|cunhad[oa])\b"
)
_DADO_PEDIDO = re.compile(
    r"\b(vendas?|recebimentos?|extrato|saldo|dados|dinheiro|faturamento|cpf|cnpj|senha|"
    r"status|quanto\s+(vendeu|recebeu|faturou))\b"
)


def detectar_tentativa(texto: str) -> str | None:
    """Motivo para mandar a mensagem a uma pessoa sem passar pela IA, ou None."""
    simples = normalizar(texto)
    if _INJECAO.search(simples):
        return "tentativa de mandar na IA"
    if _OUTRA_LOJA.search(simples) and _DADO_PEDIDO.search(simples):
        return "pedido de dado de outra loja"
    return None


def trecho_seguro(artigo: Artigo, limite: int = TAMANHO_DO_TRECHO) -> str:
    """O começo do artigo, sem o bloco "Quando chamar uma pessoa", cortado num parágrafo."""
    corpo = artigo.texto.split(TITULO_ESCALONAMENTO, 1)[0].strip()
    paragrafos = [p.strip() for p in corpo.split("\n\n") if p.strip()]
    trecho: list[str] = []
    for paragrafo in paragrafos:
        if trecho and len("\n\n".join([*trecho, paragrafo])) > limite:
            break
        trecho.append(paragrafo)
    texto = "\n\n".join(trecho)
    if len(texto) > limite:  # um parágrafo só, comprido demais: corta numa frase
        corte = texto.rfind(". ", 0, limite)
        texto = texto[: corte + 1] if corte > 0 else texto[:limite].rstrip() + "…"
    return texto


_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
# Marcas sem dígito, para o mascaramento não confundir com número.
_MARCAS = [f"⟦CONTATO{letra}⟧" for letra in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"]


def contatos_da_empresa(artigos: Sequence[Artigo]) -> frozenset[str]:
    """Os e-mails que aparecem nos artigos: são da empresa, não do lojista."""
    return frozenset(email.lower() for a in artigos for email in _EMAIL.findall(a.texto))


def mascarar_resposta(texto: str, permitidos: frozenset[str]) -> ResultadoMascaramento:
    """Mascara a resposta da IA, menos os contatos da própria empresa (como a ouvidoria)."""
    guardados: dict[str, str] = {}
    for marca, contato in zip(_MARCAS, sorted(permitidos), strict=False):
        if contato in texto:
            texto = texto.replace(contato, marca)
            guardados[marca] = contato
    resultado = mascarar(texto)
    final = resultado.texto
    for marca, contato in guardados.items():
        final = final.replace(marca, contato)
    return ResultadoMascaramento(texto=final, encontrados=resultado.encontrados)


def resposta_plano_b(artigo: Artigo) -> str:
    return (
        f'Encontrei isto na nossa ajuda, em "{artigo.titulo}":\n\n'
        f"{trecho_seguro(artigo)}\n\n{FECHO_PLANO_B}"
    )


@dataclass(frozen=True)
class ResultadoAtendimento:
    canal: Canal
    lojista_id: str
    texto_mascarado: str
    dados_pessoais_encontrados: dict[str, int]
    resposta: str
    fontes: list[Artigo]
    fila: str
    precisa_pessoa: bool
    motivos_pessoa: list[str]
    origem_resposta: OrigemResposta
    categoria: Categoria
    prioridade: Prioridade
    ferramentas_usadas: list[str]
    avisos: list[str]
    modo_busca: str
    modelo_resposta: str | None
    uso_resposta: Uso
    custo_usd: float
    custo_triagem_usd: float
    custo_busca_usd: float
    custo_resposta_usd: float
    tempo_ms: int
    tempo_triagem_ms: int
    tempo_busca_ms: int
    tempo_resposta_ms: int


def _busca_vazia(texto: str, aviso: str) -> ResultadoBusca:
    return ResultadoBusca(
        pergunta_mascarada=texto,
        modo="palavras",
        candidatos=[],
        nada_encontrado=True,
        criterio="nota_bm25",
        melhor_nota=0.0,
        limiar=0.0,
        avisos=[aviso],
    )


class ServicoAtendimento:
    def __init__(
        self,
        triagem: ServicoTriagem,
        busca: Busca,
        agente: AgenteClaude | None,
        dados: DadosLojistas,
        limite_confianca: float = 0.75,
        preco_entrada: float = 0.10,
        preco_saida: float = 0.50,
        preco_embedding: float = 0.20,
        contatos_permitidos: frozenset[str] = frozenset(),
    ) -> None:
        self._triagem = triagem
        self._busca = busca
        self._agente = agente
        self._dados = dados
        self._limite_confianca = limite_confianca
        self._preco_entrada = preco_entrada
        self._preco_saida = preco_saida
        self._preco_embedding = preco_embedding
        self._contatos_permitidos = contatos_permitidos

    @property
    def ia_configurada(self) -> bool:
        return self._agente is not None

    @property
    def modelo_triagem(self) -> str | None:
        return self._triagem.modelo

    def existe_lojista(self, lojista_id: str) -> bool:
        return self._dados.existe(lojista_id)

    def _triar(self, texto: str, canal: Canal) -> ResultadoTriagem:
        try:
            return self._triagem.triar(texto, canal)
        except Exception:
            log.exception("A triagem quebrou; classificando só pelas regras")
            return ServicoTriagem().triar(texto, canal)

    def _buscar(self, texto: str) -> tuple[ResultadoBusca, int]:
        inicio = time.perf_counter()
        try:
            resultado = self._busca.buscar(texto)
        except Exception as erro:
            log.exception("A busca quebrou; seguindo sem artigo")
            resultado = _busca_vazia(texto, f"A busca falhou ({type(erro).__name__}).")
        return resultado, int((time.perf_counter() - inicio) * 1000)

    def _conferir(
        self, resultado: ResultadoAgente, artigos: Sequence[Artigo], motivos: list[str]
    ) -> tuple[str, list[Artigo], OrigemResposta]:
        """Checagens depois da IA, antes de mandar a resposta ao lojista."""
        dados = resultado.resposta
        ids_da_busca = {artigo.id for artigo in artigos}
        fora = [id_artigo for id_artigo in dados.artigos_usados if id_artigo not in ids_da_busca]
        if fora:
            motivos.append(f"a IA citou artigo que não veio da busca ({', '.join(fora)})")
            return resposta_plano_b(artigos[0]), [artigos[0]], "plano_b"
        if (
            not dados.artigos_usados
            and not resultado.ferramentas_usadas
            and not dados.precisa_pessoa
        ):
            motivos.append("a IA respondeu sem citar artigo nem consultar dados")
            return resposta_plano_b(artigos[0]), [artigos[0]], "plano_b"
        # A resposta também passa pelo mascaramento (defesa extra). Os contatos da própria
        # empresa, que estão nos artigos, não são dado pessoal e ficam.
        mascarada = mascarar_resposta(dados.resposta, self._contatos_permitidos)
        if mascarada.encontrados:
            motivos.append("a resposta da IA tinha dado pessoal e foi mascarada")
        if dados.precisa_pessoa:
            motivos.append(f"a IA pediu uma pessoa: {dados.motivo or 'sem motivo informado'}")
        if dados.confianca < self._limite_confianca:
            motivos.append(f"confiança baixa na resposta ({dados.confianca:.2f})")
        fontes = [artigo for artigo in artigos if artigo.id in dados.artigos_usados]
        return mascarada.texto, fontes, "ia"

    def atender(self, mensagem: str, canal: Canal, lojista_id: str) -> ResultadoAtendimento:
        if not self._dados.existe(lojista_id):
            raise LojistaDesconhecido(lojista_id)
        inicio = time.perf_counter()
        mascarado = mascarar(mensagem)
        texto = mascarado.texto
        tentativa = detectar_tentativa(texto)

        # Triagem e busca ao mesmo tempo: as duas esperam a rede.
        with ThreadPoolExecutor(max_workers=2) as executor:
            futuro_triagem = executor.submit(self._triar, texto, canal)
            futuro_busca = executor.submit(self._buscar, texto)
            triagem = futuro_triagem.result()
            busca, tempo_busca_ms = futuro_busca.result()

        motivos: list[str] = [f"triagem: {motivo}" for motivo in triagem.motivos_revisao]
        if triagem.triagem.categoria is Categoria.RECLAMACAO:
            motivos.append("reclamação: vai para a Ouvidoria")
        artigos = [achado.artigo for achado in busca.achados]
        uso_resposta, modelo, usadas = Uso(), None, []
        tempo_resposta_ms = 0
        origem: OrigemResposta

        if tentativa:
            motivos.append(tentativa)
            resposta, fontes, origem = RESPOSTA_SEGURANCA, [], "fixa"
        elif not artigos:
            motivos.append("a busca não achou nada parecido na base: o agente não sabe")
            resposta, fontes, origem = RESPOSTA_NAO_SEI, [], "fixa"
        elif self._agente is None:
            motivos.append("IA não configurada: resposta pelo plano B")
            resposta, fontes, origem = resposta_plano_b(artigos[0]), [artigos[0]], "plano_b"
        else:
            comeco = time.perf_counter()
            try:
                resultado = self._agente.responder(
                    texto, canal.value, artigos, lojista_id, self._dados.hoje()
                )
                uso_resposta, modelo, usadas = (
                    resultado.uso,
                    resultado.modelo,
                    resultado.ferramentas_usadas,
                )
                resposta, fontes, origem = self._conferir(resultado, artigos, motivos)
            except ErroAgente as erro:
                log.warning("O agente falhou, usando o plano B: %s", erro)
                uso_resposta, modelo = erro.uso, erro.modelo
                motivos.append(f"a IA falhou ({erro}): resposta pelo plano B")
                resposta, fontes, origem = resposta_plano_b(artigos[0]), [artigos[0]], "plano_b"
            except Exception:
                log.exception("Erro inesperado no agente, usando o plano B")
                motivos.append("erro inesperado na IA: resposta pelo plano B")
                resposta, fontes, origem = resposta_plano_b(artigos[0]), [artigos[0]], "plano_b"
            tempo_resposta_ms = int((time.perf_counter() - comeco) * 1000)

        precisa_pessoa = bool(motivos)
        if precisa_pessoa and origem == "ia" and AVISO_PESSOA not in resposta:
            resposta = f"{resposta}\n\n{AVISO_PESSOA}"

        custo_busca = round(busca.tokens_embedding * self._preco_embedding / 1_000_000, 8)
        custo_resposta = calcular_custo(uso_resposta, self._preco_entrada, self._preco_saida)
        custo_total = round(triagem.custo_usd + custo_busca + custo_resposta, 8)
        tempo_ms = int((time.perf_counter() - inicio) * 1000)
        log.info(
            "atendimento: categoria=%s busca=%s origem=%s pessoa=%s ferramentas=%d "
            "tempo_ms=%d custo_usd=%.6f",
            triagem.triagem.categoria.value,
            busca.modo,
            origem,
            precisa_pessoa,
            len(usadas),
            tempo_ms,
            custo_total,
        )
        return ResultadoAtendimento(
            canal=canal,
            lojista_id=lojista_id,
            texto_mascarado=texto,
            dados_pessoais_encontrados=dict(mascarado.encontrados),
            resposta=resposta,
            fontes=fontes,
            fila=triagem.fila,
            precisa_pessoa=precisa_pessoa,
            motivos_pessoa=motivos,
            origem_resposta=origem,
            categoria=triagem.triagem.categoria,
            prioridade=triagem.triagem.prioridade,
            ferramentas_usadas=list(usadas),
            avisos=list(busca.avisos),
            modo_busca=busca.modo,
            modelo_resposta=modelo,
            uso_resposta=uso_resposta,
            custo_usd=custo_total,
            custo_triagem_usd=triagem.custo_usd,
            custo_busca_usd=custo_busca,
            custo_resposta_usd=custo_resposta,
            tempo_ms=tempo_ms,
            tempo_triagem_ms=triagem.tempo_ms,
            tempo_busca_ms=tempo_busca_ms,
            tempo_resposta_ms=tempo_resposta_ms,
        )


def criar_atendimento(config: Configuracao) -> ServicoAtendimento:
    """Monta o atendimento: a triagem com o negócio da Tapiri, a busca, os dados e o Claude.

    A triagem daqui é outra, com a descrição da Tapiri (base/EMPRESA.md). A de /chamados
    continua com o negócio padrão.
    """
    triagem = criar_servico(config, negocio=descricao_do_negocio())
    dados = DadosLojistas()
    chave = config.anthropic_api_key.get_secret_value().strip() if config.anthropic_api_key else ""
    agente = None
    if chave:
        cliente = anthropic.Anthropic(api_key=chave, timeout=config.timeout_llm_s, max_retries=2)
        agente = AgenteClaude(cliente, dados, modelo=config.modelo_agente)
    return ServicoAtendimento(
        triagem=triagem,
        busca=criar_busca(config),
        agente=agente,
        dados=dados,
        limite_confianca=config.limite_confianca,
        preco_entrada=config.preco_agente_entrada_usd_mtok,
        preco_saida=config.preco_agente_saida_usd_mtok,
        preco_embedding=config.preco_embedding_usd_mtok,
        contatos_permitidos=contatos_da_empresa(carregar_artigos()),
    )
