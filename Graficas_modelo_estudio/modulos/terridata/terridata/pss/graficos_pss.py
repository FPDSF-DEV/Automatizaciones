"""Los 32 constructores del inventario, uno por gráfico.

Cada constructor recibe `Datos` (ya resueltos) y el tema, y devuelve un `Render`
o `None` si sus datos no están. Ninguno levanta excepción por falta de datos: lo
que no se puede dibujar se omite con aviso y queda listado en el dashboard.
"""

from __future__ import annotations

import logging

from .. import graficas as g
from ..estilo import TAMANO_BASE, TAMANO_TORTA, Tema, formato_es
from .ambito import datos_piramide, municipios_de
from .catalogo_pss import Datos, Render, Spec, _rango_anios

log = logging.getLogger("terridata.pss")

FUENTE_TERRIDATA = "TerriData (DNP)"
FUENTE_ADRES = "ADRES — Base de Datos Única de Afiliados"
FUENTE_ODS = "TerriData (DNP) · Agenda 2030 ODS"
META_VACUNACION = 95.0


def _entidades_ambito(d: Datos) -> list[str]:
    return [d.ambito.nombre] if d.ambito.es_departamento else municipios_de(d.ambito)


def _nota_ambito(d: Datos) -> str:
    if d.ambito.es_departamento:
        return ""
    return f" · {d.ambito.calificador}"


def _dec(d: Datos, id_ind: str) -> int:
    return d.res.decimales.get(id_ind, 2)


def _fmt(valor, decimales=0):
    return formato_es(valor, decimales) if valor is not None else "—"


def _tabla_municipios(d: Datos, columnas: list[tuple[str, list]], anios: list | None = None):
    """Tabla de la vista de datos: una fila por municipio."""
    encabezados = ["Municipio"] + [c[0] for c in columnas]
    if anios is not None:
        encabezados.append("Año")
    filas = []
    for i, entidad in enumerate(d.municipios):
        fila = [entidad] + [str(c[1][i]) for c in columnas]
        if anios is not None:
            fila.append(str(anios[i] or "—"))
        filas.append(fila)
    return encabezados, filas


# --------------------------------------------------------------------------- 1 a 8


def g01_piramide(d: Datos, tema: Tema) -> Render | None:
    entidades = _entidades_ambito(d)
    p = datos_piramide(d.lectura.filas, entidades, d.anio)
    if not p.completa:
        log.warning("gráfico 1: no hay un año con los quinquenios completos de ambos sexos")
        return None

    total_h, total_m = sum(p.hombres), sum(p.mujeres)
    total = total_h + total_m
    titulo = f"Pirámide poblacional — {d.ambito.nombre}"
    subtitulo = (
        f"Personas por grupo quinquenal · dato {p.anio} · DANE"
        f" · hombres {formato_es(total_h / total * 100, 1)} %"
        f" · mujeres {formato_es(total_m / total * 100, 1)} %{_nota_ambito(d)}"
    )
    aviso = ""
    if p.anio != d.anio:
        aviso = (f" · la serie masculina por quinquenios no llega a {d.anio} en los "
                 f"archivos cargados, así que la pirámide es de {p.anio}")
    pie = f"Fuente: {FUENTE_TERRIDATA} — DANE, {p.dimension} · Dato {p.anio}{aviso}"

    fig = g.piramide(p.grupos, p.hombres, p.mujeres, tema, titulo, subtitulo, pie)
    encabezados = ["Grupo de edad", "Hombres", "Mujeres", "Total"]
    filas = [
        [grupo, _fmt(h), _fmt(m), _fmt((h or 0) + (m or 0))]
        for grupo, h, m in zip(p.grupos, p.hombres, p.mujeres)
    ]
    filas.append(["Total", _fmt(total_h), _fmt(total_m), _fmt(total)])
    return Render(ESPECIFICACIONES[0], fig, titulo, subtitulo, pie, encabezados, filas)


