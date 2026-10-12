"""Origens do catálogo, fixadas em commits e conferidas por sha256.

- Produtos: `ecommerce-federated` do repositório público algolia/datasets.
- Imagens: as fotos do dataset da Algolia saíram do ar (404 no Cloudinary, 08/10/2026). Os SKUs desse dataset
  vêm dos dados de exemplo "Sunrise" da commercetools (Apache-2.0), cujas fotos continuam publicadas; o
  `products.csv` do Sunrise dá a imagem de cada SKU.

Os arquivos brutos não entram no git (ficam em `data/raw/`): este módulo baixa a versão fixada e confere o
sha256, para que o catálogo saia igual em qualquer máquina.
"""

import csv
import hashlib
import json
import urllib.request
from dataclasses import dataclass
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Origem:
    pasta: Path
    arquivo: str
    url: str
    sha256: str

    @property
    def caminho(self) -> Path:
        return self.pasta / self.arquivo


PRODUTOS = Origem(
    pasta=RAIZ / "data" / "raw" / "ecommerce-federated",
    arquivo="products.json",
    # último commit de products.json (06/06/2022)
    url="https://raw.githubusercontent.com/algolia/datasets/32bfb56ee8d12bcef7e81844cfb0439bd38699a4/ecommerce-federated/products.json",
    sha256="7f9c3affc153b9d8b6b5169ef2d3ae6d25dfe0745ff92b90309a098650ad37a3",
)
IMAGENS = Origem(
    pasta=RAIZ / "data" / "raw" / "commercetools-sunrise",
    arquivo="products.csv",
    # último commit de data/products.csv (04/01/2022)
    url="https://raw.githubusercontent.com/commercetools/commercetools-sunrise-data/9074de20bbc031867558e14eef494beb3740e7f1/data/products.csv",
    sha256="642c16d0f026cabab762cc7044999962e6642f3f5228f70aa30c20b9833f1cf0",
)
# compatibilidade com quem só precisa saber onde fica o dataset de produtos
PASTA = PRODUTOS.pasta


def _sha256(caminho: Path) -> str:
    return hashlib.sha256(caminho.read_bytes()).hexdigest()


def baixar(origem: Origem = PRODUTOS, pasta: Path | None = None) -> Path:
    """Garante o arquivo na versão fixada; baixa só se faltar ou se o hash não bater."""
    destino = (pasta or origem.pasta) / origem.arquivo
    if destino.exists() and _sha256(destino) == origem.sha256:
        return destino
    destino.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(origem.url, timeout=120) as resp:
        destino.write_bytes(resp.read())
    if _sha256(destino) != origem.sha256:
        raise RuntimeError(f"sha256 inesperado em {destino}: o arquivo de origem mudou")
    return destino


def carregar(pasta: Path | None = None) -> list[dict]:
    return json.loads(baixar(PRODUTOS, pasta).read_text(encoding="utf-8"))


def _maior(url: str) -> str:
    # metade das URLs do Sunrise aponta para a versão de 270 px; a de 560 px existe para todas (conferido em
    # 08/10/2026) e não fica borrada no cartão
    return url.replace("_medium.jpg", "_large.jpg")


def imagens_por_sku(pasta: Path | None = None) -> dict[str, list[str]]:
    """SKU → URLs das fotos no Sunrise da commercetools, na versão grande."""
    with baixar(IMAGENS, pasta).open(encoding="utf-8", newline="") as arquivo:
        return {
            linha["sku"]: [_maior(u.strip()) for u in linha["images"].split(";") if u.strip()]
            for linha in csv.DictReader(arquivo)
            if linha["sku"] and linha["images"]
        }
