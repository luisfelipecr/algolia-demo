"""Acesso aos dados: Analytics API e índice da Algolia (a chave fica só no servidor).

Uma loja por idioma (`pt` em produtos_ptbr, `en` em produtos_en), cada uma com o seu analytics; o catálogo e o
estoque são os mesmos nas duas (mesmos objectIDs). As tools falam com um objeto `Fontes` por loja; os testes
trocam por versões em memória (`definir_fontes`).
O catálogo vem do próprio índice por browse (não conta na cota de buscas) e fica em cache por alguns minutos.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import threading
import time
from typing import Protocol

CAMPOS_CATALOGO = [
    "objectID",
    "nome",
    "marca",
    "categoria",
    "categorias",
    "genero",
    "cor",
    "grupo_cor",
    "grade",
    "tamanhos_disponiveis",
    "em_estoque",
    "em_promocao",
    "preco",
    "avaliacoes",
]
CACHE_S = 600
CACHE_ANALYTICS_S = 300  # status e contagens do sobre_os_dados: repetem a cada tool
LOJAS = ("pt", "en")


def chave_algolia() -> str:
    """A chave própria do copiloto (só `analytics` e `browse`) quando existe; senão a Write key (uso local,
    que também grava sinônimo). O modo público nunca usa a Write key: recusa subir sem a chave própria."""
    chave = os.environ.get("ALGOLIA_COPILOTO_KEY")
    if chave:
        return chave
    if os.environ.get("COPILOTO_PUBLICO") == "1":
        raise RuntimeError("modo público exige ALGOLIA_COPILOTO_KEY (só leitura); a Write key não sobe")
    return os.environ["ALGOLIA_WRITE_API_KEY"]


# avisos de "quando chegar" das duas lojas: um índice só, coberto pela chave do copiloto (produtos_ptbr*)
INDICE_AVISOS = os.environ.get("ALGOLIA_INDEX_AVISOS", "produtos_ptbr_avisos")


def chave_dos_avisos() -> str | None:
    """Chave que grava avisos: a própria (só addObject no índice de avisos) ou, no uso local, a Write key."""
    if os.environ.get("ALGOLIA_AVISOS_KEY"):
        return os.environ["ALGOLIA_AVISOS_KEY"]
    return None if os.environ.get("COPILOTO_PUBLICO") == "1" else os.environ.get("ALGOLIA_WRITE_API_KEY")


def indice_da_loja(loja: str) -> str:
    if loja == "en":
        return os.environ.get("ALGOLIA_INDEX_EN", "produtos_en")
    return os.environ.get("ALGOLIA_INDEX", "produtos_ptbr")


class Fontes(Protocol):
    indice: str

    def buscas_sem_resultado(
        self, inicio: dt.date, fim: dt.date, limite: int, tag: str | None = None
    ) -> list[dict]: ...
    def buscas_mais_feitas(
        self, inicio: dt.date, fim: dt.date, limite: int, tag: str | None = None
    ) -> list[dict]: ...
    def valores_de_filtro(self, atributo: str, inicio: dt.date, fim: dt.date) -> list[dict]: ...
    def filtros_sem_resultado(
        self, inicio: dt.date, fim: dt.date, busca: str | None = None
    ) -> list[dict]: ...
    def analytics_atualizado_em(self) -> str | None: ...
    def contagem_de_buscas(self, inicio: dt.date, fim: dt.date, tag: str | None = None) -> int: ...
    def catalogo(self) -> list[dict]: ...
    def avisos(self) -> list[dict]: ...
    def gravar_aviso(self, aviso: dict) -> None: ...
    def sinonimo(self, object_id: str) -> dict | None: ...
    def salvar_sinonimo(self, sinonimo: dict) -> None: ...
    def remover_sinonimo(self, object_id: str) -> None: ...


class FontesAlgolia:
    def __init__(self, indice: str) -> None:
        from algoliasearch.analytics.client import AnalyticsClientSync
        from algoliasearch.search.client import SearchClientSync

        app_id = os.environ["ALGOLIA_APP_ID"]
        chave = chave_algolia()
        self.indice = indice
        self.analytics = AnalyticsClientSync(app_id, chave, os.environ.get("ALGOLIA_ANALYTICS_REGIAO", "us"))
        self.busca = SearchClientSync(app_id, chave)
        self._catalogo: list[dict] = []
        self._catalogo_em = 0.0
        self._trava = threading.Lock()
        self._cache: dict[tuple, tuple[float, object]] = {}

    def _guardado(self, chave: tuple, buscar):
        agora = time.monotonic()
        achado = self._cache.get(chave)
        if achado and agora - achado[0] < CACHE_ANALYTICS_S:
            return achado[1]
        valor = buscar()
        self._cache[chave] = (agora, valor)
        return valor

    @staticmethod
    def _bruto(resposta) -> dict:
        # lê o JSON cru: os modelos pydantic do client 4.47 quebram em alguns campos opcionais
        return json.loads(resposta.raw_data)

    def buscas_sem_resultado(self, inicio, fim, limite, tag=None):
        r = self.analytics.get_searches_no_results_with_http_info(
            index=self.indice, start_date=f"{inicio}", end_date=f"{fim}", limit=limite, tags=tag
        )
        return self._bruto(r).get("searches") or []

    def buscas_mais_feitas(self, inicio, fim, limite, tag=None):
        r = self.analytics.get_top_searches_with_http_info(
            index=self.indice, start_date=f"{inicio}", end_date=f"{fim}", limit=limite, tags=tag
        )
        return self._bruto(r).get("searches") or []

    def valores_de_filtro(self, atributo, inicio, fim):
        r = self.analytics.get_top_filter_for_attribute_with_http_info(
            attribute=atributo, index=self.indice, start_date=f"{inicio}", end_date=f"{fim}", limit=1000
        )
        return self._bruto(r).get("values") or []

    def filtros_sem_resultado(self, inicio, fim, busca=None):
        # com `busca`, só os filtros que zeraram aquela busca ("" = navegação sem texto)
        r = self.analytics.get_top_filters_no_results_with_http_info(
            index=self.indice, search=busca, start_date=f"{inicio}", end_date=f"{fim}", limit=1000
        )
        valores = []
        # sem dados no período a API devolve {"values": null}; cada grupo é uma combinação de filtros
        for n, grupo in enumerate(self._bruto(r).get("values") or []):
            for v in grupo.get("values") or []:
                valores.append({**v, "count": grupo.get("count", 0), "grupo": n})
        return valores

    def analytics_atualizado_em(self):
        return self._guardado(
            ("status",),
            lambda: self._bruto(self.analytics.get_status_with_http_info(index=self.indice)).get("updatedAt"),
        )

    def contagem_de_buscas(self, inicio, fim, tag=None):
        def buscar():
            # com endDate = hoje, a contagem omite o dia corrente (o top searches inclui); pedindo até o dia
            # seguinte, a lista diária vem completa: soma só os dias do período
            r = self.analytics.get_searches_count_with_http_info(
                index=self.indice,
                start_date=f"{inicio}",
                end_date=f"{fim + dt.timedelta(days=1)}",
                tags=tag,
            )
            dias = self._bruto(r).get("dates") or []
            return sum(d.get("count", 0) for d in dias if f"{inicio}" <= d.get("date", "") <= f"{fim}")

        return self._guardado(("contagem", f"{inicio}", f"{fim}", tag), buscar)

    def catalogo(self):
        with self._trava:
            if self._catalogo and time.monotonic() - self._catalogo_em < CACHE_S:
                return self._catalogo
            itens: list[dict] = []
            self.busca.browse_objects(
                index_name=self.indice,
                aggregator=lambda resposta: itens.extend(h.to_dict() for h in resposta.hits),
                browse_params={"attributesToRetrieve": CAMPOS_CATALOGO, "hitsPerPage": 1000},
            )
            self._catalogo, self._catalogo_em = itens, time.monotonic()
            return itens

    def avisos(self):
        itens: list[dict] = []
        try:
            self.busca.browse_objects(
                index_name=INDICE_AVISOS,
                aggregator=lambda resposta: itens.extend(h.to_dict() for h in resposta.hits),
                browse_params={"hitsPerPage": 1000},
            )
        except Exception as exc:  # o índice nasce no primeiro aviso: antes disso, 404
            if getattr(exc, "status_code", None) != 404:
                raise
        return itens

    def gravar_aviso(self, aviso):
        from algoliasearch.search.client import SearchClientSync

        chave = chave_dos_avisos()
        if not chave:
            raise RuntimeError("sem ALGOLIA_AVISOS_KEY: o registro de avisos está desligado")
        SearchClientSync(os.environ["ALGOLIA_APP_ID"], chave).save_object(INDICE_AVISOS, aviso)

    def sinonimo(self, object_id):
        try:
            return self._bruto(self.busca.get_synonym_with_http_info(self.indice, object_id))
        except Exception as exc:
            if getattr(exc, "status_code", None) == 404:  # não existe; outro erro sobe
                return None
            raise

    def salvar_sinonimo(self, sinonimo):
        self.busca.save_synonym(self.indice, sinonimo["objectID"], sinonimo, forward_to_replicas=True)

    def remover_sinonimo(self, object_id):
        self.busca.delete_synonym(self.indice, object_id, forward_to_replicas=True)


_fontes: dict[str, Fontes] = {}


def fontes(loja: str = "pt") -> Fontes:
    if loja not in _fontes:
        _fontes[loja] = FontesAlgolia(indice_da_loja(loja))
    return _fontes[loja]


def definir_fontes(f: Fontes | dict[str, Fontes] | None) -> None:
    """Testes: um dict por loja, um objeto só (vale para as duas) ou None (volta à Algolia)."""
    _fontes.clear()
    if isinstance(f, dict):
        _fontes.update(f)
    elif f is not None:
        _fontes.update({loja: f for loja in LOJAS})