def g02_sexo(d: Datos, tema: Tema) -> Render | None:
    hombres, anio_h = d.dep_conteo("POB_H")
    mujeres, anio_m = d.dep_conteo("POB_M")
    if hombres is None or mujeres is None:
        return None
    total = hombres + mujeres
    diferencia = abs(mujeres - hombres)
    mayoria = "mujeres" if mujeres >= hombres else "hombres"

    titulo = f"Distribución de la población por sexo — {d.ambito.nombre}"
    subtitulo = (
        f"Personas · dato {_rango_anios([anio_h, anio_m])} · DANE (proyecciones PPED)"
        f" · {formato_es(diferencia, 0)} {mayoria} más{_nota_ambito(d)}"
    )
    pie = f"Fuente: {FUENTE_TERRIDATA} — DANE · Dato {_rango_anios([anio_h, anio_m])}"

    categorias = ["Hombres", "Mujeres"]
    valores = [hombres, mujeres]
    etiquetas = {
        c: f"{formato_es(v, 0)} · {formato_es(v / total * 100, 1)} %"
        for c, v in zip(categorias, valores)
    }
    fig = g.barras_ranking(categorias, valores, tema, titulo, subtitulo, pie,
                           decimales=0, orden="dado", etiquetas_valor=etiquetas)
    filas = [[c, formato_es(v, 0), f"{formato_es(v / total * 100, 1)} %"]
             for c, v in zip(categorias, valores)]
    filas.append(["Total", formato_es(total, 0), "100,0 %"])
    return Render(ESPECIFICACIONES[1], fig, titulo, subtitulo, pie,
                  ["Sexo", "Personas", "Participación"], filas)


def g03_urbano_rural(d: Datos, tema: Tema) -> Render | None:
    if d.ambito.es_departamento:
        urbana = d.urbana(d.ambito.nombre)
        rural = d.rural(d.ambito.nombre)
    else:
        urbana = d.dep_suma([d.urbana(e) for e in d.municipios])
        rural = d.dep_suma([d.rural(e) for e in d.municipios])
    if urbana is None or rural is None:
        return None
    total = urbana + rural

    titulo = f"Distribución urbano / rural — {d.ambito.nombre}"
    subtitulo = (
        f"Personas · dato {d.anio} · DANE (proyecciones PPED)"
        f" · {formato_es(rural / total * 100, 1)} % vive fuera de la cabecera{_nota_ambito(d)}"
    )
    pie = f"Fuente: {FUENTE_TERRIDATA} — DANE · Dato {d.anio}"

    categorias = ["Cabecera municipal", "Centros poblados y rural disperso"]
    valores = [urbana, rural]
    etiquetas = {
        c: f"{formato_es(v, 0)} · {formato_es(v / total * 100, 1)} %"
        for c, v in zip(categorias, valores)
    }
    fig = g.barras_ranking(categorias, valores, tema, titulo, subtitulo, pie,
                           decimales=0, orden="dado", etiquetas_valor=etiquetas)
    filas = [[c, formato_es(v, 0), f"{formato_es(v / total * 100, 1)} %"]
             for c, v in zip(categorias, valores)]
    filas.append(["Total", formato_es(total, 0), "100,0 %"])
    return Render(ESPECIFICACIONES[2], fig, titulo, subtitulo, pie,
                  ["Zona", "Personas", "Participación"], filas)


INDICADORES_SALUD = [
    ("FECUNDIDAD", "Fecundidad (x 1.000 MEF)"),
    ("MORT_MAT", "Mortalidad materna (x 100.000 NV)"),
    ("MORT_INF", "Mortalidad infantil (x 1.000 NV)"),
    ("MORT_GEN", "Mortalidad general (x 1.000 hab)"),
]


def g04_indicadores_salud(d: Datos, tema: Tema) -> Render | None:
    categorias, valores, anios, aportes = [], [], [], []
    for id_ind, etiqueta in INDICADORES_SALUD:
        valor, anio, aportan = d.dep_tasa(id_ind)
        categorias.append(etiqueta)
        valores.append(valor)
        anios.append(anio)
        aportes.append(aportan)
    if not any(v is not None for v in valores):
        return None

    titulo = f"Indicadores de salud — {d.ambito.nombre}"
    nota = "" if d.ambito.es_departamento else " · tasas promediadas por población"
    subtitulo = (
        f"Cada barra tiene su propia unidad, indicada en la etiqueta · "
        f"dato {_rango_anios(anios)} · DANE y MinSalud{nota}"
    )
    pie = f"Fuente: {FUENTE_TERRIDATA} — DANE (EEVV) y MinSalud · Dato {_rango_anios(anios)}"

    fig = g.columnas(categorias, valores, tema, titulo, subtitulo, pie, decimales=2)
    filas = [
        [etiqueta, _fmt(v, 2), str(a or "—"),
         "departamento" if d.ambito.es_departamento else f"{n} de {len(d.municipios)} municipios"]
        for (_, etiqueta), v, a, n in zip(INDICADORES_SALUD, valores, anios, aportes)
    ]
    return Render(ESPECIFICACIONES[3], fig, titulo, subtitulo, pie,
                  ["Indicador", "Valor", "Año", "Cobertura del dato"], filas)


