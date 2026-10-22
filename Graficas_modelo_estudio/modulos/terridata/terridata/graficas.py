"""Primitivas de dibujo (§7 del PLAN). Siete formas, ninguna más.

Tres decisiones que atraviesan el módulo:

* **Maquetación explícita.** Nada de `tight_layout`: los márgenes se fijan en
  pulgadas y las figuras salen exactamente de 1600×900 (o del tamaño pedido).
  Como el tamaño de los ejes se conoce antes de dibujar, se puede convertir
  píxeles de diseño a unidades de datos sin renderizar primero — que es lo que
  permite barras de grosor exacto y esquinas de 4 px de verdad.
* **El hueco de 2 px es geometría, no borde.** Las barras adyacentes y los
  segmentos apilados se encogen 2 px; nunca se les pinta un contorno. La única
  excepción es la torta, donde un hueco no se puede recortar y el borde del color
  de la superficie *es* el hueco.
* **Todas las marcas llevan su cifra y ninguna etiqueta se recorta.** Se mide el
  texto con `TextPath` antes de dibujarlo: si no cabe acostado se gira toda la
  serie a vertical, y el rango del eje se calcula para dejarle el aire exacto.
"""

from __future__ import annotations

from dataclasses import dataclass

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
from matplotlib.patches import PathPatch
from matplotlib.path import Path as MPath
from matplotlib.textpath import TextPath

from .estilo import (
    DPI_SALIDA,
    TAMANO_BASE,
    TAMANO_LINEAS,
    TAMANO_PIRAMIDE,
    TAMANO_TORTA,
    Tema,
    aplicar_rcparams,
    familia_disponible,
    decimales_para,
    formateador_eje,
    formato_es,
    px,
)

# Márgenes de la maqueta, en pulgadas.
BORDE = 0.34
MARGEN_DER = 0.34
MARGEN_IZQ = 0.95
MARGEN_IZQ_RANKING = 1.70
ALTO_PIE = 0.34
SEPARACION_LEYENDA = 0.34


# --------------------------------------------------------------------------- texto


def _fuente() -> FontProperties:
    return FontProperties(family=familia_disponible())


def ancho_texto(texto: str, tamano_pt: float) -> float:
    """Ancho del texto en pulgadas, sin necesidad de renderizar la figura."""
    if not texto:
        return 0.0
    ruta = TextPath((0, 0), texto, size=tamano_pt, prop=_fuente())
    return ruta.get_extents().width / 72.0


def alto_texto(tamano_pt: float, lineas: int = 1) -> float:
    """Alto aproximado de un bloque de texto en pulgadas (interlínea 1,35)."""
    return lineas * tamano_pt * 1.35 / 72.0


def envolver(texto: str, ancho_disponible: float, tamano_pt: float, max_lineas: int = 3) -> list[str]:
    """Parte el texto en líneas que caben en `ancho_disponible` pulgadas."""
    if not texto:
        return []
    palabras = texto.split()
    lineas: list[str] = []
    actual = ""
    for palabra in palabras:
        tentativa = f"{actual} {palabra}".strip()
        if ancho_texto(tentativa, tamano_pt) <= ancho_disponible or not actual:
            actual = tentativa
        else:
            lineas.append(actual)
            actual = palabra
        if len(lineas) == max_lineas:
            break
    if actual and len(lineas) < max_lineas:
        lineas.append(actual)
    return lineas


def _preparar_categorias(nombres: list[str], ancho_slot: float, tamano_pt: float):
    """Decide cómo rotular el eje de categorías sin que las etiquetas se encimen.

    Devuelve (etiquetas, rotación, alto necesario en pulgadas). Primero intenta
    horizontal, luego en dos líneas y por último rotado 30°.
    """
    disponible = max(ancho_slot - px(6), 0.2)
    mas_ancho = max((ancho_texto(n, tamano_pt) for n in nombres), default=0.0)
    if mas_ancho <= disponible:
        return nombres, 0, alto_texto(tamano_pt) + px(8)

    en_dos = [envolver(n, disponible, tamano_pt, max_lineas=2) for n in nombres]
    if all(len(l) <= 2 for l in en_dos) and all(
        ancho_texto(linea, tamano_pt) <= disponible for l in en_dos for linea in l
    ):
        return ["\n".join(l) for l in en_dos], 0, alto_texto(tamano_pt, 2) + px(8)

    import math

    alto = mas_ancho * math.sin(math.radians(30)) + alto_texto(tamano_pt) + px(8)
    return nombres, 30, min(alto, 1.30)


