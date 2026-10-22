"""Resolución de alias, año de corte y matriz entidad × indicador (§4 y §5 del PLAN).

La identidad de un indicador es la pareja (Dimensión, Indicador) — nunca incluye
Subcategoría, porque el DNP la cambia entre versiones y es lo que genera las
filas duplicadas. Las repeticiones se agregan con promedio, no con suma.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from .catalogo import CATALOGO, Ind
from .lectura import Fila

log = logging.getLogger("terridata.resolucion")

Clave = tuple[str, str]


@dataclass
class Resultado:
    entidades: list[str]
    departamento: str
    valores: dict[str, dict[str, float | str | None]] = field(default_factory=dict)
    anios: dict[str, int | None] = field(default_factory=dict)
    faltantes: list[str] = field(default_factory=list)
    # Extras que necesitan las gráficas y el dashboard:
    anios_entidad: dict[str, dict[str, int | None]] = field(default_factory=dict)
    fuentes: dict[str, str] = field(default_factory=dict)
    unidades: dict[str, str] = field(default_factory=dict)
    etiquetas: dict[str, str] = field(default_factory=dict)
    decimales: dict[str, int] = field(default_factory=dict)
    alias_usado: dict[str, Clave] = field(default_factory=dict)
    series: dict[str, dict[str, dict[int, float]]] = field(default_factory=dict)

    # --- consulta

    def valor(self, id_indicador: str, entidad: str) -> float | str | None:
        return self.valores.get(id_indicador, {}).get(entidad)

    def numero(self, id_indicador: str, entidad: str) -> float | None:
        v = self.valores.get(id_indicador, {}).get(entidad)
        return float(v) if isinstance(v, (int, float)) else None

    def disponible(self, id_indicador: str) -> bool:
        """Hay al menos una entidad con dato para ese indicador."""
        vals = self.valores.get(id_indicador)
        return bool(vals) and any(v is not None for v in vals.values())

    def serie_temporal(self, id_indicador: str, entidad: str) -> dict[int, float]:
        """Todos los años con dato numérico de ese indicador para esa entidad.

        Sin filtro de año de corte: la #47 (inversión en APSB) ancla su eje al
        último año con dato, no al corte.
        """
        return dict(sorted(self.series.get(id_indicador, {}).get(entidad, {}).items()))

    def ultimo_anio_con_dato(self, id_indicador: str) -> int | None:
        anios = [
            a
            for por_entidad in self.series.get(id_indicador, {}).values()
            for a in por_entidad
        ]
        return max(anios) if anios else None

    def etiqueta(self, id_indicador: str) -> str:
        return self.etiquetas.get(id_indicador, id_indicador)

    def unidad(self, id_indicador: str) -> str:
        return self.unidades.get(id_indicador, "")

    def fuente(self, id_indicador: str) -> str:
        return self.fuentes.get(id_indicador, "")

    def registrar(
        self,
        id_indicador: str,
        etiqueta: str,
        unidad: str,
        decimales: int,
        valores: dict[str, float | str | None],
        anio: int | None = None,
        fuente: str = "",
    ) -> None:
        """Añade un indicador calculado (lo usa derivados.py)."""
        self.valores[id_indicador] = valores
        self.anios[id_indicador] = anio
        self.anios_entidad.setdefault(id_indicador, {e: anio for e in self.entidades})
        self.etiquetas[id_indicador] = etiqueta
        self.unidades[id_indicador] = unidad
        self.decimales[id_indicador] = decimales
        self.fuentes[id_indicador] = fuente


def _indexar(filas: list[Fila]):
    """Agrupa las filas por (dimensión, indicador) y entidad."""
    num: dict[Clave, dict[str, dict[int, list[float]]]] = {}
    txt: dict[Clave, dict[str, str]] = {}
    fuente: dict[Clave, str] = {}
    unidad: dict[Clave, str] = {}

    for f in filas:
        clave = (f.dimension, f.indicador)
        if f.valor is not None:
            por_entidad = num.setdefault(clave, {})
            por_anio = por_entidad.setdefault(f.entidad, {})
            por_anio.setdefault(f.anio, []).append(f.valor)
            fuente.setdefault(clave, f.fuente)
            unidad.setdefault(clave, f.unidad)
        if f.texto:
            # Los indicadores de texto no tienen año útil: vale la primera fila.
            txt.setdefault(clave, {}).setdefault(f.entidad, f.texto)
            fuente.setdefault(clave, f.fuente)

    return num, txt, fuente, unidad


def _promedio(valores: list[float]) -> float:
    return sum(valores) / len(valores)


def _series_de(
    por_entidad: dict[str, dict[int, list[float]]]
) -> dict[str, dict[int, float]]:
    return {
        entidad: {anio: _promedio(vs) for anio, vs in por_anio.items()}
        for entidad, por_anio in por_entidad.items()
    }


def _elegir_alias(
    ind: Ind,
    num: dict[Clave, dict[str, dict[int, list[float]]]],
    txt: dict[Clave, dict[str, str]],
    anio_corte: int,
) -> Clave | None:
    """La primera pareja del catálogo que exista en los datos cargados (§4.2).

    Para los indicadores numéricos "existir" significa tener al menos un dato
    dentro del año de corte; si no, se prueba el alias siguiente.
    """
    for alias in ind.alias:
        clave: Clave = (alias[0], alias[1])
        if ind.tipo == "TXT":
            if txt.get(clave):
                return clave
            continue
        por_entidad = num.get(clave)
        if not por_entidad:
            continue
        if any(anio <= anio_corte for por_anio in por_entidad.values() for anio in por_anio):
            return clave
    return None


def resolver(
    filas: list[Fila],
    catalogo: list[Ind] = CATALOGO,
    anio_corte: int | None = None,
    entidades: list[str] | None = None,
    departamento: str = "",
) -> Resultado:
    """Matriz entidad × indicador con el dato más reciente sin pasar del corte."""
    if anio_corte is None:
        from datetime import date

        anio_corte = date.today().year

    if entidades is None:
        entidades = []
        for f in filas:
            if f.entidad not in entidades:
                entidades.append(f.entidad)
    if not departamento:
        deps: list[str] = []
        for f in filas:
            if f.departamento and f.departamento not in deps:
                deps.append(f.departamento)
        departamento = ", ".join(deps)

    num, txt, fuentes, _unidades = _indexar(filas)
    res = Resultado(entidades=list(entidades), departamento=departamento)

    for ind in catalogo:
        res.etiquetas[ind.id] = ind.etiqueta
        res.unidades[ind.id] = ind.unidad
        res.decimales[ind.id] = ind.decimales

        clave = _elegir_alias(ind, num, txt, anio_corte)
        if clave is None:
            res.valores[ind.id] = {e: None for e in entidades}
            res.anios[ind.id] = None
            res.anios_entidad[ind.id] = {e: None for e in entidades}
            res.faltantes.append(ind.id)
            log.info("%s: no disponible (ningún alias presente en los datos)", ind.id)
            continue

        res.alias_usado[ind.id] = clave
        res.fuentes[ind.id] = fuentes.get(clave, "")
        if (clave[0], clave[1]) != (ind.alias[0][0], ind.alias[0][1]):
            log.info("%s: se usó el alias '%s' (%s)", ind.id, clave[1], clave[0])

        if ind.tipo == "TXT":
            por_entidad_txt = txt.get(clave, {})
            res.valores[ind.id] = {e: por_entidad_txt.get(e) for e in entidades}
            res.anios[ind.id] = None
            res.anios_entidad[ind.id] = {e: None for e in entidades}
            if not any(res.valores[ind.id].values()):
                res.faltantes.append(ind.id)
            continue

        series = _series_de(num[clave])
        res.series[ind.id] = series

        valores: dict[str, float | str | None] = {}
        anios_e: dict[str, int | None] = {}
        for e in entidades:
            serie = series.get(e, {})
            validos = [a for a in serie if a <= anio_corte]
            if validos:
                anio = max(validos)
                valores[e] = serie[anio]
                anios_e[e] = anio
            else:
                valores[e] = None
                anios_e[e] = None
        res.valores[ind.id] = valores
        res.anios_entidad[ind.id] = anios_e
        usados = [a for a in anios_e.values() if a is not None]
        res.anios[ind.id] = max(usados) if usados else None
        if not usados:
            res.faltantes.append(ind.id)
            log.info("%s: sin datos dentro del año de corte %d", ind.id, anio_corte)

    return res


def _formato_es(valor: float, decimales: int) -> str:
    """Formato colombiano: punto de miles, coma decimal."""
    txt = f"{valor:,.{decimales}f}"
    return txt.replace(",", "\x00").replace(".", ",").replace("\x00", ".")


def tabla_texto(res: Resultado, ids: list[str] | None = None) -> str:
    """La matriz resuelta como tabla de consola (para --verboso)."""
    ids = ids or list(res.valores)
    ancho_id = max([len(i) for i in ids] + [10])
    ancho_e = max([len(e) for e in res.entidades] + [12])
    cab = f"{'INDICADOR':<{ancho_id}}  {'AÑO':>5}  " + "  ".join(
        f"{e:>{ancho_e}}" for e in res.entidades
    )
    lineas = [cab, "-" * len(cab)]
    for i in ids:
        anio = res.anios.get(i)
        celdas = []
        for e in res.entidades:
            v = res.valor(i, e)
            if v is None:
                celdas.append(f"{'—':>{ancho_e}}")
            elif isinstance(v, str):
                celdas.append(f"{v[:ancho_e]:>{ancho_e}}")
            else:
                celdas.append(f"{_formato_es(v, res.decimales.get(i, 2)):>{ancho_e}}")
        etiqueta_anio = str(anio) if anio else "—"
        lineas.append(f"{i:<{ancho_id}}  {etiqueta_anio:>5}  " + "  ".join(celdas))
    return "\n".join(lineas)