def g05_vacunacion(d: Datos, tema: Tema) -> Render | None:
    valor, anio, _ = d.dep_tasa("VAC_PENTA")
    if valor is None:
        return None
    brecha = META_VACUNACION - valor

    titulo = f"Cobertura de vacunación pentavalente frente a la meta ODS 3 — {d.ambito.nombre}"
    subtitulo = (
        f"% de menores de 1 año · dato {anio} · MinSalud (PAI) · "
        f"brecha de {formato_es(brecha, 1)} puntos frente a la meta{_nota_ambito(d)}"
    )
    pie = f"Fuente: {FUENTE_TERRIDATA} — MinSalud, PAI · Dato {anio}"

    categorias = ["Cobertura alcanzada", "Meta ODS 3"]
    valores = [valor, META_VACUNACION]
    fig = g.columnas(categorias, valores, tema, titulo, subtitulo, pie, decimales=2)
    filas = [["Cobertura alcanzada", _fmt(valor, 2), str(anio or "—")],
             ["Meta ODS 3", formato_es(META_VACUNACION, 2), "2030"],
             ["Brecha", _fmt(brecha, 2), ""]]
    return Render(ESPECIFICACIONES[4], fig, titulo, subtitulo, pie,
                  ["Concepto", "%", "Año"], filas)


INDICADORES_VIOLENCIA = [
    ("T_VIF", "Violencia intrafamiliar"),
    ("T_INTER", "Violencia interpersonal"),
    ("T_HOMIC", "Homicidios"),
]


def g06_violencia(d: Datos, tema: Tema) -> Render | None:
    categorias, valores, anios = [], [], []
    for id_ind, etiqueta in INDICADORES_VIOLENCIA:
        valor, anio, _ = d.dep_tasa(id_ind)
        categorias.append(etiqueta)
        valores.append(valor)
        anios.append(anio)
    if not any(v is not None for v in valores):
        return None

    titulo = f"Indicadores de violencia — {d.ambito.nombre}"
    nota = "" if d.ambito.es_departamento else " · tasas promediadas por población"
    subtitulo = (f"Tasa por cada 100.000 habitantes · dato {_rango_anios(anios)} · "
                 f"Policía Nacional{nota}")
    pie = (f"Fuente: {FUENTE_TERRIDATA} — Policía Nacional · "
           f"Dato {_rango_anios(anios)}")

    fig = g.columnas(categorias, valores, tema, titulo, subtitulo, pie, decimales=2)
    filas = [[c, _fmt(v, 2), str(a or "—")] for c, v, a in zip(categorias, valores, anios)]
    return Render(ESPECIFICACIONES[5], fig, titulo, subtitulo, pie,
                  ["Tipo de violencia", "Tasa x 100.000 hab", "Año"], filas)


def g07_composicion_violencia(d: Datos, tema: Tema) -> Render | None:
    vif, anio_v, _ = d.dep_tasa("T_VIF")
    inter, anio_i, _ = d.dep_tasa("T_INTER")
    if vif is None or inter is None:
        return None
    total = vif + inter

    titulo = f"Composición de la violencia no homicida — {d.ambito.nombre}"
    subtitulo = (
        f"Peso de cada tipo dentro de la violencia no homicida · "
        f"dato {_rango_anios([anio_v, anio_i])} · Policía Nacional{_nota_ambito(d)}"
    )
    pie = (f"Fuente: {FUENTE_TERRIDATA} — Policía Nacional · "
           f"Dato {_rango_anios([anio_v, anio_i])}. Las porciones comparan dos tasas "
           "por cada 100.000 habitantes, no conteos de casos.")

    fig = g.torta(
        ["Intrafamiliar", "Interpersonal"], [vif, inter], tema, titulo, subtitulo, pie,
        decimales=2, tamano=TAMANO_TORTA, dona=True,
        centro=f"{formato_es(total, 0)}\nx 100.000 hab",
    )
    filas = [["Intrafamiliar", _fmt(vif, 2), f"{formato_es(vif / total * 100, 1)} %"],
             ["Interpersonal", _fmt(inter, 2), f"{formato_es(inter / total * 100, 1)} %"]]
    return Render(ESPECIFICACIONES[6], fig, titulo, subtitulo, pie,
                  ["Tipo", "Tasa x 100.000 hab", "Participación"], filas)


