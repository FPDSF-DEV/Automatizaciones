"""Paleta, tipografía y specs de marca (§7 del PLAN). Aquí no se inventan colores.

Sobre los píxeles de las specs
------------------------------
Las specs vienen en píxeles de diseño (los de una hoja de estilos, a 96 dpi):
barras de 24 px, huecos de 2 px, líneas de 2 px, esquinas de 4 px. Los PNG salen
a 200 dpi, así que un píxel de diseño vale 200/96 ≈ 2,08 píxeles de salida. Todo
el módulo convierte a **pulgadas** con `px()`, que es la unidad en la que
matplotlib razona; así una barra de 24 px de diseño mide lo mismo en el PNG de
200 dpi y en el SVG, y no cambia de grosor si algún día cambia el dpi.
"""

from __future__ import annotations

from dataclasses import dataclass

DPI_DISENO = 96.0
DPI_SALIDA = 200


def px(valor: float) -> float:
    """Píxeles de diseño -> pulgadas."""
    return valor / DPI_DISENO


def pt(valor: float) -> float:
    """Píxeles de diseño -> puntos tipográficos (1 pt = 1/72 pulgada)."""
    return valor * 72.0 / DPI_DISENO


# --- Paleta categórica (§7.1). Orden fijo: se asignan los slots en orden, nunca cíclico.

PALETA_CLARA = [
    "#2a78d6",  # 1 azul
    "#eb6834",  # 2 naranja
    "#1baf7a",  # 3 aqua
    "#eda100",  # 4 amarillo
    "#e87ba4",  # 5 magenta
    "#008300",  # 6 verde
    "#4a3aa7",  # 7 violeta
    "#e34948",  # 8 rojo
]

PALETA_OSCURA = [
    "#3987e5",
    "#d95926",
    "#199e70",
    "#c98500",
    "#d55181",
    "#008300",
    "#9085e9",
    "#e66767",
]

# --- Rampa secuencial (§7.2), azul claro -> oscuro. Solo para magnitud continua.

RAMPA_SECUENCIAL = [
    "#cde2fb", "#b7d3f6", "#9ec5f4", "#86b6ef", "#6da7ec", "#5598e7", "#3987e5",
    "#2a78d6", "#256abf", "#1c5cab", "#184f95", "#104281", "#0d366b",
]


@dataclass(frozen=True)
class Tema:
    nombre: str
    paleta: list[str]
    superficie: str
    texto_primario: str
    texto_secundario: str
    rejilla: str

    # --- specs de marca, en pulgadas o puntos

    grosor_barra_max: float = px(24)      # §7.4: máximo 24 px de grosor
    hueco: float = px(2)                  # §7.4: 2 px del color de la superficie
    radio_esquina: float = px(4)          # §7.4: extremo del dato redondeado 4 px
    grosor_linea: float = pt(2)           # §7.4: líneas de 2 px
    diametro_marcador: float = pt(8)      # §7.4: marcadores >= 8 px
    anillo_marcador: float = pt(2)        # §7.4: anillo de 2 px del color de superficie
    grosor_rejilla: float = pt(1)         # §7.4: rejilla de 1 px, sólida

    # --- tipografía (px de diseño -> pt)

    fuente_titulo: float = pt(24)
    fuente_subtitulo: float = pt(14)
    fuente_eje: float = pt(12)
    fuente_valor: float = pt(12)
    fuente_leyenda: float = pt(13)
    fuente_pie: float = pt(11)

    def color(self, slot: int) -> str:
        """El color del slot (1-based). Nunca recicla: pasar de 8 es un error del catálogo."""
        if not 1 <= slot <= len(self.paleta):
            raise ValueError(
                f"slot {slot} fuera de la paleta de {len(self.paleta)} colores: "
                "ninguna gráfica debe pasar de 8 series (§7.1)"
            )
        return self.paleta[slot - 1]

    def colores(self, n: int) -> list[str]:
        """Los primeros n colores, en orden."""
        return [self.color(i + 1) for i in range(n)]


CLARO = Tema(
    nombre="claro",
    paleta=PALETA_CLARA,
    superficie="#fcfcfb",
    texto_primario="#0b0b0b",
    texto_secundario="#52514e",
    rejilla="#e6e5e1",
)

