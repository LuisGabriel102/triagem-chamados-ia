"""Mascaramento de dados pessoais (LGPD) antes de qualquer chamada à IA.

Esconde CPF, CNPJ (inclusive o alfanumérico), cartão, e-mail e telefone.
Na dúvida entre esconder e vazar, o código esconde. A exceção são números
sem cara de dado pessoal, como protocolo: esses ficam, porque a equipe
precisa deles para achar o caso.

Desde 16/11/2026, também RG, endereço e nome, por regras de contexto:
- RG: com a palavra "RG" ou "identidade" perto, ou no formato 12.345.678-9.
- Endereço: rua, avenida, travessa etc., seguido do nome e do número da casa.
  O CEP sozinho fica: ele aponta uma região, não uma pessoa.
- Nome: depois de "meu nome é", "me chamo", "aqui é o/a", "sou o/a", "nome do
  titular" e "atenciosamente". Para "aqui é" e "sou", só com letra maiúscula,
  para não esconder "sou a dona da loja".

Por que regras e não um modelo de reconhecimento de entidades: um modelo em
português pesa centenas de megabytes na imagem, demora para carregar no plano
gratuito e erra em texto de chat sem maiúscula. As regras pegam os jeitos mais
comuns de alguém se apresentar e passar endereço, e cada caso está nos testes.
Limite que continua: um nome solto no meio da frase ("a Joana pediu") passa.
"""

import re
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass, field

# DDDs válidos no Brasil. Número sem pontuação só vira telefone se começar por um deles.
# fmt: off
DDDS_VALIDOS = {
    11, 12, 13, 14, 15, 16, 17, 18, 19, 21, 22, 24, 27, 28, 31, 32, 33, 34, 35, 37, 38,
    41, 42, 43, 44, 45, 46, 47, 48, 49, 51, 53, 54, 55, 61, 62, 63, 64, 65, 66, 67, 68,
    69, 71, 73, 74, 75, 77, 79, 81, 82, 83, 84, 85, 86, 87, 88, 89, 91, 92, 93, 94, 95,
    96, 97, 98, 99,
}
# fmt: on

_INVISIVEIS = re.compile(r"[​-‏⁠﻿]")
_CONTROLE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
# CNPJ com pontuação, inclusive o alfanumérico (letras nas 12 primeiras posições).
_CNPJ_FORMATADO = re.compile(
    r"(?<!\w)[A-Za-z0-9]{2}\.[A-Za-z0-9]{3}\.[A-Za-z0-9]{3}/[A-Za-z0-9]{4}-\d{2}(?!\d)"
)
# CPF com pontuação: 529.982.247-25, 529982247-25 ou 529.982.247.25.
_CPF_FORMATADO = re.compile(
    r"(?<!\d)(?:\d{3}\.\d{3}\.\d{3}[. -]?\d{2}|\d{3} ?\d{3} ?\d{3}-\d{2})(?!\d)"
)
# Palavra-chave seguida de número: esconde mesmo com dígito verificador errado,
# porque cliente digita errado. Ex.: "CPF 11144477736", "tel 3221-4567".
# A palavra não pode ser um marcador já colocado ([CPF]) e o trecho até o número
# não pode atravessar outro marcador.
_CONTEXTO = re.compile(
    r"(?<!\[)\b(?P<chave>cpf|cnpj|cart[aã]o|telefone|tel|celular|cel|whatsapp|whats|zap|fone)\b"
    r"(?P<meio>[^\d\n\[\]]{0,20}?)"
    r"(?P<numero>\+?\(?\d(?:(?:\) ?|[ .-])?\d)*)",
    re.IGNORECASE,
)
# Marcador e quantidade de dígitos aceita para cada palavra-chave.
_REGRA_DO_CONTEXTO = {
    "cpf": ("CPF", 11, 11),
    "cnpj": ("CNPJ", 14, 14),
    "cartao": ("CARTAO", 13, 19),
}
_REGRA_TELEFONE = ("TELEFONE", 8, 13)
# Celular ou fixo com +55. Vem antes do cartão: com o código do país, um celular
# pode ter 13 dígitos e passar no teste de cartão por acaso (ex.: +55 82 99999-0007).
_TELEFONE_INTERNACIONAL = re.compile(
    r"\+ ?55[ .-]?\(?\d{2}\)?[ .-]?(?:9[ .-]?)?\d{4}[ .-]?\d{4}(?!\d)"
)
# Sem pontuação, CPF e CNPJ só são escondidos se o dígito verificador bater.
_SEQUENCIA_CNPJ = re.compile(r"(?<!\w)[A-Za-z0-9]{12}\d{2}(?!\w)")
_SEQUENCIA_CPF = re.compile(r"(?<!\d)\d{3} ?\d{3} ?\d{3} ?\d{2}(?!\d)")
# Números em grupos separados por espaço, ponto ou hífen (onde um cartão pode estar).
_GRUPOS_DE_NUMEROS = re.compile(r"(?<!\d)\d+(?:[ .-]\d+)*")
_TELEFONE_FORMATADO = re.compile(r"(?<![\w+])\(?\d{2}\)?[ .-]?(?:9[ .-]?)?\d{4}[ .-]?\d{4}(?!\d)")
_SEQUENCIA_TELEFONE = re.compile(r"(?<!\d)\d{10,11}(?!\d)")
_CELULAR_SEM_DDD = re.compile(r"(?<![\d-])9\d{4}-\d{4}(?![\d-])")

