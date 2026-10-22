"""Las 52 gráficas del Apéndice B y el armado de cada una.

Cada entrada dice qué forma usa y de qué indicadores se alimenta. Si un
indicador no está en los datos cargados, la serie se cae; si no queda ninguna,
la gráfica se omite **con un aviso**, nunca con una excepción (§4.2).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from . import graficas as g
from .estilo import TAMANO_BASE, TAMANO_LINEAS, TAMANO_TORTA, Tema, formato_es
from .resolucion import Resultado

log = logging.getLogger("terridata.graficas")

SECCIONES: list[tuple[str, str]] = [
    ("poblacion", "Población y aseguramiento"),
    ("ods1", "ODS 1 · Fin de la pobreza"),
    ("ods2", "ODS 2 · Hambre cero"),
    ("ods3", "ODS 3 · Salud y bienestar"),
    ("ods6", "ODS 6 · Agua limpia y saneamiento"),
    ("salud_publica", "Salud pública"),
]

NOMBRE_SECCION = dict(SECCIONES)

# Etiquetas cortas para leyendas y paneles: en la leyenda el contexto ya lo da
# el título, y "Población cabecera (urbana)" no cabe seis veces seguidas.
ETIQUETAS_CORTAS = {
    "POB_TOTAL": "Total",
    "POB_URB": "Urbana",
    "POB_RUR": "Rural",
    "POB_H": "Hombres",
    "POB_M": "Mujeres",
    "AFIL_SUBS": "Subsidiado",
    "AFIL_CONTRIB": "Contributivo",
    "AFIL_ESP": "Especiales",
    "AFIL_SGSSS": "Total SGSSS",
    "TOTAL_AFILIADOS": "Total afiliados",
    "SISBEN_REG": "Sisbenizados",
    "PPNA": "PPNA",
    "ACU_CENSO": "Censo",
    "ACU_REC": "REC",
    "ALC_CENSO": "Censo",
    "ALC_REC": "REC",
    "ACU_URB": "Urbana",
    "ACU_RUR": "Rural",
    "ALC_URB": "Urbana",
    "ALC_RUR": "Rural",
    "ASEO_REC": "Total",
    "ASEO_URB": "Urbana",
    "ASEO_RUR": "Rural",
    "ENER_RUR": "Energía rural",
    "BANDA": "Internet fijo",
    "DEF_CUAL": "Cualitativo",
    "DEF_CUANT": "Cuantitativo",
    "CULT_T1": "1º transitorio",
    "CULT_T2": "2º transitorio",
    "CULT_T3": "3º transitorio",
    "CULT_P1": "1º permanente",
    "CULT_P2": "2º permanente",
    "FECUNDIDAD": "Fecundidad",
    "MORT_INF": "Mortalidad infantil",
    "MORT_GEN": "Mortalidad general",
    "MORT_MAT": "Mortalidad materna",
    "VAC_PENTA": "Vacunación pentavalente",
    "T_VIF": "Violencia intrafamiliar",
}

# Nombre del cultivo que acompaña a cada indicador de tonelaje (§ Apéndice B #28).
NOMBRE_CULTIVO = {
    "CULT_T1": "NOM_T1",
    "CULT_T2": "NOM_T2",
    "CULT_T3": "NOM_T3",
    "CULT_P1": "NOM_P1",
    "CULT_P2": "NOM_P2",
    "CULT_P3": "NOM_P3",
}

META_VACUNACION = (95.0, "Meta 95 %")


@dataclass(frozen=True)
class Spec:
    numero: int
    id: str
    seccion: str
    forma: str
    titulo: str
    series: tuple[str, ...]
    meta: tuple[float, str] | None = None
    grid: tuple[int, int] | None = None


@dataclass
class Render:
    spec: Spec
    fig: object
    titulo: str
    subtitulo: str
    pie: str
    encabezados: list[str] = field(default_factory=list)
    filas: list[list[str]] = field(default_factory=list)
    svg: str = ""      # marcado para el dashboard, capturado antes de cerrar la figura

    @property
    def archivo(self) -> str:
        """`<seccion>_<id>`, sin repetir el prefijo: los ids del Apéndice B ya
        traen la sección (`ods1_pob_torta`) y `ods1_ods1_pob_torta` sobra."""
        if self.spec.id.startswith(self.spec.seccion):
            return self.spec.id
        return f"{self.spec.seccion}_{self.spec.id}"


# --------------------------------------------------------------------------- catálogo

GRAFICAS: list[Spec] = [
    # --- poblacion (15)
    Spec(1, "pob_total", "poblacion", "columnas", "Población total", ("POB_TOTAL",)),
    Spec(2, "pob_pct_total", "poblacion", "columnas",
         "Participación de cada entidad en la población del conjunto", ("PCT_DEL_TOTAL",)),
    Spec(3, "densidad", "poblacion", "columnas", "Densidad poblacional", ("DENSIDAD",)),
    Spec(4, "pob_hombres", "poblacion", "columnas", "Población de hombres", ("POB_H",)),
    Spec(5, "pob_mujeres", "poblacion", "columnas", "Población de mujeres", ("POB_M",)),
    Spec(6, "pct_rural", "poblacion", "columnas",
         "Peso de la población rural sobre el total", ("PCT_RURAL",)),
    Spec(7, "afil_subsidiado", "poblacion", "columnas",
         "Afiliados al régimen subsidiado", ("AFIL_SUBS",)),
    Spec(8, "afil_contributivo", "poblacion", "columnas",
         "Afiliados al régimen contributivo", ("AFIL_CONTRIB",)),
    Spec(9, "afil_total", "poblacion", "columnas",
         "Total de afiliados al SGSSS", ("TOTAL_AFILIADOS",)),
    Spec(10, "sisbenizados", "poblacion", "columnas",
         "Personas con registro válido en el SISBEN", ("SISBEN_REG",)),
    Spec(11, "sisben_puntaje", "poblacion", "columnas",
         "Puntaje promedio del SISBEN", ("SISBEN_T",)),
    Spec(12, "ipm", "poblacion", "columnas",
         "Índice de Pobreza Multidimensional", ("IPM",)),
    Spec(13, "dist_sexo", "poblacion", "columnas_agrupadas",
         "Distribución de la población por sexo", ("POB_H", "POB_M")),
    Spec(14, "dist_urbano_rural", "poblacion", "columnas_agrupadas",
         "Distribución de la población entre cabecera y resto", ("POB_URB", "POB_RUR")),
    Spec(15, "regimenes", "poblacion", "columnas_apiladas",
         "Composición de la afiliación por régimen",
         ("AFIL_SUBS", "AFIL_CONTRIB", "AFIL_ESP")),

    # --- ods1 (12)
    Spec(16, "ods1_pob_torta", "ods1", "torta",
         "Reparto de la población total", ("POB_TOTAL",)),
    Spec(17, "ods1_pct_ranking", "ods1", "barras_ranking",
         "Participación en la población del conjunto", ("PCT_DEL_TOTAL",)),
    Spec(18, "ods1_mujeres_torta", "ods1", "torta",
         "Reparto de la población de mujeres", ("POB_M",)),
    Spec(19, "ods1_hombres_torta", "ods1", "torta",
         "Reparto de la población de hombres", ("POB_H",)),
    Spec(20, "ods1_rural_torta", "ods1", "torta",
         "Reparto de la población rural", ("POB_RUR",)),
    Spec(21, "ods1_urbana_torta", "ods1", "torta",
         "Reparto de la población urbana", ("POB_URB",)),
    Spec(22, "ods1_poblacion_comparativo", "ods1", "columnas_agrupadas",
         "Población por sexo y zona",
         ("POB_TOTAL", "POB_M", "POB_H", "POB_RUR", "POB_URB")),
    Spec(23, "ods1_sisben_torta", "ods1", "torta",
         "Reparto de los registros válidos del SISBEN", ("SISBEN_REG",)),
    Spec(24, "ods1_contributivo_torta", "ods1", "torta",
         "Reparto de los afiliados al régimen contributivo", ("AFIL_CONTRIB",)),
    Spec(25, "ods1_subsidiado_torta", "ods1", "torta",
         "Reparto de los afiliados al régimen subsidiado", ("AFIL_SUBS",)),
    Spec(26, "ods1_ppna", "ods1", "columnas",
         "Población pobre no atendida (PPNA)", ("PPNA",)),
    Spec(27, "ods1_aseguramiento_comparativo", "ods1", "columnas_agrupadas",
         "Comparativo de aseguramiento en salud",
         ("SISBEN_REG", "AFIL_CONTRIB", "AFIL_SUBS", "AFIL_ESP", "TOTAL_AFILIADOS", "PPNA")),

    # --- ods2 (5)
    Spec(28, "ods2_t1_torta", "ods2", "torta",
         "Reparto del primer cultivo transitorio", ("CULT_T1",)),
    Spec(29, "ods2_t2_torta", "ods2", "torta",
         "Reparto del segundo cultivo transitorio", ("CULT_T2",)),
    Spec(30, "ods2_p1_torta", "ods2", "torta",
         "Reparto del primer cultivo permanente", ("CULT_P1",)),
    Spec(31, "ods2_p2_torta", "ods2", "torta",
         "Reparto del segundo cultivo permanente", ("CULT_P2",)),
    Spec(32, "ods2_cultivos", "ods2", "columnas_agrupadas",
         "Producción de los principales cultivos",
         ("CULT_T1", "CULT_T2", "CULT_T3", "CULT_P1", "CULT_P2")),

    # --- ods3 (5)
    Spec(33, "ods3_fecundidad", "ods3", "barras_ranking",
         "Tasa de fecundidad", ("FECUNDIDAD",)),
    Spec(34, "ods3_mort_infantil", "ods3", "barras_ranking",
         "Tasa de mortalidad infantil en menores de 1 año", ("MORT_INF",)),
    Spec(35, "ods3_mort_general", "ods3", "barras_ranking",
         "Tasa de mortalidad general", ("MORT_GEN",)),
    Spec(36, "ods3_vacunacion", "ods3", "barras_ranking",
         "Cobertura de vacunación pentavalente en menores de 1 año",
         ("VAC_PENTA",), meta=META_VACUNACION),
    Spec(37, "ods3_panel", "ods3", "panel",
         "Comparativo de indicadores de salud",
         ("FECUNDIDAD", "MORT_INF", "MORT_GEN", "VAC_PENTA"), grid=(2, 2)),

    # --- ods6 (10)
    Spec(38, "ods6_acueducto_ranking", "ods6", "barras_ranking",
         "Cobertura de acueducto (REC)", ("ACU_REC",)),
    Spec(39, "ods6_alcantarillado_ranking", "ods6", "barras_ranking",
         "Cobertura de alcantarillado (REC)", ("ALC_REC",)),
    Spec(40, "ods6_acueducto_censo_rec", "ods6", "columnas_agrupadas",
         "Cobertura de acueducto: Censo frente a REC", ("ACU_CENSO", "ACU_REC")),
    Spec(41, "ods6_alcantarillado_censo_rec", "ods6", "columnas_agrupadas",
         "Cobertura de alcantarillado: Censo frente a REC", ("ALC_CENSO", "ALC_REC")),
    Spec(42, "ods6_acueducto_urb_rur", "ods6", "columnas_agrupadas",
         "Cobertura de acueducto por zona", ("ACU_URB", "ACU_RUR")),
    Spec(43, "ods6_alcantarillado_urb_rur", "ods6", "columnas_agrupadas",
         "Cobertura de alcantarillado por zona", ("ALC_URB", "ALC_RUR")),
    Spec(44, "ods6_aseo", "ods6", "columnas_agrupadas",
         "Cobertura de aseo", ("ASEO_REC", "ASEO_URB", "ASEO_RUR")),
    Spec(45, "ods6_energia_internet", "ods6", "columnas_agrupadas",
         "Energía eléctrica rural e internet fijo", ("ENER_RUR", "BANDA")),
    Spec(46, "ods6_deficit_vivienda", "ods6", "columnas_agrupadas",
         "Déficit de vivienda", ("DEF_CUAL", "DEF_CUANT")),
    Spec(47, "ods6_inversion_apsb", "ods6", "lineas",
         "Porcentaje de inversión en agua potable y saneamiento básico", ("PCT_APSB",)),

    # --- salud_publica (5)
    Spec(48, "sp_vacunacion", "salud_publica", "columnas",
         "Cobertura de vacunación pentavalente en menores de 1 año",
         ("VAC_PENTA",), meta=META_VACUNACION),
    Spec(49, "sp_vif", "salud_publica", "columnas",
         "Tasa de violencia intrafamiliar", ("T_VIF",)),
    Spec(50, "sp_mort_infantil", "salud_publica", "columnas",
         "Tasa de mortalidad infantil en menores de 1 año", ("MORT_INF",)),
    Spec(51, "sp_fecundidad", "salud_publica", "columnas",
         "Tasa de fecundidad", ("FECUNDIDAD",)),
    Spec(52, "sp_panel", "salud_publica", "panel",
         "Panorama de salud pública",
         ("FECUNDIDAD", "MORT_MAT", "MORT_INF", "MORT_GEN", "VAC_PENTA", "T_VIF"),
         grid=(2, 3)),
]

assert len(GRAFICAS) == 52, "el Apéndice B define exactamente 52 gráficas"


# --------------------------------------------------------------------------- textos


def _etiqueta_corta(res: Resultado, id_indicador: str) -> str:
    return ETIQUETAS_CORTAS.get(id_indicador, res.etiqueta(id_indicador))


def _anios(res: Resultado, ids: list[str]) -> str:
    anios = sorted({res.anios.get(i) for i in ids if res.anios.get(i)})
    if not anios:
        return "sin año"
    if len(anios) == 1:
        return str(anios[0])
    return f"{anios[0]}–{anios[-1]}"


def _fuentes(res: Resultado, ids: list[str]) -> str:
    vistas: list[str] = []
    for i in ids:
        f = res.fuente(i)
        if f and f not in vistas:
            vistas.append(f)
    return " y ".join(vistas[:2]) if vistas else "TerriData"


def _unidad(res: Resultado, ids: list[str]) -> str:
    unidades = []
    for i in ids:
        u = res.unidad(i)
        if u and u not in unidades:
            unidades.append(u)
    return unidades[0] if unidades else ""


def _subtitulo(res: Resultado, ids: list[str]) -> str:
    """Unidad, año del dato y fuente (§7.5)."""
    partes = [p for p in (_unidad(res, ids), f"dato de {_anios(res, ids)}", _fuentes(res, ids)) if p]
    return " · ".join(partes)


def _pie(res: Resultado, ids: list[str]) -> str:
    return f"Fuente: TerriData (DNP) — {_fuentes(res, ids)} · Dato {_anios(res, ids)}"


def _titulo_con_cultivo(res: Resultado, spec: Spec) -> str:
    """El título del cultivo lleva el nombre de la entidad que más produce."""
    id_cultivo = spec.series[0]
    id_nombre = NOMBRE_CULTIVO.get(id_cultivo)
    if not id_nombre:
        return spec.titulo
    mayor, mayor_valor = None, None
    for e in res.entidades:
        v = res.numero(id_cultivo, e)
        if v is not None and (mayor_valor is None or v > mayor_valor):
            mayor, mayor_valor = e, v
    nombre = res.valor(id_nombre, mayor) if mayor else None
    return f"{spec.titulo} — {nombre} en {mayor}" if nombre else spec.titulo


# --------------------------------------------------------------------------- datos


def _series_disponibles(res: Resultado, spec: Spec) -> list[str]:
    return [i for i in spec.series if res.disponible(i)]


def _tabla(res: Resultado, ids: list[str]) -> tuple[list[str], list[list[str]]]:
    """Los datos que alimentan la gráfica, para la vista de tabla del dashboard."""
    encabezados = ["Entidad"] + [
        f"{res.etiqueta(i)} ({res.unidad(i)})" if res.unidad(i) else res.etiqueta(i)
        for i in ids
    ]
    filas = []
    for e in res.entidades:
        fila = [e]
        for i in ids:
            v = res.valor(i, e)
            if v is None:
                fila.append("—")
            elif isinstance(v, str):
                fila.append(v)
            else:
                fila.append(formato_es(v, res.decimales.get(i, 2)))
        filas.append(fila)
    return encabezados, filas


def _tabla_series(res: Resultado, id_indicador: str, anios: list[int]) -> tuple[list[str], list[list[str]]]:
    encabezados = ["Entidad"] + [str(a) for a in anios]
    filas = []
    for e in res.entidades:
        serie = res.serie_temporal(id_indicador, e)
        filas.append([e] + [
            formato_es(serie[a], res.decimales.get(id_indicador, 2)) if a in serie else "—"
            for a in anios
        ])
    return encabezados, filas


# --------------------------------------------------------------------------- armado


def construir(spec: Spec, res: Resultado, tema: Tema) -> Render | None:
    """Arma una gráfica. Devuelve None (con aviso) si los datos no dan."""
    ids = _series_disponibles(res, spec)
    if not ids:
        log.warning("gráfica %02d %s: omitida, sin datos para %s",
                    spec.numero, spec.id, ", ".join(spec.series))
        return None
    if len(ids) < len(spec.series):
        faltan = [i for i in spec.series if i not in ids]
        log.info("gráfica %02d %s: sin %s, se dibuja con el resto",
                 spec.numero, spec.id, ", ".join(faltan))

    entidades = res.entidades
    # El nombre del cultivo solo aplica a las tortas de un cultivo (#28-#31): en la
    # agrupada conviven cinco cultivos distintos y ninguno da nombre al conjunto.
    lleva_cultivo = spec.forma == "torta" and spec.series[0] in NOMBRE_CULTIVO
    titulo = _titulo_con_cultivo(res, spec) if lleva_cultivo else spec.titulo
    subtitulo = _subtitulo(res, ids)
    pie = _pie(res, ids)

    if spec.forma == "columnas":
        valores = [res.numero(ids[0], e) for e in entidades]
        fig = g.columnas(entidades, valores, tema, titulo, subtitulo, pie,
                         meta=spec.meta)
        enc, filas = _tabla(res, ids)

    elif spec.forma == "barras_ranking":
        valores = [res.numero(ids[0], e) for e in entidades]
        fig = g.barras_ranking(entidades, valores, tema, titulo, subtitulo, pie,
                               meta=spec.meta)
        enc, filas = _tabla(res, ids)

    elif spec.forma == "torta":
        valores = [res.numero(ids[0], e) for e in entidades]
        fig = g.torta(entidades, valores, tema, titulo, subtitulo, pie,
                      tamano=TAMANO_TORTA)
        enc, filas = _tabla(res, ids)

    elif spec.forma in ("columnas_agrupadas", "columnas_apiladas"):
        series = [
            (_etiqueta_corta(res, i), [res.numero(i, e) for e in entidades]) for i in ids
        ]
        if len(series) == 1:
            # Una sola serie no lleva leyenda: se dibuja como columnas (§7.5).
            fig = g.columnas(entidades, series[0][1], tema, titulo, subtitulo, pie)
        elif spec.forma == "columnas_agrupadas":
            fig = g.columnas_agrupadas(entidades, series, tema, titulo, subtitulo, pie)
        else:
            fig = g.columnas_apiladas(entidades, series, tema, titulo, subtitulo, pie)
        enc, filas = _tabla(res, ids)

    elif spec.forma == "lineas":
        id_indicador = ids[0]
        ultimo = res.ultimo_anio_con_dato(id_indicador)
        anios = sorted({
            a
            for e in entidades
            for a in res.serie_temporal(id_indicador, e)
            if ultimo is not None and a > ultimo - 10
        })
        series = []
        for e in entidades:
            serie = {a: v for a, v in res.serie_temporal(id_indicador, e).items() if a in anios}
            if serie:
                series.append((e, serie))
        if not series:
            log.warning("gráfica %02d %s: omitida, sin serie temporal", spec.numero, spec.id)
            return None
        omitidas = ""
        if len(series) > 8:
            # La paleta no se recicla (§7.1): se muestran ocho y se dice cuáles.
            series = series[:8]
            omitidas = " · se muestran las 8 primeras entidades"
            log.warning("gráfica %02d: más de 8 entidades, se grafican las 8 primeras",
                        spec.numero)
        subtitulo = f"{_unidad(res, ids)} · últimos {len(anios)} años con dato · {_fuentes(res, ids)}{omitidas}"
        fig = g.lineas(series, tema, titulo, subtitulo, pie, tamano=TAMANO_LINEAS)
        enc, filas = _tabla_series(res, id_indicador, anios)

    elif spec.forma == "panel":
        filas_grid, cols_grid = spec.grid or (2, 2)
        paneles = [
            (
                f"{_etiqueta_corta(res, i)}\n{res.unidad(i)}" if res.unidad(i)
                else _etiqueta_corta(res, i),
                entidades,
                [res.numero(i, e) for e in entidades],
                res.decimales.get(i, 1),
            )
            for i in ids
        ]
        subtitulo = (
            f"Cada panel conserva su escala: las unidades no son comparables entre sí"
            f" · dato de {_anios(res, ids)}"
        )
        fig = g.panel(paneles, tema, titulo, subtitulo, pie,
                      filas=filas_grid, columnas_grid=cols_grid, tamano=TAMANO_BASE)
        enc, filas = _tabla(res, ids)

    else:
        raise ValueError(f"forma desconocida: {spec.forma}")

    return Render(spec=spec, fig=fig, titulo=titulo, subtitulo=subtitulo, pie=pie,
                  encabezados=enc, filas=filas)


def generar(res: Resultado, tema: Tema, secciones: list[str] | None = None):
    """Itera `(spec, render_o_None)` armando **una gráfica a la vez**.

    Es un generador a propósito: quien consume guarda y cierra cada figura antes
    de pedir la siguiente, y así no hay 52 figuras abiertas al tiempo.
    """
    for spec in GRAFICAS:
        if secciones and spec.seccion not in secciones:
            continue
        yield spec, construir(spec, res, tema)