def alto_de_leyenda(tema: Tema, n_series: int, columnas: int = 4) -> float:
    """Alto en pulgadas que hay que reservarle a la leyenda de arriba.

    Crece hacia arriba desde el borde de los ejes: si no se le reserva el alto de
    sus filas, una leyenda de dos filas se mete debajo del subtítulo.
    """
    if n_series < 2:
        return 0.0
    filas = -(-n_series // min(columnas, n_series))
    return alto_texto(tema.fuente_leyenda, filas) + px(14)


# --------------------------------------------------------------------------- lienzo


@dataclass
class Lienzo:
    fig: plt.Figure
    ax: plt.Axes
    tema: Tema
    ancho_ejes: float      # pulgadas
    alto_ejes: float       # pulgadas

    # Van en valor absoluto: un eje invertido (los rankings) devuelve límites al
    # revés, y un grosor negativo voltearía el orden de las series.
    def unidades_por_pulgada_x(self) -> float:
        x0, x1 = self.ax.get_xlim()
        return abs(x1 - x0) / self.ancho_ejes

    def unidades_por_pulgada_y(self) -> float:
        y0, y1 = self.ax.get_ylim()
        return abs(y1 - y0) / self.alto_ejes

    def a_datos_x(self, pulgadas: float) -> float:
        return pulgadas * self.unidades_por_pulgada_x()

    def a_datos_y(self, pulgadas: float) -> float:
        return pulgadas * self.unidades_por_pulgada_y()


def _dibujar_cabecera(fig, tema: Tema, titulo: str, subtitulo: str, ancho_util: float):
    """Título y subtítulo arriba a la izquierda. Devuelve el alto ocupado."""
    W, H = fig.get_size_inches()
    y = H - 0.26
    alto = 0.26

    for linea in envolver(titulo, ancho_util, tema.fuente_titulo, max_lineas=2):
        alto_linea = alto_texto(tema.fuente_titulo)
        y -= alto_linea
        fig.text(
            BORDE / W, y / H, linea,
            fontsize=tema.fuente_titulo, color=tema.texto_primario,
            va="baseline", ha="left", fontweight="semibold",
        )
        alto += alto_linea

    if subtitulo:
        for linea in envolver(subtitulo, ancho_util, tema.fuente_subtitulo, max_lineas=2):
            alto_linea = alto_texto(tema.fuente_subtitulo)
            y -= alto_linea
            fig.text(
                BORDE / W, y / H, linea,
                fontsize=tema.fuente_subtitulo, color=tema.texto_secundario,
                va="baseline", ha="left",
            )
            alto += alto_linea

    return alto + 0.18


def _dibujar_pie(fig, tema: Tema, pie: str, ancho_util: float) -> float:
    """Pie de fuente. Devuelve el alto ocupado en pulgadas."""
    if not pie:
        return ALTO_PIE
    W, H = fig.get_size_inches()
    lineas = envolver(pie, ancho_util, tema.fuente_pie, max_lineas=2)
    y = 0.18
    for linea in reversed(lineas):
        fig.text(
            BORDE / W, y / H, linea,
            fontsize=tema.fuente_pie, color=tema.texto_secundario,
            va="baseline", ha="left",
        )
        y += alto_texto(tema.fuente_pie)
    return max(y - 0.18 + 0.20, ALTO_PIE)


def crear_lienzo(
    tema: Tema,
    titulo: str,
    subtitulo: str = "",
    pie: str = "",
    tamano: tuple[float, float] = TAMANO_BASE,
    margen_izq: float = MARGEN_IZQ,
    margen_der: float = MARGEN_DER,
    alto_categorias: float = 0.0,
    alto_leyenda: float = 0.0,
) -> Lienzo:
    """Figura con maquetación explícita: cabecera, ejes y pie no se pisan nunca."""
    aplicar_rcparams(tema)
    W, H = tamano
    fig = plt.figure(figsize=tamano, dpi=DPI_SALIDA, facecolor=tema.superficie)

    ancho_util = W - BORDE - MARGEN_DER
    alto_cabecera = _dibujar_cabecera(fig, tema, titulo, subtitulo, ancho_util)
    alto_pie = _dibujar_pie(fig, tema, pie, ancho_util)

    abajo = alto_pie + alto_categorias
    arriba = alto_cabecera + alto_leyenda
    alto_ejes = max(H - abajo - arriba, 0.9)
    ancho_ejes = max(W - margen_izq - margen_der, 1.0)

    ax = fig.add_axes([margen_izq / W, abajo / H, ancho_ejes / W, alto_ejes / H])
    ax.set_facecolor(tema.superficie)
    for lado in ("top", "right"):
        ax.spines[lado].set_visible(False)
    for lado in ("left", "bottom"):
        ax.spines[lado].set_color(tema.rejilla)
        ax.spines[lado].set_linewidth(tema.grosor_rejilla)
    ax.tick_params(colors=tema.texto_secundario, labelsize=tema.fuente_eje,
                   length=0, pad=6)

    return Lienzo(fig=fig, ax=ax, tema=tema, ancho_ejes=ancho_ejes, alto_ejes=alto_ejes)


# --------------------------------------------------------------------------- marcas


def _ruta_redondeada(x0, y0, x1, y1, rx, ry, esquinas: str) -> MPath:
    """Rectángulo con dos esquinas redondeadas en el extremo del dato (§7.4).

    `esquinas` es 'arriba', 'abajo', 'derecha', 'izquierda' o 'ninguna'.
    """
    rx = max(rx, 0.0)
    ry = max(ry, 0.0)
    if esquinas in ("arriba", "abajo"):
        ry = min(ry, abs(y1 - y0))
        rx = min(rx, abs(x1 - x0) / 2)
    else:
        rx = min(rx, abs(x1 - x0))
        ry = min(ry, abs(y1 - y0) / 2)

    if esquinas == "ninguna" or rx <= 0 or ry <= 0:
        return MPath(
            [(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)],
            [MPath.MOVETO, MPath.LINETO, MPath.LINETO, MPath.LINETO, MPath.CLOSEPOLY],
        )

    v: list[tuple[float, float]] = []
    c: list[int] = []

    def mover(p):
        v.append(p)
        c.append(MPath.MOVETO)

    def linea(p):
        v.append(p)
        c.append(MPath.LINETO)

    def curva(ctrl, fin):
        v.extend([ctrl, fin])
        c.extend([MPath.CURVE3, MPath.CURVE3])

    if esquinas == "arriba":
        mover((x0, y0))
        linea((x0, y1 - ry))
        curva((x0, y1), (x0 + rx, y1))
        linea((x1 - rx, y1))
        curva((x1, y1), (x1, y1 - ry))
        linea((x1, y0))
    elif esquinas == "abajo":
        mover((x0, y1))
        linea((x0, y0 + ry))
        curva((x0, y0), (x0 + rx, y0))
        linea((x1 - rx, y0))
        curva((x1, y0), (x1, y0 + ry))
        linea((x1, y1))
    elif esquinas == "derecha":
        mover((x0, y0))
        linea((x1 - rx, y0))
        curva((x1, y0), (x1, y0 + ry))
        linea((x1, y1 - ry))
        curva((x1, y1), (x1 - rx, y1))
        linea((x0, y1))
    else:  # izquierda
        mover((x1, y0))
        linea((x0 + rx, y0))
        curva((x0, y0), (x0, y0 + ry))
        linea((x0, y1 - ry))
        curva((x0, y1), (x0 + rx, y1))
        linea((x1, y1))

    v.append(v[0])
    c.append(MPath.CLOSEPOLY)
    return MPath(v, c)


def dibujar_barra(lienzo: Lienzo, x0, y0, x1, y1, color, esquinas="arriba"):
    """Una marca de barra con el extremo del dato redondeado 4 px."""
    rx = lienzo.a_datos_x(lienzo.tema.radio_esquina)
    ry = lienzo.a_datos_y(lienzo.tema.radio_esquina)
    ruta = _ruta_redondeada(x0, y0, x1, y1, rx, ry, esquinas)
    parche = PathPatch(ruta, facecolor=color, edgecolor="none", linewidth=0, zorder=3)
    lienzo.ax.add_patch(parche)
    return parche


def _grosor_barra(lienzo: Lienzo, n_slots: int, n_series: int = 1) -> float:
    """Grosor en unidades de datos: nunca más de 24 px y con 2 px de aire entre barras."""
    tema = lienzo.tema
    slot_pulg = lienzo.ancho_ejes / max(n_slots, 1) / max(n_series, 1)
    grosor_pulg = min(tema.grosor_barra_max, max(slot_pulg - tema.hueco, px(2)))
    return lienzo.a_datos_x(grosor_pulg)


def _grosor_barra_horizontal(lienzo: Lienzo, n_slots: int, n_series: int = 1) -> float:
    tema = lienzo.tema
    slot_pulg = lienzo.alto_ejes / max(n_slots, 1) / max(n_series, 1)
    grosor_pulg = min(tema.grosor_barra_max, max(slot_pulg - tema.hueco, px(2)))
    return lienzo.a_datos_y(grosor_pulg)


# --------------------------------------------------------------------------- ejes


def ajustar_formato_eje(ax, eje: str = "y"):
    """Ticks con números redondos y los mismos decimales en todo el eje (§7.5).

    Se decide con los ticks ya calculados: si todos son enteros no llevan
    decimales, y si alguno los necesita, los llevan todos (12,5 · 10,0 · 7,5).
    """
    ticks = ax.get_yticks() if eje == "y" else ax.get_xticks()
    limites = ax.get_ylim() if eje == "y" else ax.get_xlim()
    visibles = [t for t in ticks if min(limites) - 1e-9 <= t <= max(limites) + 1e-9]
    decimales = 0
    for t in visibles:
        if abs(t - round(t)) > 1e-6:
            decimales = 1
            break
    formateador = formateador_eje(decimales)
    if eje == "y":
        ax.yaxis.set_major_formatter(formateador)
    else:
        ax.xaxis.set_major_formatter(formateador)


def _rejilla_horizontal(lienzo: Lienzo):
    lienzo.ax.grid(axis="y", color=lienzo.tema.rejilla,
                   linewidth=lienzo.tema.grosor_rejilla, linestyle="-", zorder=0)
    lienzo.ax.set_axisbelow(True)


def _rejilla_vertical(lienzo: Lienzo):
    lienzo.ax.grid(axis="x", color=lienzo.tema.rejilla,
                   linewidth=lienzo.tema.grosor_rejilla, linestyle="-", zorder=0)
    lienzo.ax.set_axisbelow(True)


def _limites_valor(valores: list[float], meta: float | None = None, holgura=0.16):
    """Rango del eje de valores con aire para las etiquetas (que van afuera)."""
    finitos = [v for v in valores if v is not None]
    if meta is not None:
        finitos = finitos + [meta]
    if not finitos:
        return 0.0, 1.0
    maximo = max(finitos)
    minimo = min(finitos)
    if maximo == minimo:
        maximo = maximo + abs(maximo) * 0.2 + 1.0
    span = maximo - minimo if maximo > 0 else abs(minimo)
    if minimo >= 0:
        return 0.0, maximo + span * holgura
    if maximo <= 0:
        return minimo - span * holgura, 0.0
    return minimo - span * holgura, maximo + span * holgura


def _orden_por_filas(handles, etiquetas, columnas: int):
    """Reordena para que la leyenda se lea de izquierda a derecha.

    matplotlib llena la leyenda por columnas: con seis series en cuatro columnas,
    la primera fila saldría 1·3·5·6 y el lector creería que ese es el orden de
    las barras. Transponiendo, el orden visual vuelve a ser el de las series.
    """
    n = len(etiquetas)
    if columnas <= 1 or n <= columnas:
        return handles, etiquetas
    filas = -(-n // columnas)
    orden = []
    for columna in range(columnas):
        for fila in range(filas):
            indice = fila * columnas + columna
            if indice < n:
                orden.append(indice)
    return [handles[i] for i in orden], [etiquetas[i] for i in orden]


def _leyenda(lienzo: Lienzo, handles, etiquetas):
    """Leyenda arriba, horizontal, sin marco (§7.5). Solo con 2+ series."""
    if len(etiquetas) < 2:
        return None
    tema = lienzo.tema
    columnas = min(len(etiquetas), 4)
    handles, etiquetas = _orden_por_filas(handles, etiquetas, columnas)
    leyenda = lienzo.ax.legend(
        handles, etiquetas,
        loc="lower left",
        bbox_to_anchor=(0.0, 1.0 + (px(10) / lienzo.alto_ejes)),
        ncol=columnas,
        frameon=False,
        fontsize=tema.fuente_leyenda,
        handlelength=0.9,
        handleheight=0.9,
        handletextpad=0.5,
        columnspacing=1.6,
        borderaxespad=0.0,
    )
    for texto in leyenda.get_texts():
        texto.set_color(tema.texto_primario)
    return leyenda


def _linea_meta(lienzo: Lienzo, valor: float, etiqueta: str, orientacion="horizontal"):
    """Línea de referencia (la meta del 95 % de vacunación). Nunca de color de serie."""
    tema = lienzo.tema
    ax = lienzo.ax
    if orientacion == "horizontal":
        ax.axhline(valor, color=tema.texto_secundario, linewidth=tema.grosor_rejilla,
                   linestyle="-", zorder=2)
        ax.text(ax.get_xlim()[1], valor, f" {etiqueta}", va="center", ha="left",
                fontsize=tema.fuente_pie, color=tema.texto_secundario, clip_on=False)
    else:
        ax.axvline(valor, color=tema.texto_secundario, linewidth=tema.grosor_rejilla,
                   linestyle="-", zorder=2)
        ax.text(valor, ax.get_ylim()[1], f"{etiqueta}", va="bottom", ha="center",
                fontsize=tema.fuente_pie, color=tema.texto_secundario, clip_on=False)


def _etiqueta_valor(lienzo: Lienzo, x, y, texto, va="bottom", ha="center", rotacion=0):
    """Valor en la punta de la marca, siempre por fuera: nunca se recorta."""
    lienzo.ax.text(
        x, y, texto, va=va, ha=ha, rotation=rotacion,
        fontsize=lienzo.tema.fuente_valor, color=lienzo.tema.texto_primario,
        zorder=4, clip_on=False,
    )


def plan_etiquetas(tema: Tema, textos: list[str], ancho_disponible: float,
                   fuente: float | None = None):
    """Decide cómo rotular los valores y cuánto espacio hay que reservarles.

    Todas las barras llevan su cifra. Si el número más largo no cabe acostado en
    el ancho que tiene la barra, **todas** las etiquetas van en vertical: mezclar
    acostadas y giradas en la misma gráfica se ve desordenado. Devuelve
    `(rotación, espacio en pulgadas)` para que el eje deje ese aire y la etiqueta
    nunca quede por fuera del lienzo.
    """
    tamano = fuente or tema.fuente_valor
    mas_ancho = max((ancho_texto(t, tamano) for t in textos), default=0.0)
    if mas_ancho <= max(ancho_disponible - px(4), 0.0):
        return 0, alto_texto(tamano) + px(6)
    return 90, mas_ancho + px(10)


def _etiqueta_segmento(lienzo: Lienzo, x, base, valor, texto, ancho_barra: float):
    """Cifra dentro de un segmento apilado, acostada o girada según lo que quepa.

    Dentro de la marca el texto va del color de la superficie. Si el segmento no
    da ni acostado ni girado, la cifra se omite aquí: está en la tabla del
    dashboard y forzarla dejaría números encimados sobre la barra.
    """
    tema = lienzo.tema
    alto_segmento = abs(valor) / lienzo.unidades_por_pulgada_y()

    # Se prueba con la tipografía de valores y, si no cabe, con la del pie antes
    # de rendirse: así quedan rotulados más segmentos sin apretar el dibujo.
    for fuente in (tema.fuente_valor, tema.fuente_pie):
        ancho = ancho_texto(texto, fuente)
        alto = alto_texto(fuente)
        if ancho + px(6) <= ancho_barra and alto + px(4) <= alto_segmento:
            giro = 0
        elif alto + px(4) <= ancho_barra and ancho + px(6) <= alto_segmento:
            giro = 90
        else:
            continue
        lienzo.ax.text(
            x, base + valor / 2, texto, va="center", ha="center", rotation=giro,
            fontsize=fuente, color=tema.superficie, zorder=5,
        )
        return


def _limites_con_espacio(valores, alto_ejes: float, espacio: float,
                         meta: float | None = None):
    """Rango del eje que deja libres `espacio` pulgadas para las etiquetas.

    Se resuelve en cerrado: si el tope debe quedar a `espacio` pulgadas por
    encima del dato mayor, entonces `tope = maximo / (1 - espacio/alto)`.
    """
    finitos = [v for v in valores if v is not None]
    if meta is not None:
        finitos = finitos + [meta]
    if not finitos:
        return 0.0, 1.0

    fraccion = min(espacio / alto_ejes, 0.45) if alto_ejes > 0 else 0.16
    factor = 1.0 / (1.0 - fraccion)
    maximo, minimo = max(finitos), min(finitos)
    if maximo == minimo:
        maximo = maximo + abs(maximo) * 0.2 + 1.0

    if minimo >= 0:
        return 0.0, maximo * factor if maximo > 0 else 1.0
    if maximo <= 0:
        return minimo * factor, 0.0
    return minimo * factor, maximo * factor


# --------------------------------------------------------------------------- formas


def columnas(
    categorias: list[str],
    valores: list[float | None],
    tema: Tema,
    titulo: str,
    subtitulo: str = "",
    pie: str = "",
    decimales: int | None = None,
    meta: tuple[float, str] | None = None,
    tamano: tuple[float, float] = TAMANO_BASE,
) -> plt.Figure:
    """Magnitud comparada entre entidades, una sola serie: todas las barras del slot 1."""
    finitos = [v for v in valores if v is not None]
    dec = decimales_para(finitos) if decimales is None else decimales

    ancho_slot = (TAMANO_BASE[0] if tamano is None else tamano[0]) - MARGEN_IZQ - MARGEN_DER
    ancho_slot = ancho_slot / max(len(categorias), 1)
    etiquetas, rotacion, alto_cat = _preparar_categorias(categorias, ancho_slot, tema.fuente_eje)

    lienzo = crear_lienzo(tema, titulo, subtitulo, pie, tamano,
                          alto_categorias=alto_cat)
    ax = lienzo.ax
    ax.set_xlim(-0.5, len(categorias) - 0.5)
    _rejilla_horizontal(lienzo)
    ax.set_xticks(range(len(categorias)))
    ax.set_xticklabels(etiquetas, rotation=rotacion,
                       ha="right" if rotacion else "center", rotation_mode="anchor")

    # El grosor depende solo del eje X, así que se puede decidir cómo van las
    # etiquetas antes de fijar el rango vertical que las tiene que albergar.
    grosor = _grosor_barra(lienzo, len(categorias))
    textos = [formato_es(v, dec) for v in valores if v is not None]
    # Con una sola serie las barras vecinas están lejos: lo que limita la etiqueta
    # es el paso entre categorías, no el grosor de la barra.
    giro, espacio = plan_etiquetas(tema, textos,
                                   lienzo.ancho_ejes / max(len(categorias), 1))
    ax.set_ylim(*_limites_con_espacio(valores, lienzo.alto_ejes, espacio,
                                      meta[0] if meta else None))
    ajustar_formato_eje(ax, "y")

    color = tema.color(1)
    holgura_y = lienzo.a_datos_y(px(6))

    for i, valor in enumerate(valores):
        if valor is None:
            continue
        x0, x1 = i - grosor / 2, i + grosor / 2
        esquinas = "arriba" if valor >= 0 else "abajo"
        dibujar_barra(lienzo, x0, 0.0, x1, valor, color, esquinas)
        texto = formato_es(valor, dec)
        if valor >= 0:
            _etiqueta_valor(lienzo, i, valor + holgura_y, texto, va="bottom", rotacion=giro)
        else:
            _etiqueta_valor(lienzo, i, valor - holgura_y, texto, va="top", rotacion=giro)

    if min([v for v in valores if v is not None], default=0) < 0:
        ax.axhline(0, color=tema.rejilla, linewidth=tema.grosor_rejilla, zorder=2)
    if meta:
        _linea_meta(lienzo, meta[0], meta[1])

    return lienzo.fig


def columnas_agrupadas(
    categorias: list[str],
    series: list[tuple[str, list[float | None]]],
    tema: Tema,
    titulo: str,
    subtitulo: str = "",
    pie: str = "",
    decimales: int | None = None,
    tamano: tuple[float, float] = TAMANO_BASE,
) -> plt.Figure:
    """De 2 a 6 series de la misma unidad, con la cifra sobre cada barra."""
    todos = [v for _, vs in series for v in vs if v is not None]
    dec = decimales_para(todos) if decimales is None else decimales

    ancho_slot = (tamano[0] - MARGEN_IZQ - MARGEN_DER) / max(len(categorias), 1)
    etiquetas, rotacion, alto_cat = _preparar_categorias(categorias, ancho_slot, tema.fuente_eje)

    lienzo = crear_lienzo(tema, titulo, subtitulo, pie, tamano,
                          alto_categorias=alto_cat,
                          alto_leyenda=alto_de_leyenda(tema, len(series)))
    ax = lienzo.ax
    ax.set_xlim(-0.5, len(categorias) - 0.5)
    _rejilla_horizontal(lienzo)
    ax.set_xticks(range(len(categorias)))
    ax.set_xticklabels(etiquetas, rotation=rotacion,
                       ha="right" if rotacion else "center", rotation_mode="anchor")

    n = len(series)
    grosor = _grosor_barra(lienzo, len(categorias), n)
    hueco = lienzo.a_datos_x(tema.hueco)
    paso = grosor + hueco
    ancho_grupo = paso * n - hueco

    # Cada barra lleva su cifra: se decide el giro con el ancho de barra y se le
    # reserva al eje el aire que necesita.
    textos = [formato_es(v, dec) for v in todos]
    giro, espacio = plan_etiquetas(tema, textos, paso / lienzo.unidades_por_pulgada_x())
    ax.set_ylim(*_limites_con_espacio(todos, lienzo.alto_ejes, espacio))
    ajustar_formato_eje(ax, "y")

    minimo = min(todos) if todos else 0
    handles = []
    holgura_y = lienzo.a_datos_y(px(5))

    for s, (nombre, valores) in enumerate(series):
        color = tema.color(s + 1)
        handles.append(plt.Rectangle((0, 0), 1, 1, facecolor=color, edgecolor="none"))
        for i, valor in enumerate(valores):
            if valor is None:
                continue
            centro = i - ancho_grupo / 2 + paso * s + grosor / 2
            dibujar_barra(lienzo, centro - grosor / 2, 0.0, centro + grosor / 2, valor,
                          color, "arriba" if valor >= 0 else "abajo")
            texto = formato_es(valor, dec)
            if valor >= 0:
                _etiqueta_valor(lienzo, centro, valor + holgura_y, texto,
                                va="bottom", rotacion=giro)
            else:
                _etiqueta_valor(lienzo, centro, valor - holgura_y, texto,
                                va="top", rotacion=giro)

    if minimo < 0:
        ax.axhline(0, color=tema.rejilla, linewidth=tema.grosor_rejilla, zorder=2)
    _leyenda(lienzo, handles, [n for n, _ in series])
    return lienzo.fig


def columnas_apiladas(
    categorias: list[str],
    series: list[tuple[str, list[float | None]]],
    tema: Tema,
    titulo: str,
    subtitulo: str = "",
    pie: str = "",
    decimales: int | None = None,
    tamano: tuple[float, float] = TAMANO_BASE,
) -> plt.Figure:
    """Composición de un total: segmentos con hueco de 2 px y el extremo redondeado."""
    totales = []
    for i in range(len(categorias)):
        partes = [vs[i] for _, vs in series if vs[i] is not None]
        totales.append(sum(partes) if partes else None)
    dec = decimales_para([t for t in totales if t is not None]) if decimales is None else decimales

    ancho_slot = (tamano[0] - MARGEN_IZQ - MARGEN_DER) / max(len(categorias), 1)
    etiquetas, rotacion, alto_cat = _preparar_categorias(categorias, ancho_slot, tema.fuente_eje)

    lienzo = crear_lienzo(tema, titulo, subtitulo, pie, tamano,
                          alto_categorias=alto_cat,
                          alto_leyenda=alto_de_leyenda(tema, len(series)))
    ax = lienzo.ax
    ax.set_xlim(-0.5, len(categorias) - 0.5)
    _rejilla_horizontal(lienzo)
    ax.set_xticks(range(len(categorias)))
    ax.set_xticklabels(etiquetas, rotation=rotacion,
                       ha="right" if rotacion else "center", rotation_mode="anchor")

    grosor = _grosor_barra(lienzo, len(categorias))
    con_total = [t for t in totales if t is not None]
    textos_total = [formato_es(t, dec) for t in con_total]
    giro, espacio = plan_etiquetas(tema, textos_total,
                                   lienzo.ancho_ejes / max(len(categorias), 1))
    ax.set_ylim(*_limites_con_espacio(con_total, lienzo.alto_ejes, espacio))
    ajustar_formato_eje(ax, "y")

    hueco = lienzo.a_datos_y(tema.hueco)
    handles = [
        plt.Rectangle((0, 0), 1, 1, facecolor=tema.color(s + 1), edgecolor="none")
        for s in range(len(series))
    ]
    holgura_y = lienzo.a_datos_y(px(6))
    ancho_barra = grosor / lienzo.unidades_por_pulgada_x()

    for i in range(len(categorias)):
        base = 0.0
        presentes = [(s, vs[i]) for s, (_, vs) in enumerate(series) if vs[i] is not None]
        for orden, (s, valor) in enumerate(presentes):
            color = tema.color(s + 1)
            es_ultimo = orden == len(presentes) - 1
            tope = base + valor
            # El hueco se recorta del segmento: es un hueco, no un borde.
            tope_dibujo = tope if es_ultimo else max(tope - hueco, base)
            dibujar_barra(lienzo, i - grosor / 2, base, i + grosor / 2, tope_dibujo,
                          color, "arriba" if es_ultimo else "ninguna")
            _etiqueta_segmento(lienzo, i, base, valor, formato_es(valor, dec), ancho_barra)
            base = tope
        if totales[i] is not None:
            _etiqueta_valor(lienzo, i, totales[i] + holgura_y,
                            formato_es(totales[i], dec), va="bottom", rotacion=giro)

    _leyenda(lienzo, handles, [n for n, _ in series])
    return lienzo.fig


def barras_ranking(
    categorias: list[str],
    valores: list[float | None],
    tema: Tema,
    titulo: str,
    subtitulo: str = "",
    pie: str = "",
    decimales: int | None = None,
    meta: tuple[float, str] | None = None,
    tamano: tuple[float, float] = TAMANO_BASE,
    orden: str = "asc",
    etiquetas_valor: dict[str, str] | None = None,
) -> plt.Figure:
    """Ranking horizontal, leído de arriba hacia abajo.

    `orden`: 'asc' pone el menor arriba, 'desc' el mayor arriba y 'dado' respeta
    el orden recibido (para dos o tres categorías fijas, donde ordenar confunde).
    Un solo color sólido: el orden ya comunica la magnitud, así que no va rampa (§7.2).
    """
    pares = [(c, v) for c, v in zip(categorias, valores) if v is not None]
    if orden == "asc":
        pares.sort(key=lambda p: p[1])
    elif orden == "desc":
        pares.sort(key=lambda p: p[1], reverse=True)
    nombres = [p[0] for p in pares]
    vals = [p[1] for p in pares]
    dec = decimales_para(vals) if decimales is None else decimales

    margen_izq = max(
        MARGEN_IZQ,
        min(MARGEN_IZQ_RANKING,
            max((ancho_texto(n, tema.fuente_eje) for n in nombres), default=0.6) + 0.28),
    )
    lienzo = crear_lienzo(tema, titulo, subtitulo, pie, tamano,
                          margen_izq=margen_izq,
                          alto_categorias=alto_texto(tema.fuente_eje) + px(10))
    ax = lienzo.ax
    ax.set_ylim(-0.5, max(len(nombres) - 0.5, 0.5))
    # El eje reserva el ancho de la etiqueta más larga: así todas las cifras
    # caben al lado de su barra sin salirse del lienzo.
    textos = [(etiquetas_valor or {}).get(n) or formato_es(v, dec)
              for n, v in zip(nombres, vals)]
    espacio = max((ancho_texto(x, tema.fuente_valor) for x in textos), default=0.0) + px(12)
    ax.set_xlim(*_limites_con_espacio(vals, lienzo.ancho_ejes, espacio,
                                      meta[0] if meta else None))
    ax.invert_yaxis()   # el menor arriba: se lee de menor a mayor hacia abajo
    _rejilla_vertical(lienzo)
    ajustar_formato_eje(ax, "x")
    ax.set_yticks(range(len(nombres)))
    ax.set_yticklabels(nombres)

    grosor = _grosor_barra_horizontal(lienzo, max(len(nombres), 1))
    color = tema.color(1)
    holgura_x = lienzo.a_datos_x(px(6))

    for i, valor in enumerate(vals):
        dibujar_barra(lienzo, 0.0, i - grosor / 2, valor, i + grosor / 2, color,
                      "derecha" if valor >= 0 else "izquierda")
        texto = (etiquetas_valor or {}).get(nombres[i]) or formato_es(valor, dec)
        if valor >= 0:
            _etiqueta_valor(lienzo, valor + holgura_x, i, texto, va="center", ha="left")
        else:
            _etiqueta_valor(lienzo, valor - holgura_x, i, texto, va="center", ha="right")

    if min(vals, default=0) < 0:
        ax.axvline(0, color=tema.rejilla, linewidth=tema.grosor_rejilla, zorder=2)
    if meta:
        _linea_meta(lienzo, meta[0], meta[1], orientacion="vertical")
    return lienzo.fig


def torta(
    categorias: list[str],
    valores: list[float | None],
    tema: Tema,
    titulo: str,
    subtitulo: str = "",
    pie: str = "",
    decimales: int | None = None,
    tamano: tuple[float, float] = TAMANO_TORTA,
    dona: bool = False,
    centro: str = "",
) -> plt.Figure:
    """Composición de un total. Máximo 7 porciones; el resto se agrupa en 'Otros' (§7.6).

    `dona=True` deja el centro hueco; `centro` escribe un rótulo dentro del hueco.
    """
    pares = [(c, v) for c, v in zip(categorias, valores) if v is not None and v > 0]
    pares.sort(key=lambda p: p[1], reverse=True)
    total = sum(v for _, v in pares)
    dec = decimales_para([v for _, v in pares]) if decimales is None else decimales

    # Solo con más de 7 entidades se agrupa lo que esté por debajo del 2 %.
    if len(pares) > 7:
        grandes = [(c, v) for c, v in pares if v / total * 100 >= 2.0]
        resto = [(c, v) for c, v in pares if v / total * 100 < 2.0]
        if len(grandes) > 7:
            resto = resto + grandes[6:]
            grandes = grandes[:6]
        pares = grandes + ([("Otros", sum(v for _, v in resto))] if resto else [])

    nombres = [c for c, _ in pares]
    vals = [v for _, v in pares]

    aplicar_rcparams(tema)
    W, H = tamano
    fig = plt.figure(figsize=tamano, dpi=DPI_SALIDA, facecolor=tema.superficie)
    ancho_util = W - BORDE - MARGEN_DER
    alto_cabecera = _dibujar_cabecera(fig, tema, titulo, subtitulo, ancho_util)
    alto_pie = _dibujar_pie(fig, tema, pie, ancho_util)

    # La leyenda va debajo: con siete porciones, las etiquetas radiales se
    # encaramarían unas sobre otras y el PLAN prohíbe justamente eso.
    columnas_leyenda = 2 if len(vals) > 4 else max(len(vals), 1)
    filas_leyenda = -(-max(len(vals), 1) // columnas_leyenda)
    alto_leyenda = filas_leyenda * alto_texto(tema.fuente_leyenda) + px(14)

    alto_ejes = max(H - alto_pie - alto_leyenda - alto_cabecera, 1.0)
    ax = fig.add_axes([0.04, (alto_pie + alto_leyenda) / H, 0.92, alto_ejes / H])
    ax.set_facecolor(tema.superficie)
    ax.set_axis_off()

    if not vals:
        ax.text(0.5, 0.5, "Sin datos", ha="center", va="center",
                color=tema.texto_secundario, fontsize=tema.fuente_subtitulo)
        return fig

    colores = [tema.color(i + 1) for i in range(len(vals))]
    cunas, _ = ax.pie(
        vals,
        colors=colores,
        startangle=90,
        counterclock=False,
        radius=1.0,
        # En una torta el hueco no se puede recortar: el borde del color de la
        # superficie ES el hueco de 2 px (§7.4).
        wedgeprops={
            "linewidth": tema.hueco * 72,
            "edgecolor": tema.superficie,
            **({"width": 0.42} if dona else {}),
        },
    )
    if dona and centro:
        for indice, linea in enumerate(centro.split("\n")):
            ax.text(0, 0.13 - indice * 0.22, linea, ha="center", va="center",
                    fontsize=tema.fuente_subtitulo if indice == 0 else tema.fuente_pie,
                    color=tema.texto_primario if indice == 0 else tema.texto_secundario,
                    fontweight="semibold" if indice == 0 else "normal")
    # Caja cuadrada centrada: el diámetro lo fija el alto disponible.
    ax.set_xlim(-1.05, 1.05)
    ax.set_ylim(-1.05, 1.05)
    ax.set_aspect("equal", adjustable="box", anchor="C")

    import math

    # El diámetro real en pulgadas manda para decidir si el porcentaje cabe dentro.
    radio_pulg = min(alto_ejes, ancho_util) / 2.1
    for cuna, valor in zip(cunas, vals):
        porcentaje = valor / total * 100
        texto = f"{formato_es(porcentaje, 1)} %"
        angulo_span = math.radians(abs(cuna.theta2 - cuna.theta1))
        radio_etiqueta = 0.79 if dona else 0.62
        cuerda = 2 * radio_etiqueta * radio_pulg * math.sin(min(angulo_span, math.pi) / 2)
        if ancho_texto(texto, tema.fuente_valor) > cuerda - px(8):
            continue   # no cabe: el porcentaje queda solo en la leyenda
        angulo = math.radians((cuna.theta1 + cuna.theta2) / 2)
        ax.text(
            math.cos(angulo) * radio_etiqueta, math.sin(angulo) * radio_etiqueta, texto,
            ha="center", va="center",
            fontsize=tema.fuente_valor, color=tema.superficie, zorder=5,
        )

    handles = [
        plt.Rectangle((0, 0), 1, 1, facecolor=c, edgecolor="none") for c in colores
    ]
    etiquetas = [
        f"{nombre} · {formato_es(v / total * 100, 1)} %" for nombre, v in zip(nombres, vals)
    ]
    leyenda = fig.legend(
        handles, etiquetas,
        loc="lower center",
        bbox_to_anchor=(0.5, (alto_pie + px(4)) / H),
        ncol=columnas_leyenda,
        frameon=False,
        fontsize=tema.fuente_leyenda,
        handlelength=0.9,
        handleheight=0.9,
        handletextpad=0.5,
        columnspacing=1.8,
    )
    for t in leyenda.get_texts():
        t.set_color(tema.texto_primario)
    return fig


def lineas(
    series: list[tuple[str, dict[int, float]]],
    tema: Tema,
    titulo: str,
    subtitulo: str = "",
    pie: str = "",
    decimales: int | None = None,
    tamano: tuple[float, float] = TAMANO_LINEAS,
    max_anios: int = 10,
) -> plt.Figure:
    """Evolución en el tiempo. El eje X se ancla al último año con dato, no al corte."""
    anios_todos = sorted({a for _, s in series for a in s})
    if not anios_todos:
        anios_todos = [0]
    ultimo = max(anios_todos)
    anios = [a for a in anios_todos if a > ultimo - max_anios]

    valores = [v for _, s in series for a, v in s.items() if a in anios]
    dec = decimales_para(valores) if decimales is None else decimales

    # Con etiqueta directa hay que reservarle el ancho: si no cabe, se recorta,
    # y recortar está prohibido.
    con_etiqueta_directa = len(series) <= 4
    margen_der = MARGEN_DER
    if con_etiqueta_directa:
        mas_ancha = max((ancho_texto(n, tema.fuente_eje) for n, _ in series), default=0.0)
        margen_der = MARGEN_DER + mas_ancha + px(12)

    lienzo = crear_lienzo(tema, titulo, subtitulo, pie, tamano,
                          margen_der=margen_der,
                          alto_categorias=0.34,
                          alto_leyenda=alto_de_leyenda(tema, len(series)))
    ax = lienzo.ax
    ax.set_xlim(min(anios) - 0.35, max(anios) + 0.35)
    ax.set_ylim(*_limites_valor(valores, holgura=0.14))
    _rejilla_horizontal(lienzo)
    ajustar_formato_eje(ax, "y")
    ax.set_xticks(anios)
    ax.set_xticklabels([str(a) for a in anios])

    handles = []
    etiquetas = []
    finales: list[tuple[float, float, str]] = []
    for s, (nombre, serie) in enumerate(series):
        color = tema.color(s + 1)
        puntos = [(a, serie[a]) for a in anios if a in serie]
        if not puntos:
            continue
        xs = [p[0] for p in puntos]
        ys = [p[1] for p in puntos]
        linea, = ax.plot(
            xs, ys,
            color=color,
            linewidth=tema.grosor_linea,
            solid_capstyle="round",
            solid_joinstyle="round",
            marker="o",
            markersize=tema.diametro_marcador,
            markerfacecolor=color,
            markeredgecolor=tema.superficie,   # anillo de 2 px del color de superficie
            markeredgewidth=tema.anillo_marcador,
            zorder=3,
        )
        handles.append(linea)
        etiquetas.append(nombre)
        finales.append((ys[-1], xs[-1], nombre))

    # Etiqueta directa al final de la línea (hasta 4 series, §7.5), separando las
    # que caerían una encima de otra.
    if con_etiqueta_directa and finales:
        separacion = lienzo.a_datos_y(alto_texto(tema.fuente_eje))
        finales.sort()
        colocadas: list[float] = []
        for y_valor, x_valor, nombre in finales:
            y_etiqueta = y_valor
            if colocadas and y_etiqueta - colocadas[-1] < separacion:
                y_etiqueta = colocadas[-1] + separacion
            colocadas.append(y_etiqueta)
            ax.text(x_valor + lienzo.a_datos_x(px(10)), y_etiqueta, nombre,
                    va="center", ha="left", fontsize=tema.fuente_eje,
                    color=tema.texto_primario, clip_on=False)

    _leyenda(lienzo, handles, etiquetas)
    return lienzo.fig


def panel(
    paneles: list[tuple[str, list[str], list[float | None], int]],
    tema: Tema,
    titulo: str,
    subtitulo: str = "",
    pie: str = "",
    filas: int = 2,
    columnas_grid: int = 2,
    tamano: tuple[float, float] = TAMANO_BASE,
) -> plt.Figure:
    """Small multiples: cada indicador con su propia escala, un color para todos.

    Cada panel es `(título, categorías, valores, decimales)`.
    """
    aplicar_rcparams(tema)
    W, H = tamano
    fig = plt.figure(figsize=tamano, dpi=DPI_SALIDA, facecolor=tema.superficie)
    ancho_util = W - BORDE - MARGEN_DER
    alto_cabecera = _dibujar_cabecera(fig, tema, titulo, subtitulo, ancho_util)
    alto_pie = _dibujar_pie(fig, tema, pie, ancho_util)

    categorias = paneles[0][1] if paneles else []
    izq, der = 0.70, 0.30
    alto_disponible = max(H - alto_cabecera - alto_pie, 1.2)
    ancho_disponible = max(W - izq - der, 1.2)
    sep_x, sep_y = 0.62, 0.34
    ancho_celda = (ancho_disponible - sep_x * (columnas_grid - 1)) / columnas_grid

    ancho_slot = ancho_celda / max(len(categorias), 1)
    fuente_mini = tema.fuente_eje * 0.85
    etiquetas, rotacion, alto_cat = _preparar_categorias(categorias, ancho_slot, fuente_mini)

    # El título de cada panel se envuelve al ancho de su celda: en una rejilla de
    # tres columnas, "Violencia intrafamiliar (x 100.000 hab)" no cabe de un tirón
    # y recortarlo está prohibido.
    # Cada título llega como "nombre\nunidad": el nombre en primario y la unidad
    # debajo en secundario, cada parte envuelta a lo que da la celda.
    titulos: list[list[tuple[str, bool]]] = []
    for p in paneles:
        lineas_panel: list[tuple[str, bool]] = []
        for indice_parte, parte in enumerate(str(p[0]).split("\n")):
            principal = indice_parte == 0
            tamano = tema.fuente_subtitulo if principal else tema.fuente_pie
            for linea in envolver(parte, ancho_celda, tamano, max_lineas=2) or [parte]:
                lineas_panel.append((linea, principal))
        titulos.append(lineas_panel)
    lineas_titulo = max((len(t) for t in titulos), default=1)

    # Solo la fila de abajo lleva los nombres de las entidades; el resto de las
    # celdas ceden ese alto a los ejes para que los paneles no queden enanos.
    alto_titulo = alto_texto(tema.fuente_subtitulo, lineas_titulo) + px(6)
    alto_ejes = max(
        (alto_disponible - alto_cat - sep_y * (filas - 1)) / filas - alto_titulo,
        0.5,
    )
    alto_fila = alto_ejes + alto_titulo + sep_y

    color = tema.color(1)
    for indice, (titulo_panel, cats, valores, dec) in enumerate(paneles):
        fila = indice // columnas_grid
        col = indice % columnas_grid
        x0 = izq + col * (ancho_celda + sep_x)
        y_tope = H - alto_cabecera - fila * alto_fila
        y0 = y_tope - alto_titulo - alto_ejes

        ax = fig.add_axes([x0 / W, y0 / H, ancho_celda / W, alto_ejes / H])
        ax.set_facecolor(tema.superficie)
        for lado in ("top", "right"):
            ax.spines[lado].set_visible(False)
        for lado in ("left", "bottom"):
            ax.spines[lado].set_color(tema.rejilla)
            ax.spines[lado].set_linewidth(tema.grosor_rejilla)
        ax.tick_params(colors=tema.texto_secundario, labelsize=fuente_mini, length=0, pad=4)

        lienzo = Lienzo(fig=fig, ax=ax, tema=tema,
                        ancho_ejes=ancho_celda, alto_ejes=alto_ejes)
        ax.set_xlim(-0.5, len(cats) - 0.5)
        _rejilla_horizontal(lienzo)

        # También en los mini-paneles cada barra lleva su cifra, con la fuente
        # pequeña y girada si el panel es estrecho.
        textos = [formato_es(v, dec) for v in valores if v is not None]
        giro, espacio = plan_etiquetas(tema, textos,
                                       ancho_celda / max(len(cats), 1),
                                       fuente=fuente_mini)
        ax.set_ylim(*_limites_con_espacio(valores, alto_ejes, espacio))

        from matplotlib.ticker import MaxNLocator

        ax.yaxis.set_major_locator(MaxNLocator(nbins=4, integer=dec == 0))
        ajustar_formato_eje(ax, "y")
        ax.set_xticks(range(len(cats)))
        es_ultima_fila = fila == filas - 1 or indice + columnas_grid >= len(paneles)
        if es_ultima_fila:
            ax.set_xticklabels(etiquetas, rotation=rotacion, fontsize=fuente_mini,
                               ha="right" if rotacion else "center", rotation_mode="anchor")
        else:
            ax.set_xticklabels([])

        grosor = _grosor_barra(lienzo, max(len(cats), 1))
        holgura_mini = lienzo.a_datos_y(px(4))
        for i, valor in enumerate(valores):
            if valor is None:
                continue
            dibujar_barra(lienzo, i - grosor / 2, 0.0, i + grosor / 2, valor, color,
                          "arriba" if valor >= 0 else "abajo")
            texto = formato_es(valor, dec)
            ax.text(
                i, valor + (holgura_mini if valor >= 0 else -holgura_mini), texto,
                va="bottom" if valor >= 0 else "top", ha="center", rotation=giro,
                fontsize=fuente_mini, color=tema.texto_primario, zorder=4, clip_on=False,
            )

        y_titulo = y_tope - alto_texto(tema.fuente_subtitulo) * 0.78
        for linea, principal in titulos[indice]:
            fig.text(
                x0 / W, y_titulo / H, linea,
                fontsize=tema.fuente_subtitulo if principal else tema.fuente_pie,
                color=tema.texto_primario if principal else tema.texto_secundario,
                va="baseline", ha="left",
                fontweight="semibold" if principal else "normal",
            )
            y_titulo -= alto_texto(
                tema.fuente_subtitulo if principal else tema.fuente_pie
            )

    return fig


def barras_agrupadas_h(
    categorias: list[str],
    series: list[tuple[str, list[float | None]]],
    tema: Tema,
    titulo: str,
    subtitulo: str = "",
    pie: str = "",
    decimales: int | None = None,
    tamano: tuple[float, float] = TAMANO_BASE,
    orden: str = "dado",
) -> plt.Figure:
    """Barras horizontales agrupadas: 2 a 4 series de la misma unidad.

    La versión acostada de `columnas_agrupadas`. Se usa cuando los nombres de las
    categorías son largos: acostadas se leen enteras sin rotar.
    """
    todos = [v for _, vs in series for v in vs if v is not None]
    dec = decimales_para(todos) if decimales is None else decimales

    indices = list(range(len(categorias)))
    if orden in ("asc", "desc"):
        totales = [
            sum(vs[i] for _, vs in series if vs[i] is not None) for i in indices
        ]
        indices.sort(key=lambda i: totales[i], reverse=(orden == "desc"))
    nombres = [categorias[i] for i in indices]

    margen_izq = max(
        MARGEN_IZQ,
        min(MARGEN_IZQ_RANKING,
            max((ancho_texto(n, tema.fuente_eje) for n in nombres), default=0.6) + 0.28),
    )
    lienzo = crear_lienzo(tema, titulo, subtitulo, pie, tamano,
                          margen_izq=margen_izq,
                          alto_categorias=alto_texto(tema.fuente_eje) + px(10),
                          alto_leyenda=alto_de_leyenda(tema, len(series)))
    ax = lienzo.ax
    ax.set_ylim(-0.5, max(len(nombres) - 0.5, 0.5))
    textos = [formato_es(v, dec) for v in todos]
    espacio = max((ancho_texto(x, tema.fuente_valor) for x in textos), default=0.0) + px(12)
    ax.set_xlim(*_limites_con_espacio(todos, lienzo.ancho_ejes, espacio))
    ax.invert_yaxis()
    _rejilla_vertical(lienzo)
    ajustar_formato_eje(ax, "x")
    ax.set_yticks(range(len(nombres)))
    ax.set_yticklabels(nombres)

    n = len(series)
    grosor = _grosor_barra_horizontal(lienzo, len(nombres), n)
    hueco = lienzo.a_datos_y(tema.hueco)
    paso = grosor + hueco
    alto_grupo = paso * n - hueco
    holgura_x = lienzo.a_datos_x(px(6))

    handles = []
    for s, (nombre, valores) in enumerate(series):
        color = tema.color(s + 1)
        handles.append(plt.Rectangle((0, 0), 1, 1, facecolor=color, edgecolor="none"))
        for fila, indice in enumerate(indices):
            valor = valores[indice]
            if valor is None:
                continue
            centro = fila - alto_grupo / 2 + paso * s + grosor / 2
            dibujar_barra(lienzo, 0.0, centro - grosor / 2, valor, centro + grosor / 2,
                          color, "derecha" if valor >= 0 else "izquierda")
            # La etiqueta va afuera de la barra, en el aire que el eje ya reservó.
            _etiqueta_valor(lienzo, valor + holgura_x, centro, formato_es(valor, dec),
                            va="center", ha="left")

    _leyenda(lienzo, handles, [n for n, _ in series])
    return lienzo.fig


def piramide(
    grupos: list[str],
    hombres: list[float | None],
    mujeres: list[float | None],
    tema: Tema,
    titulo: str,
    subtitulo: str = "",
    pie: str = "",
    etiquetas: tuple[str, str] = ("Hombres", "Mujeres"),
    tamano: tuple[float, float] = TAMANO_PIRAMIDE,
    decimales: int = 0,
) -> plt.Figure:
    """Pirámide poblacional: barras horizontales enfrentadas por grupo de edad.

    El eje X es simétrico y sus rótulos van en valor absoluto: a la izquierda los
    hombres no son cantidades negativas, solo están dibujados hacia ese lado.
    Cada barra lleva su cifra en la punta, por fuera de la marca.
    """
    finitos = [abs(v) for v in list(hombres) + list(mujeres) if v is not None]
    maximo = max(finitos) if finitos else 1.0

    margen_izq = max(
        MARGEN_IZQ,
        max((ancho_texto(g, tema.fuente_eje) for g in grupos), default=0.6) + 0.30,
    )
    lienzo = crear_lienzo(tema, titulo, subtitulo, pie, tamano,
                          margen_izq=margen_izq,
                          alto_categorias=alto_texto(tema.fuente_eje) + px(10),
                          alto_leyenda=alto_de_leyenda(tema, 2))
    ax = lienzo.ax
    ax.set_ylim(-0.6, len(grupos) - 0.4)
    # El eje simétrico reserva a cada lado el ancho de la cifra más larga.
    textos = [formato_es(v, decimales)
              for v in list(hombres) + list(mujeres) if v is not None]
    espacio = max((ancho_texto(x, tema.fuente_valor) for x in textos), default=0.0) + px(12)
    fraccion = min(espacio / (lienzo.ancho_ejes / 2), 0.45)
    tope = maximo / (1.0 - fraccion)
    ax.set_xlim(-tope, tope)
    _rejilla_vertical(lienzo)
    ax.set_yticks(range(len(grupos)))
    ax.set_yticklabels(grupos)
    ax.xaxis.set_major_formatter(formateador_eje(0))
    # Rótulos en valor absoluto: el signo solo indica el lado.
    from matplotlib.ticker import FuncFormatter

    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _p: formato_es(abs(v), 0)))

    grosor = _grosor_barra_horizontal(lienzo, len(grupos))
    color_h, color_m = tema.color(1), tema.color(2)
    holgura_x = lienzo.a_datos_x(px(6))
    for i, (h, m) in enumerate(zip(hombres, mujeres)):
        if h is not None:
            dibujar_barra(lienzo, -h, i - grosor / 2, 0.0, i + grosor / 2, color_h,
                          "izquierda")
            _etiqueta_valor(lienzo, -h - holgura_x, i, formato_es(h, decimales),
                            va="center", ha="right")
        if m is not None:
            dibujar_barra(lienzo, 0.0, i - grosor / 2, m, i + grosor / 2, color_m,
                          "derecha")
            _etiqueta_valor(lienzo, m + holgura_x, i, formato_es(m, decimales),
                            va="center", ha="left")

    ax.axvline(0, color=tema.rejilla, linewidth=tema.grosor_rejilla, zorder=2)
    handles = [
        plt.Rectangle((0, 0), 1, 1, facecolor=color_h, edgecolor="none"),
        plt.Rectangle((0, 0), 1, 1, facecolor=color_m, edgecolor="none"),
    ]
    _leyenda(lienzo, handles, list(etiquetas))
    return lienzo.fig


# --------------------------------------------------------------------------- salida


def guardar(fig: plt.Figure, ruta_sin_extension, formatos=("png", "svg")) -> list[str]:
    """Guarda la figura sin recortar: la maqueta ya es exacta."""
    from pathlib import Path as RutaFS

    generados = []
    base = RutaFS(ruta_sin_extension)
    for formato in formatos:
        destino = base.with_suffix(f".{formato}")
        destino.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(
            destino,
            format=formato,
            dpi=DPI_SALIDA,
            facecolor=fig.get_facecolor(),
            edgecolor="none",
        )
        generados.append(str(destino))
    return generados


def cerrar(fig: plt.Figure) -> None:
    plt.close(fig)