def g08_composicion_sgsss(d: Datos, tema: Tema) -> Render | None:
    afiliacion = d.afiliacion_departamento()
    if afiliacion is None:
        log.warning("gráfico 8: no hay fila del departamento en el Excel de afiliación")
        return None
    partes = [
        ("Contributivo", afiliacion.contributivo),
        ("Subsidiado", afiliacion.subsidiado),
        ("Excepción y especiales", afiliacion.excepcion),
    ]
    valores = [v for _, v in partes]
    if not any(v for v in valores):
        return None
    total = sum(v for v in valores if v)

    nombre = afiliacion.nombre.title()
    titulo = f"Composición de la afiliación al SGSSS — {nombre}"
    subtitulo = (
        f"Afiliados por régimen · corte {d.cobertura.corte} · ADRES · "
        f"{formato_es(total, 0)} afiliados sobre "
        f"{formato_es(afiliacion.poblacion, 0)} habitantes"
    )
    pie = (f"Fuente: {FUENTE_ADRES} · Corte {d.cobertura.corte}. "
           "Cifras del departamento completo, no del área de influencia.")

    fig = g.torta([p[0] for p in partes], valores, tema, titulo, subtitulo, pie,
                  decimales=0, tamano=TAMANO_TORTA)
    filas = [[nombre_parte, _fmt(v), f"{formato_es((v or 0) / total * 100, 1)} %"]
             for nombre_parte, v in partes]
    filas.append(["Total afiliados", _fmt(total), "100,0 %"])
    return Render(ESPECIFICACIONES[7], fig, titulo, subtitulo, pie,
                  ["Régimen", "Afiliados", "Participación"], filas)


# --------------------------------------------------------------------------- 9 a 12


def _afiliaciones(d: Datos):
    return [d.afiliacion_municipio(e) for e in d.municipios]


def g09_cobertura(d: Datos, tema: Tema) -> Render | None:
    filas_afil = _afiliaciones(d)
    valores = [a.cobertura_pct if a else None for a in filas_afil]
    if not any(v is not None for v in valores):
        return None

    titulo = "Cobertura de afiliación al SGSSS por municipio"
    subtitulo = (f"% de la población afiliada · corte {d.cobertura.corte} · ADRES · "
                 "la cobertura se topa en 100 %")
    pie = f"Fuente: {FUENTE_ADRES} · Corte {d.cobertura.corte}"

    fig = g.columnas(d.municipios, valores, tema, titulo, subtitulo, pie, decimales=2)
    encabezados, filas = _tabla_municipios(d, [
        ("Afiliados", [_fmt(a.afiliados) if a else "—" for a in filas_afil]),
        ("Población", [_fmt(a.poblacion) if a else "—" for a in filas_afil]),
        ("Cobertura (%)", [_fmt(v, 2) for v in valores]),
    ])
    return Render(ESPECIFICACIONES[8], fig, titulo, subtitulo, pie, encabezados, filas)