# RG com a palavra perto: esconde de 5 a 13 dígitos, com ou sem pontuação, com ou sem o X
# do fim. Sem a palavra, só o formato inconfundível 12.345.678-9 (o CPF é 3.3.3-2).
_RG_CONTEXTO = re.compile(
    r"(?<!\[)\b(?P<chave>rg|r\.g\.|identidade|registro geral)(?!\w)"
    r"(?P<meio>[^\d\n\[\]]{0,20}?)"
    r"(?P<numero>\d(?:[ .-]?\d){4,12}(?:-?[Xx])?)(?!\d)",
    re.IGNORECASE,
)
_RG_FORMATADO = re.compile(r"(?<![\d.])\d{1,2}\.\d{3}\.\d{3}-[\dXx](?!\w)")
# O CEP sozinho fica (decisão anterior, com teste): ele aponta uma rua ou uma região, não uma
# pessoa. O que identifica é a rua com o número da casa, e isso é escondido logo abaixo.
# Endereço: o tipo de logradouro, um nome sem número e o número da casa. O número não pode
# ser seguido de "vezes", "dias", "reais" etc.: "vendi na rua 3 vezes" não é endereço.
_LOGRADOURO = (
    r"rua|r\.|avenida|av\.?|travessa|tv\.|alameda|al\.|rodovia|rod\.|estrada|"
    r"pra[çc]a|largo|servid[ãa]o"
)
_NAO_E_NUMERO_DE_CASA = (
    r"vez|vezes|dias?|horas?|reais|real|x\b|%|m[eê]s|meses|anos?|minutos?|semanas?|"
    r"maquininhas?|vendas?|parcelas?"
)
_ENDERECO = re.compile(
    rf"(?<![\w\[])(?:{_LOGRADOURO})\s+"
    r"[^\d\n,;:!?()\[\]]{2,50}?\s*,?\s*"
    r"(?:n[º°o]\.?\s*|n[uú]mero\s*)?"
    r"\d{1,5}"
    rf"(?!\d|[,.]\d|\s*(?:{_NAO_E_NUMERO_DE_CASA}))"
    r"(?:\s*[-,/]?\s*(?:apto?\.?|apartamento|sala|bloco|casa)\s*\w{1,5})?",
    re.IGNORECASE,
)
# Nome. Depois destes gatilhos, a primeira palavra pode vir em minúscula (chat sem maiúscula):
_GATILHO_NOME_LIVRE = re.compile(
    # "nome do titular" sozinho aparece em texto de ajuda ("nome do titular ou razão social");
    # só vale com dois-pontos ou "é" depois.
    r"\b(?:meu nome (?:é|e)|me chamo|"
    r"(?:nome do titular|titular da conta|nome completo)[ \t]*(?::|(?:é|e)(?!\w)))"
    r"(?!\w)[ \t]*:?[ \t]*",
    re.IGNORECASE,
)
# Depois destes, só com maiúscula: "sou a dona da loja" não tem nome; "sou a Joana" tem.
_GATILHO_NOME_MAIUSCULA = re.compile(
    r"\b(?:aqui (?:é|e)|sou|atenciosamente|att|abra[çc]os?|ass)(?!\w)[.,:]?[ \t]+"
    r"(?:(?:o|a)[ \t]+)?",
    re.IGNORECASE,
)
_PALAVRA_NOME = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿ][A-Za-zÀ-ÖØ-öø-ÿ'’-]*")
_ESPACO_NA_LINHA = re.compile(r"[ \t]+")
_CONECTORES_DE_NOME = {"de", "da", "do", "dos", "das", "e"}
# Palavras com maiúscula depois de "sou" ou "atenciosamente" que não são nome de pessoa.
_NAO_E_NOME = {
    "tapiri", "equipe", "time", "suporte", "atendimento", "central", "ouvidoria",
    "maquininha", "pix", "app", "loja", "lojista", "dono", "dona", "cliente", "gerente",
    "eu", "o", "a", "um", "uma", "novo", "nova", "empresa", "empresário", "empresária",
    "microempreendedor", "microempreendedora", "aposentado", "aposentada",
}  # fmt: skip
_MAXIMO_DE_PALAVRAS_NO_NOME = 6


@dataclass(frozen=True)
class ResultadoMascaramento:
    texto: str
    encontrados: dict[str, int] = field(default_factory=dict)


def _so_digitos(texto: str) -> str:
    return re.sub(r"\D", "", texto)


def limpar_texto(texto: str) -> str:
    """Normaliza o texto e tira caracteres invisíveis e de controle.

    Assim "５２９" vira "529" e um caractere invisível não esconde um CPF nem uma
    marcação. Quebra de linha e tabulação ficam.
    """
    texto = unicodedata.normalize("NFKC", texto)
    texto = _INVISIVEIS.sub("", texto)
    return _CONTROLE.sub(" ", texto)


def cpf_valido(numero: str) -> bool:
    d = _so_digitos(numero)
    if len(d) != 11 or d == d[0] * 11:
        return False
    for posicao in (9, 10):
        soma = sum(int(d[i]) * (posicao + 1 - i) for i in range(posicao))
        digito = (soma * 10) % 11
        if digito == 10:
            digito = 0
        if digito != int(d[posicao]):
            return False
    return True


def cnpj_valido(numero: str) -> bool:
    """Confere o CNPJ numérico e o alfanumérico (cada letra vale o código ASCII menos 48)."""
    c = re.sub(r"[^0-9A-Za-z]", "", numero).upper()
    if len(c) != 14 or not c[12:].isdigit() or c == c[0] * 14:
        return False
    valores = [ord(caractere) - 48 for caractere in c]
    pesos_1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    pesos_2 = [6, *pesos_1]
    for tamanho, pesos in ((12, pesos_1), (13, pesos_2)):
        resto = sum(valores[i] * pesos[i] for i in range(tamanho)) % 11
        digito = 0 if resto < 2 else 11 - resto
        if digito != valores[tamanho]:
            return False
    return True


def luhn_valido(numero: str) -> bool:
    d = _so_digitos(numero)
    if not 13 <= len(d) <= 19:
        return False
    total = 0
    for i, caractere in enumerate(reversed(d)):
        n = int(caractere)
        if i % 2 == 1:
            n *= 2
            if n > 9:
                n -= 9
        total += n
    return total % 10 == 0


def parece_telefone(numero: str) -> bool:
    """Número sem pontuação: celular (11 dígitos, 9 depois do DDD) ou fixo (10 dígitos)."""
    d = _so_digitos(numero)
    if len(d) not in (10, 11) or int(d[:2]) not in DDDS_VALIDOS:
        return False
    if len(d) == 11:
        return d[2] == "9"
    return d[2] in "2345"


def _cartoes_no_trecho(trecho: str) -> list[tuple[int, int]]:
    """Acha cartões num trecho de números, mesmo com validade ou CVV logo depois.

    Testa blocos de grupos inteiros com 13 a 19 dígitos, do maior para o menor.
    Ex.: em "4111 1111 1111 1111 12" o cartão são os quatro primeiros grupos.
    """
    grupos = [(g.start(), g.end(), g.group()) for g in re.finditer(r"\d+", trecho)]
    achados: list[tuple[int, int]] = []
    inicio = 0
    while inicio < len(grupos):
        candidatos = []
        digitos = ""
        for fim in range(inicio, len(grupos)):
            digitos += grupos[fim][2]
            if len(digitos) > 19:
                break
            if len(digitos) >= 13:
                candidatos.append((fim, digitos))
        for fim, numero in reversed(candidatos):
            if luhn_valido(numero):
                achados.append((grupos[inicio][0], grupos[fim][1]))
                inicio = fim
                break
        inicio += 1
    return achados


def _fim_do_nome(texto: str, inicio: int, exige_maiuscula: bool) -> int | None:
    """Onde termina o nome que começa em `inicio`; None se ali não começa um nome.

    A primeira palavra é o nome (com maiúscula, se `exige_maiuscula`). Depois, só entram
    palavras com maiúscula, e "de", "da", "dos"... quando vem outro nome com maiúscula em
    seguida. Assim "joana da padaria" esconde só "joana", e "Joana Prado da Silva" esconde
    tudo. O nome não atravessa vírgula, ponto nem quebra de linha.
    """
    fim: int | None = None
    posicao = inicio
    for _ in range(_MAXIMO_DE_PALAVRAS_NO_NOME):
        achado = _PALAVRA_NOME.match(texto, posicao)
        if not achado:
            break
        palavra = achado.group()
        minuscula = palavra.casefold()
        # Sigla curta toda em maiúscula ("MEI", "PJ") não é nome: "não sou MEI nem nada".
        sigla = palavra.isupper() and len(palavra) <= 4
        if fim is None:
            if minuscula in _NAO_E_NOME or minuscula in _CONECTORES_DE_NOME or sigla:
                return None
            if exige_maiuscula and not palavra[0].isupper():
                return None
            fim = achado.end()
        elif minuscula in _CONECTORES_DE_NOME:
            pass  # só conta se a próxima palavra for nome; o fim não anda
        elif palavra[0].isupper() and minuscula not in _NAO_E_NOME and not sigla:
            fim = achado.end()
        else:
            break
        espaco = _ESPACO_NA_LINHA.match(texto, achado.end())
        if not espaco:
            break
        posicao = espaco.end()
    return fim


def _trocar_nomes(texto: str, marcar: Callable[[str], str]) -> str:
    """Troca por [NOME] o nome que vem depois de um gatilho ("meu nome é", "sou a"...)."""
    trechos: list[tuple[int, int]] = []
    for padrao, exige_maiuscula in (
        (_GATILHO_NOME_LIVRE, False),
        (_GATILHO_NOME_MAIUSCULA, True),
    ):
        for gatilho in padrao.finditer(texto):
            fim = _fim_do_nome(texto, gatilho.end(), exige_maiuscula)
            if fim is not None:
                trechos.append((gatilho.end(), fim))
    # Dois gatilhos podem apontar o mesmo nome ("meu nome é" e "é"): troca cada trecho uma vez,
    # de trás para a frente, para as posições não mudarem.
    usados: list[tuple[int, int]] = []
    for inicio, fim in sorted(set(trechos), reverse=True):
        if any(inicio < u_fim and u_inicio < fim for u_inicio, u_fim in usados):
            continue
        texto = texto[:inicio] + marcar("NOME") + texto[fim:]
        usados.append((inicio, fim))
    return texto


def mascarar(texto: str) -> ResultadoMascaramento:
    """Limpa o texto, troca dados pessoais por marcadores como [CPF] e conta o que achou."""
    texto = limpar_texto(texto)
    encontrados: dict[str, int] = {}

    def marcar(marcador: str) -> str:
        encontrados[marcador] = encontrados.get(marcador, 0) + 1
        return f"[{marcador}]"

    def trocar(
        padrao: re.Pattern[str], marcador: str, aceitar: Callable[[str], bool] | None = None
    ) -> None:
        nonlocal texto

        def substituir(achado: re.Match[str]) -> str:
            trecho = achado.group(0)
            if aceitar is not None and not aceitar(trecho):
                return trecho
            return marcar(marcador)

        texto = padrao.sub(substituir, texto)

    def trocar_por_contexto(achado: re.Match[str]) -> str:
        chave = achado["chave"].lower().replace("ã", "a")
        marcador, minimo, maximo = _REGRA_DO_CONTEXTO.get(chave, _REGRA_TELEFONE)
        if not minimo <= len(_so_digitos(achado["numero"])) <= maximo:
            return achado.group(0)
        return achado["chave"] + achado["meio"] + marcar(marcador)

    def trocar_cartoes(achado: re.Match[str]) -> str:
        trecho = achado.group(0)
        for inicio, fim in reversed(_cartoes_no_trecho(trecho)):
            trecho = trecho[:inicio] + marcar("CARTAO") + trecho[fim:]
        return trecho

    # A ordem importa: primeiro o que tem formato inconfundível, depois o que
    # precisa de conferência (dígito verificador, Luhn, DDD).
    def trocar_rg_por_contexto(achado: re.Match[str]) -> str:
        return achado["chave"] + achado["meio"] + marcar("RG")

    trocar(_EMAIL, "EMAIL")
    trocar(_CNPJ_FORMATADO, "CNPJ")
    trocar(_CPF_FORMATADO, "CPF")
    # RG e endereço vêm antes das sequências de dígitos: um RG de 9 dígitos não pode virar
    # outra coisa, e o número da casa não pode virar pedaço de telefone.
    texto = _RG_CONTEXTO.sub(trocar_rg_por_contexto, texto)
    trocar(_RG_FORMATADO, "RG")
    trocar(_ENDERECO, "ENDERECO")
    texto = _CONTEXTO.sub(trocar_por_contexto, texto)
    trocar(_TELEFONE_INTERNACIONAL, "TELEFONE")
    trocar(_SEQUENCIA_CNPJ, "CNPJ", aceitar=cnpj_valido)
    trocar(_SEQUENCIA_CPF, "CPF", aceitar=cpf_valido)
    texto = _GRUPOS_DE_NUMEROS.sub(trocar_cartoes, texto)
    trocar(_TELEFONE_FORMATADO, "TELEFONE", aceitar=lambda t: not t.isdigit())
    trocar(_SEQUENCIA_TELEFONE, "TELEFONE", aceitar=parece_telefone)
    trocar(_CELULAR_SEM_DDD, "TELEFONE")
    # O nome vem por último: aí os números já viraram marcador e não confundem.
    texto = _trocar_nomes(texto, marcar)
    return ResultadoMascaramento(texto=texto, encontrados=encontrados)
