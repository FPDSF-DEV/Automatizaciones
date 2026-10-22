"""Gráficas en PNG y SVG.

Reglas que se respetan en todo el módulo:
  - Un solo eje de valores por gráfica. Nunca dos escalas.
  - Los colores se asignan en orden fijo: la serie 1 siempre es azul.
  - Leyenda solo cuando hay dos o más series; con una, el título la nombra.
  - Título y leyenda siempre centrados respecto al área de dibujo.
  - Todos los puntos llevan su etiqueta de datos.
  - Rejilla y ejes discretos; la línea de datos es lo único con peso.
"""
from __future__ import annotations

from pathlib import Path
import textwrap

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter, MaxNLocator

from .config import DPI, PALETA, REJILLA, SUPERFICIE, TINTA, TINTA_SUAVE
from .indicadores import Indicador

plt.rcParams.update(
    {
        "font.family": "DejaVu Sans",
        "font.size": 10,
        "axes.titlesize": 13,
        "axes.titleweight": "bold",
        "axes.titlecolor": TINTA,
        "axes.labelsize": 9.5,
        "axes.labelcolor": TINTA_SUAVE,
        "axes.edgecolor": REJILLA,
        "axes.facecolor": SUPERFICIE,
        "figure.facecolor": SUPERFICIE,
        "xtick.color": TINTA_SUAVE,
        "ytick.color": TINTA_SUAVE,
        "xtick.labelsize": 9,
        "ytick.labelsize": 9,
        "legend.frameon": False,
        "legend.fontsize": 9,
        "savefig.bbox": "tight",
    }
)


def _formateador(porcentaje: bool, miles: bool):
    if porcentaje:
        return FuncFormatter(lambda v, _: f"{v:.0%}")
    if miles:
        return FuncFormatter(lambda v, _: f"{v:,.0f}".replace(",", "."))
    return FuncFormatter(lambda v, _: f"{v:,.2f}".replace(",", "@").replace(".", ",").replace("@", "."))


def _texto_valor(v, porcentaje=False, miles=False) -> str:
    """Un valor tal como se rotula sobre el punto o la barra."""
    if porcentaje:
        return f"{v:.1%}".replace(".", ",")
    if miles:
        return f"{v:,.0f}".replace(",", ".")
    return f"{v:,.2f}".replace(",", "@").replace(".", ",").replace("@", ".")


def _titulo(ax, texto: str) -> None:
    """Título centrado; si es largo se parte en líneas para que no ensanche
    la figura y descentre el área de dibujo."""
    ax.set_title(textwrap.fill(texto, width=46), loc="center", pad=14)


