"""Plano B: classificação por palavras-chave, usada quando a IA não responde.

É simples de propósito. O objetivo é o serviço nunca parar. Todo chamado
classificado aqui vai para revisão humana.
"""

import re
import unicodedata

from app.esquemas import Categoria, Prioridade, Sentimento, Triagem

# As palavras são comparadas pelo começo: "cobr" pega cobrança, cobrado e cobraram.
# Os textos são comparados sem acento e em minúsculas.
# fmt: off

# Qualquer menção a cancelar vai para a equipe de retenção, mesmo que o chamado fale
# de outras coisas. Por isso o cancelamento é checado antes das outras categorias.
PALAVRAS_CANCELAMENTO = ("cancel", "encerrar", "rescind", "rescis")

# Nas demais categorias vence a que tiver mais palavras encontradas.
# Em caso de empate, vale a ordem abaixo.
PALAVRAS_CATEGORIA: dict[Categoria, tuple[str, ...]] = {
    Categoria.FINANCEIRO: (
        "cobr", "boleto", "fatura", "pagamento", "pagar", "paguei", "pago", "pix",
        "estorno", "reembolso", "nota fiscal", "debit", "mensalidade", "cartao",
    ),
    Categoria.SUPORTE_TECNICO: (
        "erro", "falha", "bug", "nao consigo", "nao funciona", "nao abre", "parou",
        "trava", "lento", "lentidao", "fora do ar", "senha", "login", "acesso", "codigo",
        "integracao", "sincroniz", "aplicativo", "app", "sistema", "site", "instal", "atualiz",
    ),
    Categoria.COMERCIAL: (
        "preco", "quanto custa", "plano", "proposta", "orcamento", "contrat", "upgrade",
        "desconto", "parceria", "revenda", "modulo", "comprar", "interesse",
    ),
    Categoria.RECLAMACAO: (
        "pessim", "absurdo", "horrivel", "descaso", "vergonha", "indignad", "revoltad",
        "insatisfeit", "decepcion", "esperava mais", "falta de respeito", "entrega",
        "encomenda", "defeito", "quebrad", "amassad", "faltando", "demora",
        "ninguem resolve", "ninguem responde",
    ),
}

PALAVRAS_URGENTE = (
    "urgente", "urgencia", "fora do ar", "procon", "reclame aqui", "processar", "processo",
    "advogado", "justica", "sem autoriz", "nao autorizei", "fraude", "parado",
)
PALAVRAS_ALTA = (
    "nao consigo", "nao funciona", "erro", "falha", "parou", "trava", "lento", "bloque",
    "recusad", "cobr", "estorno", "reembolso", "defeito", "faltando", "pessim", "absurdo",
    "indignad", "revoltad",
)
PALAVRAS_BAIXA = (
    "como faco", "como eu", "como posso", "gostaria de saber", "duvida", "informacao",
    "horario", "parabens", "agradec", "elogi", "sugestao", "tudo bem",
)

PALAVRAS_NEGATIVO = (
    "pessim", "absurdo", "horrivel", "ridicul", "descaso", "vergonha", "indignad",
    "revoltad", "insatisfeit", "decepcion", "esperava mais", "falta de respeito",
    "ninguem resolve", "ninguem responde", "procon", "reclame aqui", "processar", "advogado",
)
PALAVRAS_POSITIVO = (
    "parabens", "agradec", "excelente", "otimo", "adorei", "amei", "nota 10", "satisfeit",
    "recomendo",
)

# fmt: on

RESPOSTA_PADRAO: dict[Categoria, str] = {
    Categoria.FINANCEIRO: (
        "Olá! Recebemos sua mensagem sobre pagamento e cobrança. Nossa equipe financeira "
        "vai analisar o caso e retornar por este canal."
    ),
    Categoria.SUPORTE_TECNICO: (
        "Olá! Recebemos o relato do problema. Nossa equipe de suporte vai verificar e "
        "retornar por este canal."
    ),
    Categoria.COMERCIAL: (
        "Olá! Obrigado pelo interesse. Um consultor de vendas vai entrar em contato para ajudar."
    ),
    Categoria.CANCELAMENTO: (
        "Olá! Recebemos sua solicitação sobre cancelamento. Nossa equipe vai retornar por "
        "este canal com os próximos passos."
    ),
    Categoria.RECLAMACAO: (
        "Olá! Sentimos muito pela experiência. Sua reclamação foi registrada e nossa equipe "
        "vai analisar e retornar por este canal."
    ),
    Categoria.OUTROS: (
        "Olá! Recebemos sua mensagem. Nossa equipe vai analisar e retornar por este canal."
    ),
}