def g10_sin_afiliar(d: Datos, tema: Tema) -> Render | None:
    filas_afil = _afiliaciones(d)
    valores = [a.sin_afiliar_pct if a else None for a in filas_afil]
    if not any(v is not None for v in valores):
        return None
    sin_afiliar = [
        (a.poblacion - a.afiliados) if a and a.poblacion and a.afiliados
        and a.poblacion > a.afiliados else 0.0
        for a in filas_afil
    ]

    titulo = "Brecha de cobertura: población sin afiliar por municipio"
    subtitulo = (f"% de la población sin afiliación · corte {d.cobertura.corte} · ADRES · "
                 "complemento de la cobertura")
    pie = f"Fuente: {FUENTE_ADRES} · Corte {d.cobertura.corte}"

    fig = g.columnas(d.municipios, valores, tema, titulo, subtitulo, pie, decimales=2)
    encabezados, filas = _tabla_municipios(d, [
        ("Sin afiliar (%)", [_fmt(v, 2) for v in valores]),
        ("Personas sin afiliar (aprox.)", [_fmt(v) for v in sin_afiliar]),
    ])
    return Render(ESPECIFICACIONES[9], fig, titulo, subtitulo, pie, encabezados, filas)


def g11_poblacion_vs_afiliados(d: Datos, tema: Tema) -> Render | None:
    filas_afil = _afiliaciones(d)
    poblacion = [a.poblacion if a else None for a in filas_afil]
    afiliados = [a.afiliados if a else None for a in filas_afil]
    if not any(v is not None for v in afiliados):
        return None

    exceso = [
        e for e, p, af in zip(d.municipios, poblacion, afiliados)
        if p and af and af > p
    ]
    nota = ""
    if exceso:
        nota = (f" · en {', '.join(exceso)} los afiliados superan la población "
                "proyectada (población flotante y migración)")

    titulo = "Población frente a total de afiliados, por municipio"
    subtitulo = (f"Personas · población y afiliados del mismo corte · "
                 f"{d.cobertura.corte} · ADRES{nota}")
    pie = f"Fuente: {FUENTE_ADRES} · Corte {d.cobertura.corte}"

    fig = g.columnas_agrupadas(
        d.municipios,
        [("Población", poblacion), ("Total afiliados", afiliados)],
        tema, titulo, subtitulo, pie, decimales=0,
    )
    encabezados, filas = _tabla_municipios(d, [
        ("Población", [_fmt(v) for v in poblacion]),
        ("Total afiliados", [_fmt(v) for v in afiliados]),
        ("Diferencia", [_fmt((af - p) if af is not None and p is not None else None)
                        for p, af in zip(poblacion, afiliados)]),
    ])
    return Render(ESPECIFICACIONES[10], fig, titulo, subtitulo, pie, encabezados, filas)


def g12_sin_sisben(d: Datos, tema: Tema) -> Render | None:
    filas_afil = _afiliaciones(d)
    valores = [a.subsidiado_sin_sisben if a else None for a in filas_afil]
    if not any(v is not None for v in valores):
        return None
    total = sum(v for v in valores if v is not None)

    titulo = "Afiliados al régimen subsidiado sin encuesta SISBÉN IV"
    subtitulo = (f"Personas · corte {d.cobertura.corte} · ADRES · "
                 f"{formato_es(total, 0)} en el área de influencia")
    pie = (f"Fuente: {FUENTE_ADRES} · Corte {d.cobertura.corte}. "
           "Sin SISBÉN IV se pone en riesgo la continuidad del aseguramiento.")

    fig = g.columnas(d.municipios, valores, tema, titulo, subtitulo, pie, decimales=0)
    subsidiado = [a.subsidiado if a else None for a in filas_afil]
    encabezados, filas = _tabla_municipios(d, [
        ("Subsidiados sin SISBÉN IV", [_fmt(v) for v in valores]),
        ("Total subsidiado", [_fmt(v) for v in subsidiado]),
        ("Peso (%)", [_fmt((v / s * 100) if v is not None and s else None, 1)
                      for v, s in zip(valores, subsidiado)]),
    ])
    return Render(ESPECIFICACIONES[11], fig, titulo, subtitulo, pie, encabezados, filas)


# --------------------------------------------------------------------------- 13 a 15


