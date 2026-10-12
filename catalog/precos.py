"""EUR → R$ com câmbio fixo e documentado, arredondado para preço de vitrine.

O câmbio é fixo de propósito: o catálogo precisa sair igual a cada build (o índice é reconstruível pelo repo).
A taxa, a data e a fonte ficam aqui e no README do catálogo.
"""

from decimal import ROUND_HALF_UP, Decimal

# PTAX de venda do Banco Central, boletim de fechamento (a referência do BCE no mesmo dia era 5,5953)
CAMBIO_EUR_BRL = Decimal("5.5867")
CAMBIO_DATA = "2026-10-07"
CAMBIO_FONTE = "https://olinda.bcb.gov.br/olinda/servico/PTAX/versao/v1/odata/ (moeda EUR, Fechamento)"


def para_reais(valor_eur: float | Decimal, cambio: Decimal = CAMBIO_EUR_BRL) -> Decimal:
    """Converte e arredonda para o preço de vitrine terminado em ,90 (ex.: 1.103,40 → 1.103,90).

    Arredonda o real para baixo e soma 0,90: o preço nunca sobe mais de R$ 0,90 por causa do arredondamento.
    """
    if cambio <= 0:
        raise ValueError("câmbio não configurado")
    bruto = (Decimal(str(valor_eur)) * cambio).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return Decimal(int(bruto)) + Decimal("0.90")


def preco_de_venda(preco_de: Decimal, desconto_pct: int) -> Decimal:
    """Preço com desconto, recalculado em reais a partir do preço cheio para manter o ,90 nos dois."""
    if not desconto_pct:
        return preco_de
    com_desconto = preco_de * (Decimal(100 - desconto_pct) / Decimal(100))
    return Decimal(int(com_desconto)) + Decimal("0.90")
