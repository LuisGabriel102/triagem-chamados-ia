"""Orquestra a triagem: mascara, classifica, confere a resposta e decide a fila."""

import logging
import re
import time
from dataclasses import dataclass

from app.classificador import ClassificadorClaude, ErroClassificador, Uso, criar_classificador
from app.config import Configuracao
from app.esquemas import (
    FILA_POR_CATEGORIA,
    Canal,
    Categoria,
    Origem,
    Prioridade,
    Triagem,
    TriagemDemo,
)
from app.mascaramento import mascarar
from app.regras import classificar_por_regras

log = logging.getLogger(__name__)

# Escrever no cache (validade de 5 minutos) custa 25% a mais que a entrada normal.
MULTIPLICADOR_CACHE_ESCRITA = 1.25
# Ler do cache custa 10% do preço da entrada normal.
MULTIPLICADOR_CACHE_LEITURA = 0.10


@dataclass(frozen=True)
class ResultadoTriagem:
    canal: Canal
    texto_mascarado: str
    dados_pessoais_encontrados: dict[str, int]
    triagem: Triagem
    fila: str
    origem: Origem
    revisao_humana: bool
    motivos_revisao: list[str]
    modelo: str | None
    uso: Uso
    custo_usd: float
    tempo_ms: int


def para_demo(resultado: ResultadoTriagem) -> TriagemDemo:
    """O que a página de demonstração mostra. Mesmo formato na API e no site gravado."""
    triagem = resultado.triagem
    return TriagemDemo(
        texto_mascarado=resultado.texto_mascarado,
        dados_pessoais_encontrados=resultado.dados_pessoais_encontrados,
        categoria=triagem.categoria,
        prioridade=triagem.prioridade,
        sentimento=triagem.sentimento,
        resumo=triagem.resumo,
        numero_pedido=triagem.numero_pedido,
        resposta_sugerida=triagem.resposta_sugerida,
        confianca=triagem.confianca,
        justificativa=triagem.justificativa,
        fila=resultado.fila,
        origem=resultado.origem,
        revisao_humana=resultado.revisao_humana,
        motivos_revisao=resultado.motivos_revisao,
        modelo=resultado.modelo,
        custo_usd=resultado.custo_usd,
        tempo_ms=resultado.tempo_ms,
    )


def calcular_custo(uso: Uso, preco_entrada: float, preco_saida: float) -> float:
    """Custo em dólar. Os preços são em dólar por milhão de tokens."""
    total = (
        uso.tokens_entrada * preco_entrada
        + uso.tokens_cache_escrita * preco_entrada * MULTIPLICADOR_CACHE_ESCRITA
        + uso.tokens_cache_leitura * preco_entrada * MULTIPLICADOR_CACHE_LEITURA
        + uso.tokens_saida * preco_saida
    )
    return round(total / 1_000_000, 8)


def _pedido_aparece_no_texto(numero: str, texto: str) -> bool:
    """Confere se o número do pedido está mesmo no texto (aceita 458.812 para 458812)."""
    digitos = re.sub(r"\D", "", numero)
    if not digitos:
        return False
    padrao = r"[.\s-]?".join(digitos)
    return re.search(rf"(?<!\d){padrao}(?!\d)", texto) is not None