def g13_poblacion_total(d: Datos, tema: Tema) -> Render | None:
    valores = [d.poblacion(e) for e in d.municipios]
    if not any(v is not None for v in valores):
        return None
    total = sum(v for v in valores if v is not None)

    titulo = f"Población total proyectada por municipio, {d.anio}"
    subtitulo = (f"Personas · dato {d.anio} · DANE (proyecciones PPED 2018-2042) · "
                 f"{formato_es(total, 0)} habitantes en el área de influencia")
    pie = f"Fuente: {FUENTE_TERRIDATA} — DANE, PPED 2018-2042 · Dato {d.anio}"

    fig = g.barras_ranking(d.municipios, valores, tema, titulo, subtitulo, pie,
                           decimales=0, orden="desc")
    encabezados, filas = _tabla_municipios(d, [
        ("Población", [_fmt(v) for v in valores]),
        ("Participación (%)", [_fmt((v / total * 100) if v is not None else None, 1)
                               for v in valores]),
    ])
    return Render(ESPECIFICACIONES[12], fig, titulo, subtitulo, pie, encabezados, filas)


def g14_poblacion_sexo(d: Datos, tema: Tema) -> Render | None:
    hombres = [d.valor("POB_H", e)[0] for e in d.municipios]
    mujeres = [d.valor("POB_M", e)[0] for e in d.municipios]
    if not any(v is not None for v in hombres):
        return None
    total_h = sum(v for v in hombres if v is not None)
    total_m = sum(v for v in mujeres if v is not None)
    total = total_h + total_m

    titulo = f"Población por sexo en cada municipio, {d.anio}"
    subtitulo = (f"Personas · dato {d.anio} · DANE (proyecciones PPED) · "
                 f"en el conjunto, {formato_es(total_m / total * 100, 1)} % son mujeres")
    pie = f"Fuente: {FUENTE_TERRIDATA} — DANE, PPED 2018-2042 · Dato {d.anio}"

    fig = g.barras_agrupadas_h(
        d.municipios, [("Hombres", hombres), ("Mujeres", mujeres)],
        tema, titulo, subtitulo, pie, decimales=0, orden="desc",
    )
    encabezados, filas = _tabla_municipios(d, [
        ("Hombres", [_fmt(v) for v in hombres]),
        ("Mujeres", [_fmt(v) for v in mujeres]),
        ("Total", [_fmt((h or 0) + (m or 0) if h or m else None)
                   for h, m in zip(hombres, mujeres)]),
    ])
    return Render(ESPECIFICACIONES[13], fig, titulo, subtitulo, pie, encabezados, filas)


def g15_urbano_rural_municipios(d: Datos, tema: Tema) -> Render | None:
    urbana = [d.urbana(e) for e in d.municipios]
    rural = [d.rural(e) for e in d.municipios]
    if not any(v is not None for v in urbana):
        return None
    total_r = sum(v for v in rural if v is not None)
    total = total_r + sum(v for v in urbana if v is not None)
    mas_rural = max(
        ((e, (r / ((u or 0) + r) * 100)) for e, u, r in zip(d.municipios, urbana, rural)
         if r and ((u or 0) + r) > 0),
        key=lambda p: p[1], default=None,
    )
    nota = ""
    if mas_rural:
        nota = f" · {mas_rural[0]} es el más rural con {formato_es(mas_rural[1], 1)} %"

    titulo = f"Población en cabecera y en zona rural por municipio, {d.anio}"
    subtitulo = (f"Personas · dato {d.anio} · DANE (proyecciones PPED) · "
                 f"{formato_es(total_r / total * 100, 1)} % del área vive fuera de la "
                 f"cabecera{nota}")
    pie = f"Fuente: {FUENTE_TERRIDATA} — DANE, PPED 2018-2042 · Dato {d.anio}"

    fig = g.barras_agrupadas_h(
        d.municipios,
        [("Cabecera municipal", urbana), ("Centros poblados y rural", rural)],
        tema, titulo, subtitulo, pie, decimales=0, orden="desc",
    )
    encabezados, filas = _tabla_municipios(d, [
        ("Cabecera", [_fmt(v) for v in urbana]),
        ("Centros poblados y rural", [_fmt(v) for v in rural]),
        ("% rural", [_fmt((r / ((u or 0) + r) * 100) if r and ((u or 0) + r) else None, 1)
                     for u, r in zip(urbana, rural)]),
    ])
    return Render(ESPECIFICACIONES[14], fig, titulo, subtitulo, pie, encabezados, filas)


# --------------------------------------------------------------------------- 16 a 32 (ODS)