def _limpiar(ax, porcentaje=False, miles=False):
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_visible(False)
    ax.spines["bottom"].set_color(REJILLA)
    ax.grid(axis="y", color=REJILLA, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.yaxis.set_major_formatter(_formateador(porcentaje, miles))
    ax.xaxis.set_major_locator(MaxNLocator(integer=True))


def _rotular_barras(ax, contenedor, valores, dentro: bool, color_serie=None) -> None:
    """Etiqueta cada barra.

    En las apiladas la etiqueta va dentro del segmento; los segmentos
    demasiado bajos para contenerla se rotulan al costado, en el color de
    la serie, para que sigan siendo legibles.
    """
    if not dentro:
        ax.bar_label(
            contenedor, labels=[_texto_valor(v, miles=True) if v else "" for v in valores],
            label_type="edge", padding=3, fontsize=8, fontweight="bold",
            color=TINTA, zorder=4,
        )
        return

    alto_minimo = 0.07 * (ax.get_ylim()[1] - ax.get_ylim()[0])
    etiquetas_dentro = []
    for barra, valor in zip(contenedor, valores):
        if not valor:
            etiquetas_dentro.append("")
            continue
        if barra.get_height() >= alto_minimo:
            etiquetas_dentro.append(_texto_valor(valor, miles=True))
            continue
        etiquetas_dentro.append("")
        ax.annotate(
            _texto_valor(valor, miles=True),
            (barra.get_x() + barra.get_width(), barra.get_y() + barra.get_height() / 2),
            textcoords="offset points", xytext=(5, 0), ha="left", va="center",
            fontsize=8, fontweight="bold", color=color_serie or TINTA,
            annotation_clip=False, zorder=4,
        )
    ax.bar_label(
        contenedor, labels=etiquetas_dentro, label_type="center", padding=0,
        fontsize=8, fontweight="bold", color=SUPERFICIE, zorder=4,
    )


def _guardar(fig, destino: Path, nombre: str) -> dict[str, Path]:
    destino.mkdir(parents=True, exist_ok=True)
    rutas = {}
    for ext in ("png", "svg"):
        ruta = destino / f"{nombre}.{ext}"
        fig.savefig(ruta, dpi=DPI if ext == "png" else None, format=ext)
        rutas[ext] = ruta
    plt.close(fig)
    return rutas


def linea(tabla, columna, titulo, eje_y, destino, nombre, porcentaje=False):
    """Serie única a lo largo de los años, con el último valor rotulado."""
    fig, ax = plt.subplots(figsize=(6.6, 3.6))
    serie = tabla[columna].dropna()
    ax.plot(
        serie.index, serie.values, color=PALETA[0], linewidth=2,
        marker="o", markersize=6, markerfacecolor=PALETA[0],
        markeredgecolor=SUPERFICIE, markeredgewidth=1.4, zorder=3,
    )
    for x, y in zip(serie.index, serie.values):
        ax.annotate(
            _texto_valor(y, porcentaje=porcentaje), (x, y),
            textcoords="offset points", xytext=(0, 11),
            ha="center", fontsize=8.5, fontweight="bold", color=TINTA, zorder=4,
        )
    _titulo(ax, titulo)
    ax.set_ylabel(eje_y)
    ax.set_xlabel("Año")
    ax.set_ylim(bottom=0, top=(max(serie.values) * 1.18 if len(serie) and max(serie.values) > 0 else None))
    _limpiar(ax, porcentaje=porcentaje)
    return _guardar(fig, destino, nombre)


def barras(tabla, columnas, titulo, eje_y, destino, nombre, apiladas=False):
    """Una o varias series de volumen por año."""
    fig, ax = plt.subplots(figsize=(6.6, 3.6))
    anios = list(tabla.index)
    n = len(columnas)
    pendientes = []  # el rotulado espera a que la escala final esté fijada
    if apiladas or n == 1:
        acumulado = [0.0] * len(anios)
        for i, col in enumerate(columnas):
            vals = tabla[col].fillna(0).values
            barras_col = ax.bar(
                anios, vals, bottom=acumulado, width=0.58,
                color=PALETA[i], edgecolor=SUPERFICIE, linewidth=1.2,
                label=col, zorder=3,
            )
            pendientes.append((barras_col, vals, n > 1, PALETA[i]))
            acumulado = [a + b for a, b in zip(acumulado, vals)]
    else:
        ancho = 0.72 / n
        for i, col in enumerate(columnas):
            desp = (i - (n - 1) / 2) * ancho
            vals = tabla[col].fillna(0).values
            barras_col = ax.bar(
                [a + desp for a in anios], vals, width=ancho,
                color=PALETA[i], edgecolor=SUPERFICIE, linewidth=1.0,
                label=col, zorder=3,
            )
            pendientes.append((barras_col, vals, False, PALETA[i]))
    ax.margins(y=0.16)
    ax.set_ylim(bottom=0)
    for contenedor, vals, dentro, color in pendientes:
        _rotular_barras(ax, contenedor, vals, dentro=dentro, color_serie=color)
    _titulo(ax, titulo)
    ax.set_ylabel(eje_y)
    ax.set_xlabel("Año")
    ax.set_xticks(anios)
    _limpiar(ax, miles=True)
    if n > 1:
        ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.22),
                  ncol=min(n, 3), alignment="center")
    return _guardar(fig, destino, nombre)


def comparativa(tablas, indicadores, titulo, eje_y, destino, nombre):
    """Varios indicadores de la misma unidad en una sola gráfica."""
    fig, ax = plt.subplots(figsize=(6.6, 3.6))
    tope = 0.0
    for i, ind in enumerate(indicadores):
        serie = tablas[ind.clave][ind.indicador].dropna()
        ax.plot(
            serie.index, serie.values, color=PALETA[i], linewidth=2,
            marker="o", markersize=6, markerfacecolor=PALETA[i],
            markeredgecolor=SUPERFICIE, markeredgewidth=1.4,
            label=ind.titulo, zorder=3,
        )
        # Series alternas rotulan debajo del punto para no pisarse entre sí.
        desp = (0, 11) if i % 2 == 0 else (0, -16)
        for x, y in zip(serie.index, serie.values):
            ax.annotate(
                _texto_valor(y), (x, y), textcoords="offset points", xytext=desp,
                ha="center", fontsize=8.5, fontweight="bold", color=PALETA[i], zorder=4,
            )
        if len(serie):
            tope = max(tope, float(max(serie.values)))
    _titulo(ax, titulo)
    ax.set_ylabel(eje_y)
    ax.set_xlabel("Año")
    ax.set_ylim(bottom=0, top=tope * 1.18 if tope > 0 else None)
    _limpiar(ax)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.22), ncol=2, alignment="center")
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