class ServicoTriagem:
    def __init__(
        self,
        classificador: ClassificadorClaude | None = None,
        limite_confianca: float = 0.75,
        preco_entrada: float = 0.10,
        preco_saida: float = 0.50,
    ) -> None:
        self._classificador = classificador
        self._limite_confianca = limite_confianca
        self._preco_entrada = preco_entrada
        self._preco_saida = preco_saida

    @property
    def ia_configurada(self) -> bool:
        return self._classificador is not None

    @property
    def modelo(self) -> str | None:
        return self._classificador.modelo if self._classificador else None

    def triar(self, texto: str, canal: Canal = Canal.OUTRO) -> ResultadoTriagem:
        inicio = time.perf_counter()
        mascarado = mascarar(texto)
        motivos: list[str] = []
        triagem: Triagem | None = None
        origem, modelo, uso = Origem.REGRAS, None, Uso()

        if self._classificador is None:
            motivos.append("IA não configurada: classificado pelo plano B (regras)")
        else:
            try:
                resultado = self._classificador.classificar(mascarado.texto, canal.value)
                triagem, uso, modelo = resultado.triagem, resultado.uso, resultado.modelo
                origem = Origem.IA
            except ErroClassificador as erro:
                log.warning("IA falhou, usando o plano B: %s", erro)
                uso, modelo = erro.uso, erro.modelo
                motivos.append(f"IA indisponível ({erro}): classificado pelo plano B (regras)")
            except Exception:
                log.exception("Erro inesperado na IA, usando o plano B")
                motivos.append("erro inesperado na IA: classificado pelo plano B (regras)")

        if triagem is None:
            triagem = classificar_por_regras(mascarado.texto)
        else:
            triagem = self._conferir_resposta_da_ia(triagem, mascarado.texto, motivos)
        motivos += self._motivos_de_revisao(triagem, origem)

        tempo_ms = int((time.perf_counter() - inicio) * 1000)
        custo = calcular_custo(uso, self._preco_entrada, self._preco_saida)
        log.info(
            "chamado triado: categoria=%s prioridade=%s origem=%s revisao=%s tempo_ms=%d "
            "custo_usd=%.6f",
            triagem.categoria.value,
            triagem.prioridade.value,
            origem.value,
            bool(motivos),
            tempo_ms,
            custo,
        )
        return ResultadoTriagem(
            canal=canal,
            texto_mascarado=mascarado.texto,
            dados_pessoais_encontrados=dict(mascarado.encontrados),
            triagem=triagem,
            fila=FILA_POR_CATEGORIA[triagem.categoria],
            origem=origem,
            revisao_humana=bool(motivos),
            motivos_revisao=motivos,
            modelo=modelo,
            uso=uso,
            custo_usd=custo,
            tempo_ms=tempo_ms,
        )

    def _conferir_resposta_da_ia(
        self, triagem: Triagem, texto_mascarado: str, motivos: list[str]
    ) -> Triagem:
        """Checagens depois da IA, antes de confiar na resposta."""
        # A resposta da IA também passa pelo mascaramento (defesa extra).
        alteracoes: dict[str, str | None] = {
            "resumo": mascarar(triagem.resumo).texto,
            "resposta_sugerida": mascarar(triagem.resposta_sugerida).texto,
            "justificativa": mascarar(triagem.justificativa).texto,
        }
        # Número de pedido que não está no texto foi inventado: descarta.
        if triagem.numero_pedido and not _pedido_aparece_no_texto(
            triagem.numero_pedido, texto_mascarado
        ):
            alteracoes["numero_pedido"] = None
            motivos.append("número de pedido descartado: não aparece no texto do cliente")
        # Segunda opinião sobre urgência: se as palavras-chave apontam urgência e a IA
        # não, uma pessoa olha. Também segura quem escreve no chamado uma ordem para a
        # IA baixar a prioridade.
        if (
            triagem.prioridade is not Prioridade.URGENTE
            and classificar_por_regras(texto_mascarado).prioridade is Prioridade.URGENTE
        ):
            motivos.append("as palavras-chave indicam urgência e a IA não confirmou")
        return triagem.model_copy(update=alteracoes)

    def _motivos_de_revisao(self, triagem: Triagem, origem: Origem) -> list[str]:
        motivos = []
        if origem is Origem.IA:
            if triagem.confianca is None:
                motivos.append("a IA não informou a confiança")
            elif triagem.confianca < self._limite_confianca:
                motivos.append(f"confiança baixa ({triagem.confianca:.2f})")
        if triagem.categoria is Categoria.OUTROS:
            motivos.append("categoria 'outros' precisa de um olhar humano")
        if triagem.prioridade is Prioridade.URGENTE:
            motivos.append("prioridade urgente: uma pessoa confirma antes de escalar")
        return motivos


def criar_servico(config: Configuracao) -> ServicoTriagem:
    return ServicoTriagem(
        classificador=criar_classificador(config),
        limite_confianca=config.limite_confianca,
        preco_entrada=config.preco_entrada_usd_mtok,
        preco_saida=config.preco_saida_usd_mtok,
    )