def _constructor_ods(indice: int, id_ind: str, anio_pref: int, lectura_alta: str,
                     fuente_nota: str = "", orden: str = "desc"):
    """Fábrica de los 17 gráficos ODS: ranking horizontal de un indicador.

    `lectura_alta` explica cómo leer el indicador (si un valor alto es bueno o
    malo), porque en ODS 1, 10, 11, 13 y 16 el mejor desempeño es el valor bajo.
    """

    def constructor(d: Datos, tema: Tema) -> Render | None:
        valores, anios = d.valores(id_ind, anio_pref)
        if not any(v is not None for v in valores):
            log.warning("gráfico %d: sin datos para %s", indice + 1, id_ind)
            return None

        spec = ESPECIFICACIONES[indice]
        etiqueta = d.res.etiqueta(id_ind)
        unidad = d.res.unidad(id_ind)
        decimales = _dec(d, id_ind)

        presentes = [(e, v) for e, v in zip(d.municipios, valores) if v is not None]
        mejor = min(presentes, key=lambda p: p[1]) if "bajo" in lectura_alta else \
            max(presentes, key=lambda p: p[1])
        peor = max(presentes, key=lambda p: p[1]) if "bajo" in lectura_alta else \
            min(presentes, key=lambda p: p[1])

        titulo = f"{spec.titulo} — {etiqueta}"
        subtitulo = (
            f"{unidad} · dato {_rango_anios(anios)} · {lectura_alta} · "
            f"mejor {mejor[0]} ({formato_es(mejor[1], decimales)}) · "
            f"mayor reto {peor[0]} ({formato_es(peor[1], decimales)})"
        )
        pie = f"Fuente: {FUENTE_ODS} · Dato {_rango_anios(anios)}"
        if fuente_nota:
            pie = f"{pie}. {fuente_nota}"

        fig = g.barras_ranking(d.municipios, valores, tema, titulo, subtitulo, pie,
                               decimales=decimales, orden=orden)
        encabezados, filas = _tabla_municipios(
            d, [(f"{etiqueta} ({unidad})", [_fmt(v, decimales) for v in valores])],
            anios=anios,
        )
        return Render(spec, fig, titulo, subtitulo, pie, encabezados, filas)

    return constructor


# (número, id, título ODS, indicador, año del documento, cómo se lee, nota)
DEFINICION_ODS = [
    (16, "ods01_pobreza", "ODS 1 · Fin de la pobreza", "IPM", 2018,
     "un valor más bajo es mejor", ""),
    (17, "ods02_hambre", "ODS 2 · Hambre cero", "PAE", 2025,
     "un valor más alto es mejor", ""),
    (18, "ods03_salud", "ODS 3 · Salud y bienestar", "VAC_PENTA", 2025,
     "un valor más alto es mejor", "La meta ODS es 95 %."),
    (19, "ods04_educacion", "ODS 4 · Educación de calidad", "COB_NETA_EDU", 2024,
     "un valor más alto es mejor", ""),
    (20, "ods05_genero", "ODS 5 · Igualdad de género", "COTIZ_MUJERES", 2016,
     "un valor más alto es mejor", "La paridad estaría en 50 %."),
    (21, "ods06_agua", "ODS 6 · Agua limpia y saneamiento", "ACU_CENSO", 2018,
     "un valor más alto es mejor", ""),
    (22, "ods07_energia", "ODS 7 · Energía asequible", "ENER_RUR", 2019,
     "un valor más alto es mejor", ""),
    (23, "ods08_trabajo", "ODS 8 · Trabajo decente y crecimiento", "VA_PER_CAPITA", 2019,
     "un valor más alto es mejor", ""),
    (24, "ods09_infraestructura", "ODS 9 · Industria, innovación e infraestructura",
     "INTERNET", 2025, "un valor más alto es mejor", ""),
    (25, "ods10_desigualdades", "ODS 10 · Reducción de las desigualdades", "NBI", 2018,
     "un valor más bajo es mejor", ""),
    (26, "ods11_ciudades", "ODS 11 · Ciudades y comunidades sostenibles",
     "ICM_SOSTENIBILIDAD", 2024, "un valor más alto es mejor",
     "El documento original usa el Índice de Calidad de Vida Municipal, que no "
     "viene en las extracciones cargadas; aquí se usa el Índice de Sostenibilidad del ICM."),
    (27, "ods12_consumo", "ODS 12 · Producción y consumo responsables",
     "ICM_AMBIENTAL", 2024, "un valor más alto es mejor",
     "El documento original usa el Índice de circularidad ambiental, que no viene "
     "en las extracciones cargadas; aquí se usa el Índice de Cuidado ambiental del ICM."),
    (28, "ods13_clima", "ODS 13 · Acción por el clima", "VULNERABILIDAD", 2017,
     "un valor más bajo es mejor", ""),
    (29, "ods14_agua_vida", "ODS 14 · Vida submarina", "ALC_REC", 2021,
     "un valor más alto es mejor",
     "En un territorio andino sin costa se usa el saneamiento hídrico como proxy."),
    (30, "ods15_ecosistemas", "ODS 15 · Vida de ecosistemas terrestres", "SINAP", 2017,
     "un valor más alto es mejor", ""),
    (31, "ods16_paz", "ODS 16 · Paz, justicia e instituciones sólidas", "T_HOMIC", 2020,
     "un valor más bajo es mejor", ""),
    (32, "ods17_alianzas", "ODS 17 · Alianzas para lograr los objetivos",
     "ICM_INSTITUCIONAL", 2024, "un valor más alto es mejor", ""),
]


