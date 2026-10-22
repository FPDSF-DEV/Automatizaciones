"""Gráficas en PNG y SVG.

Se dibujan con el sistema de diseño de terridata (paleta, tipografía, maqueta,
formato numérico), el mismo de los módulos terridata y pss, para que todas las
gráficas del proyecto se vean iguales. Reglas que se respetan:
  - Un solo eje de valores por gráfica. Nunca dos escalas.
  - Los colores se asignan en orden fijo: la serie 1 siempre es azul.
  - Leyenda solo cuando hay dos o más series; con una, el título la nombra.
  - La unidad del eje va en el subtítulo, no como rótulo del eje.
  - Todos los puntos y barras llevan su cifra.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

from .config import RAIZ
from .indicadores import Indicador

sys.path.insert(0, str(RAIZ.parent / "terridata"))
from terridata import graficas as g  # noqa: E402
from terridata.estilo import CLARO, TAMANO_BASE  # noqa: E402

TEMA = CLARO
PIE = "Fuente: SIHO — Formularios anuales y reporte de contratación externa"


def _valor(v) -> float | None:
    return None if pd.isna(v) else float(v)


def _guardar(fig, destino: Path, nombre: str) -> dict[str, Path]:
    rutas = g.guardar(fig, destino / nombre, formatos=("png", "svg"))
    g.cerrar(fig)
    return {Path(r).suffix.lstrip("."): Path(r) for r in rutas}


def linea(tabla, columna, titulo, eje_y, destino, nombre, porcentaje=False):
    """Serie única a lo largo de los años, con la cifra en cada punto."""
    serie = tabla[columna].dropna()
    factor = 100 if porcentaje else 1
    puntos = {int(a): float(v) * factor for a, v in serie.items()}
    fig = g.lineas(
        [("", puntos)], TEMA, titulo,
        subtitulo=f"{eje_y} (%)" if porcentaje else eje_y,
        pie=PIE, decimales=1 if porcentaje else 2,
        tamano=TAMANO_BASE, etiquetas_puntos=True,
    )
    return _guardar(fig, destino, nombre)


def barras(tabla, columnas, titulo, eje_y, destino, nombre, apiladas=False):
    """Una o varias series de volumen por año."""
    anios = [str(a) for a in tabla.index]
    series = [(col, [_valor(v) for v in tabla[col]]) for col in columnas]
    if len(series) == 1:
        fig = g.columnas(anios, series[0][1], TEMA, titulo, eje_y, PIE, decimales=0)
    elif apiladas:
        fig = g.columnas_apiladas(anios, series, TEMA, titulo, eje_y, PIE, decimales=0)
    else:
        fig = g.columnas_agrupadas(anios, series, TEMA, titulo, eje_y, PIE, decimales=0)
    return _guardar(fig, destino, nombre)


def comparativa(tablas, indicadores, titulo, eje_y, destino, nombre):
    """Varios indicadores de la misma unidad en una sola gráfica."""
    series = [
        (ind.titulo, {int(a): float(v) for a, v in tablas[ind.clave][ind.indicador].dropna().items()})
        for ind in indicadores
    ]
    fig = g.lineas(series, TEMA, titulo, subtitulo=eje_y, pie=PIE, decimales=2,
                   tamano=TAMANO_BASE, etiquetas_puntos=True)
    return _guardar(fig, destino, nombre)


def generar(indicador: Indicador, tabla, destino: Path) -> dict[str, dict[str, Path]]:
    """Las dos gráficas de un indicador: volumen y resultado."""
    salidas = {}
    if indicador.volumen:
        salidas["volumen"] = barras(
            tabla, list(indicador.volumen),
            f"{indicador.titulo} — volumen", indicador.eje_y_volumen,
            destino, f"{indicador.clave}_volumen",
            apiladas=indicador.grafica_volumen == "barras_apiladas",
        )
    salidas["indicador"] = linea(
        tabla, indicador.indicador,
        f"{indicador.titulo} — {indicador.indicador.lower()}", indicador.eje_y,
        destino, f"{indicador.clave}_indicador", porcentaje=indicador.porcentaje,
    )
    return salidas