# "pedido 458812", "Pedido: 458812", "pedido nº 458.812", "pedido #458812".
_NUMERO_PEDIDO = re.compile(
    r"\bpedido\b[\s:]*(?:(?:numero|n[o.°]?)[\s.:]*)?(?:#\s*)?(\d(?:\.?\d){2,11})\b"
)


def normalizar(texto: str) -> str:
    """Minúsculas e sem acento: "Cobrança" vira "cobranca"."""
    decomposto = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in decomposto if not unicodedata.combining(c)).lower()


def _achar(texto: str, palavras: tuple[str, ...]) -> list[str]:
    """Palavras-chave que aparecem no texto, sempre no começo de uma palavra."""
    return [p for p in palavras if re.search(rf"(?<!\w){re.escape(p)}", texto)]


def _escolher_categoria(texto: str) -> tuple[Categoria, list[str]]:
    achadas = _achar(texto, PALAVRAS_CANCELAMENTO)
    if achadas:
        return Categoria.CANCELAMENTO, achadas
    melhor, melhores = Categoria.OUTROS, []
    for categoria, palavras in PALAVRAS_CATEGORIA.items():
        achadas = _achar(texto, palavras)
        if len(achadas) > len(melhores):
            melhor, melhores = categoria, achadas
    return melhor, melhores


def _escolher_prioridade(texto: str, categoria: Categoria) -> tuple[Prioridade, list[str]]:
    if achadas := _achar(texto, PALAVRAS_URGENTE):
        return Prioridade.URGENTE, achadas
    if categoria is Categoria.CANCELAMENTO:
        return Prioridade.ALTA, ["cancelamento"]
    if achadas := _achar(texto, PALAVRAS_ALTA):
        return Prioridade.ALTA, achadas
    if achadas := _achar(texto, PALAVRAS_BAIXA):
        return Prioridade.BAIXA, achadas
    if categoria is Categoria.OUTROS:
        return Prioridade.BAIXA, []
    return Prioridade.MEDIA, []


def _escolher_sentimento(texto: str) -> Sentimento:
    if _achar(texto, PALAVRAS_NEGATIVO):
        return Sentimento.NEGATIVO
    if _achar(texto, PALAVRAS_POSITIVO):
        return Sentimento.POSITIVO
    return Sentimento.NEUTRO


def _resumir(texto: str, limite: int = 120) -> str:
    primeira_frase = re.split(r"(?<=[.!?])\s+", texto.strip(), maxsplit=1)[0]
    if len(primeira_frase) <= limite:
        return primeira_frase
    return primeira_frase[: limite - 3].rstrip() + "..."


def _explicar(palavras_categoria: list[str], palavras_prioridade: list[str]) -> str:
    def listar(palavras: list[str]) -> str:
        return ", ".join(f"'{p}'" for p in palavras) or "nenhuma palavra-chave"

    return (
        f"Plano B por palavras-chave. Categoria: {listar(palavras_categoria)}. "
        f"Prioridade: {listar(palavras_prioridade)}."
    )


def classificar_por_regras(texto: str) -> Triagem:
    """Classifica um texto já mascarado usando só palavras-chave."""
    normalizado = normalizar(texto)
    categoria, palavras_categoria = _escolher_categoria(normalizado)
    prioridade, palavras_prioridade = _escolher_prioridade(normalizado, categoria)
    pedido = _NUMERO_PEDIDO.search(normalizado)
    return Triagem(
        categoria=categoria,
        prioridade=prioridade,
        sentimento=_escolher_sentimento(normalizado),
        resumo=_resumir(texto),
        numero_pedido=pedido.group(1) if pedido else None,
        resposta_sugerida=RESPOSTA_PADRAO[categoria],
        confianca=None,
        justificativa=_explicar(palavras_categoria, palavras_prioridade),
    )