OSCURO = Tema(
    nombre="oscuro",
    paleta=PALETA_OSCURA,
    superficie="#1a1a19",
    texto_primario="#ffffff",
    texto_secundario="#c3c2b7",
    rejilla="#383835",
)

TEMAS = {"claro": CLARO, "oscuro": OSCURO}

# Tipografías en orden de preferencia; DejaVu Sans siempre está con matplotlib.
FUENTES = ["Segoe UI", "Helvetica Neue", "Helvetica", "Arial", "DejaVu Sans"]

_familia_resuelta: str | None = None


def familia_disponible() -> str:
    """La primera tipografía de la lista que exista en el sistema.

    Se resuelve una sola vez: pasarle la lista entera a matplotlib hace que
    avise por cada fuente ausente, una vez por cada texto de cada gráfica.
    """
    global _familia_resuelta
    if _familia_resuelta is None:
        from matplotlib import font_manager

        instaladas = {f.name for f in font_manager.fontManager.ttflist}
        _familia_resuelta = next((f for f in FUENTES if f in instaladas), "DejaVu Sans")
    return _familia_resuelta

# --- Tamaños de figura (§7.7), en pulgadas a DPI_SALIDA

TAMANO_BASE = (1600 / DPI_SALIDA, 900 / DPI_SALIDA)     # 8,0 × 4,5
TAMANO_TORTA = (1100 / DPI_SALIDA, 900 / DPI_SALIDA)    # 5,5 × 4,5
TAMANO_LINEAS = (2000 / DPI_SALIDA, 800 / DPI_SALIDA)   # 10,0 × 4,0
# La pirámide lleva 17 filas con su cifra a cada lado: necesita más alto que la
# base para que las etiquetas no se toquen entre filas.
TAMANO_PIRAMIDE = (1600 / DPI_SALIDA, 1100 / DPI_SALIDA)


def aplicar_rcparams(tema: Tema) -> None:
    """Deja matplotlib alineado con el tema. Se llama una vez por render."""
    import matplotlib

    matplotlib.use("Agg", force=False)
    from matplotlib import rcParams

    rcParams["figure.dpi"] = DPI_SALIDA
    rcParams["savefig.dpi"] = DPI_SALIDA
    rcParams["font.family"] = "sans-serif"
    rcParams["font.sans-serif"] = [familia_disponible()]
    rcParams["font.size"] = tema.fuente_eje
    rcParams["figure.facecolor"] = tema.superficie
    rcParams["savefig.facecolor"] = tema.superficie
    rcParams["axes.facecolor"] = tema.superficie
    rcParams["text.color"] = tema.texto_primario
    rcParams["axes.labelcolor"] = tema.texto_secundario
    rcParams["xtick.color"] = tema.texto_secundario
    rcParams["ytick.color"] = tema.texto_secundario
    rcParams["axes.edgecolor"] = tema.rejilla
    rcParams["grid.color"] = tema.rejilla
    rcParams["grid.linestyle"] = "-"       # §7.4: nunca punteada
    rcParams["grid.linewidth"] = tema.grosor_rejilla
    rcParams["axes.grid"] = False
    rcParams["axes.spines.top"] = False    # §7.4: sin marco
    rcParams["axes.spines.right"] = False
    rcParams["svg.fonttype"] = "none"      # §7.7: texto como texto, no trazados
    rcParams["pdf.fonttype"] = 42
    rcParams["axes.unicode_minus"] = True


# --- Formato numérico colombiano (§7.5)


def formato_es(valor: float, decimales: int = 0) -> str:
    """1234567.5 -> '1.234.567,5' (punto de miles, coma decimal)."""
    if valor is None:
        return "—"
    texto = f"{valor:,.{decimales}f}"
    return texto.replace(",", "\x00").replace(".", ",").replace("\x00", ".")


def formateador_eje(decimales: int = 0):
    """FuncFormatter con el formato colombiano para los ticks del eje."""
    from matplotlib.ticker import FuncFormatter

    return FuncFormatter(lambda v, _pos: formato_es(v, decimales))


def decimales_para(valores: list[float]) -> int:
    """Cuántos decimales merece una escala: los grandes no llevan ninguno."""
    finitos = [abs(v) for v in valores if v is not None]
    if not finitos:
        return 0
    mayor = max(finitos)
    if mayor >= 1000:
        return 0
    if mayor >= 100:
        return 0
    return 1