# --------------------------------------------------------------------------- especificaciones

ESPECIFICACIONES: list[Spec] = [
    Spec(1, "piramide_poblacional", "departamento", "Pirámide poblacional", g01_piramide),
    Spec(2, "distribucion_sexo", "departamento", "Distribución por sexo", g02_sexo),
    Spec(3, "distribucion_urbano_rural", "departamento", "Distribución urbano/rural",
         g03_urbano_rural),
    Spec(4, "indicadores_salud", "departamento", "Indicadores de salud",
         g04_indicadores_salud),
    Spec(5, "vacunacion_meta_ods", "departamento", "Vacunación frente a la meta ODS",
         g05_vacunacion),
    Spec(6, "violencia_tasas", "departamento", "Indicadores de violencia", g06_violencia),
    Spec(7, "violencia_composicion", "departamento", "Composición de la violencia",
         g07_composicion_violencia),
    Spec(8, "sgsss_composicion", "departamento", "Composición del SGSSS",
         g08_composicion_sgsss, fuente="ADRES"),
    Spec(9, "cobertura_sgsss", "aseguramiento", "Cobertura de afiliación", g09_cobertura,
         fuente="ADRES"),
    Spec(10, "brecha_sin_afiliar", "aseguramiento", "Población sin afiliar",
         g10_sin_afiliar, fuente="ADRES"),
    Spec(11, "poblacion_vs_afiliados", "aseguramiento", "Población frente a afiliados",
         g11_poblacion_vs_afiliados, fuente="ADRES"),
    Spec(12, "subsidiados_sin_sisben", "aseguramiento", "Subsidiados sin SISBÉN IV",
         g12_sin_sisben, fuente="ADRES"),
    Spec(13, "poblacion_total", "municipios", "Población total", g13_poblacion_total),
    Spec(14, "poblacion_por_sexo", "municipios", "Población por sexo", g14_poblacion_sexo),
    Spec(15, "poblacion_urbano_rural", "municipios", "Población urbano/rural",
         g15_urbano_rural_municipios),
]

for _numero, _id, _titulo, _ind, _anio, _lectura, _nota in DEFINICION_ODS:
    ESPECIFICACIONES.append(
        Spec(_numero, _id, "ods", _titulo,
             _constructor_ods(_numero - 1, _ind, _anio, _lectura, _nota))
    )

assert len(ESPECIFICACIONES) == 32, "el inventario define exactamente 32 gráficos"
assert [s.numero for s in ESPECIFICACIONES] == list(range(1, 33))


def generar(datos: Datos, tema: Tema, numeros: list[int] | None = None):
    """Itera `(spec, render_o_None)` armando un gráfico a la vez."""
    for spec in ESPECIFICACIONES:
        if numeros and spec.numero not in numeros:
            continue
        try:
            yield spec, spec.constructor(datos, tema)
        except Exception as error:      # un gráfico roto no puede tumbar los otros 31
            log.error("gráfico %02d %s: %s", spec.numero, spec.id, error, exc_info=True)
            yield spec, None
