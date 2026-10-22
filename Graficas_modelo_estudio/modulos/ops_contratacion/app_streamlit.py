# -*- coding: utf-8 -*-
"""
Interfaz web para el analisis de contratacion OPS.

Uso:
    streamlit run app_streamlit.py

Reutiliza el pipeline existente:
    analisis_ops.py          -> descubrimiento de archivos y consolidacion
    normalizar_nombres.py    -> identidad del contratista y nombre canonico
    analisis_concurrencia.py -> meses contratados, rachas y analisis por perfil
"""
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

from analisis_concurrencia import (analizar_perfil, expandir_meses,
                                   marcar_anomalias, ranking_concurrencia,
                                   serie_mensual)
from analisis_ops import (AZUL, SUPERFICIE, TINTA_2, carpeta_por_defecto,
                          consolidar, seleccionar_consolidados,
                          seleccionar_union)

st.set_page_config(page_title="Contratacion OPS", page_icon="📋", layout="wide")


# --------------------------------------------------------------------------
# Carga (cacheada: releer y normalizar 4.000+ contratos tarda varios segundos)
# --------------------------------------------------------------------------
@st.cache_data(show_spinner="Leyendo y normalizando los reportes...")
def cargar(ruta_carpeta, estrategia):
    """
    estrategia 'union'  -> une los cuatro trimestres y deduplica (recomendado)
    estrategia 'oct'    -> solo el consolidado anual, para poder contrastar
    """
    carpeta = Path(ruta_carpeta)
    conflictos = pd.DataFrame()

    if estrategia == "union":
        por_anio, informe, conflictos = seleccionar_union(carpeta)
        if not por_anio:
            return None
        archivos = informe.rename(columns={"archivo_origen": "archivo",
                                           "contratos_aportados": "contratos"})
    else:
        por_anio = seleccionar_consolidados(carpeta)
        if not por_anio:
            return None
        archivos = pd.DataFrame(
            [{"anio": a, "archivo": r.name, "contratos": len(d)} for a, (r, d) in por_anio.items()]
        )

    datos, auditoria, resumen = consolidar(por_anio)
    datos = marcar_anomalias(datos)
    expandido = expandir_meses(datos)
    return {
        "datos": datos,
        "expandido": expandido,
        "auditoria": auditoria,
        "resumen": resumen,
        "archivos": archivos,
        "conflictos": conflictos,
    }


def pesos(valor):
    """1234567890 -> $1.234,6 M (los montos OPS viven en millones)."""
    if pd.isna(valor):
        return "-"
    if abs(valor) >= 1e9:
        return f"${valor / 1e9:,.2f} mil M"
    return f"${valor / 1e6:,.1f} M"


def barras_top(df, campo_valor, campo_etiqueta, titulo, n=15):
    """Barras horizontales, serie unica: un solo color y sin leyenda."""
    top = df.nlargest(n, campo_valor)
    return (
        alt.Chart(top, title=titulo)
        .mark_bar(color=AZUL, cornerRadiusTopRight=4, cornerRadiusBottomRight=4, height=16)
        .encode(
            x=alt.X(f"{campo_valor}:Q", title=None, axis=alt.Axis(grid=True)),
            y=alt.Y(f"{campo_etiqueta}:N", sort="-x", title=None),
            tooltip=[alt.Tooltip(f"{campo_etiqueta}:N", title="Contratista"),
                     alt.Tooltip(f"{campo_valor}:Q", title="Meses", format=",")],
        )
        .properties(height=max(200, 26 * len(top)))
        .configure_view(strokeWidth=0, fill=SUPERFICIE)
        .configure_axis(labelColor=TINTA_2, titleColor=TINTA_2, domainColor="#dcdbd5",
                        tickColor="#dcdbd5", gridColor="#e8e7e1")
        .configure_title(anchor="start", fontSize=14)
    )


def linea_mensual(serie, titulo):
    """Personas activas mes a mes. Serie unica -> el titulo la nombra."""
    return (
        alt.Chart(serie, title=titulo)
        .mark_area(color=AZUL, opacity=0.18, line={"color": AZUL, "strokeWidth": 2},
                   interpolate="monotone")
        .encode(
            x=alt.X("mes_str:T", title=None),
            y=alt.Y("personas:Q", title=None),
            tooltip=[alt.Tooltip("mes_str:T", title="Mes", format="%Y-%m"),
                     alt.Tooltip("personas:Q", title="Personas activas")],
        )
        .properties(height=260)
        .configure_view(strokeWidth=0, fill=SUPERFICIE)
        .configure_axis(labelColor=TINTA_2, titleColor=TINTA_2, domainColor="#dcdbd5",
                        tickColor="#dcdbd5", gridColor="#e8e7e1")
        .configure_title(anchor="start", fontSize=14)
    )


# --------------------------------------------------------------------------
# Barra lateral: de donde se leen los datos y que se incluye
# --------------------------------------------------------------------------
st.sidebar.header("Origen de los datos")
ruta = st.sidebar.text_input("Carpeta con los reportes CSV", value=str(carpeta_por_defecto()))

FUENTES = {
    "union": "Union de los 4 trimestres (recomendado)",
    "oct": "Solo el consolidado oct-dic",
}
estrategia = st.sidebar.radio(
    "Que archivos usar",
    list(FUENTES),
    format_func=FUENTES.get,
    help="El reporte de oct-dic es acumulativo del anio, pero algunos contratos "
         "solo quedaron registrados en un trimestre previo. La union los recupera "
         "y deduplica, conservando la version mas reciente de cada contrato.",
)

if not Path(ruta).is_dir():
    st.title("Contratacion OPS")
    st.warning(f"No existe la carpeta `{ruta}`. Indica la ruta que contiene los CSV del reporte.")
    st.stop()

paquete = cargar(ruta, estrategia)
if paquete is None:
    st.title("Contratacion OPS")
    st.error("No se encontro ningun CSV con las columnas esperadas del reporte de contratacion externa.")
    st.stop()

datos, expandido = paquete["datos"], paquete["expandido"]

excluir = st.sidebar.checkbox(
    "Excluir contratos con datos dudosos",
    value=False,
    help="Fechas invertidas o faltantes, duraciones imposibles, valores no positivos "
         "u honorarios mensuales atipicos.",
)
if excluir:
    validos = datos["anomalia"] == ""
    datos = datos[validos]
    expandido = expandido[expandido["consecutivo"].isin(datos["consecutivo"])]

clases = sorted(datos["clase_persona"].dropna().unique())
clase = st.sidebar.multiselect("Clase de persona", clases, default=clases)
if clase and len(clase) < len(clases):
    datos = datos[datos["clase_persona"].isin(clase)]
    expandido = expandido[expandido["clase_persona"].isin(clase)]

anios = sorted(datos["anio"].dropna().unique())
rango = st.sidebar.select_slider("Años", options=anios, value=(anios[0], anios[-1])) if len(anios) > 1 else (anios[0], anios[0])
datos = datos[datos["anio"].between(*rango)]
expandido = expandido[expandido["anio"].between(*rango)]

st.sidebar.divider()
st.sidebar.caption("Archivos usados y cuantos contratos aporto cada uno")
st.sidebar.dataframe(paquete["archivos"], hide_index=True, width="stretch")

if datos.empty:
    st.title("Contratacion OPS")
    st.warning("Los filtros no dejaron ningun contrato.")
    st.stop()

ranking = ranking_concurrencia(datos, expandido)

# --------------------------------------------------------------------------
# Encabezado
# --------------------------------------------------------------------------
st.title("Contratacion OPS")
st.caption(
    f"{len(datos):,} contratos · {datos['id_persona'].nunique():,} contratistas · "
    f"{rango[0]}–{rango[1]} · identidad resuelta por cedula y nombre"
)

k1, k2, k3, k4 = st.columns(4)
k1.metric("Contratos", f"{len(datos):,}")
k2.metric("Contratistas", f"{datos['id_persona'].nunique():,}")
k3.metric("Valor contratado", pesos(datos["valor_total"].sum()))
k4.metric("Meses cubiertos", f"{expandido['mes'].nunique():,}")

tab_ranking, tab_perfil, tab_calidad = st.tabs(
    ["Concurrencia y retencion", "Analisis por perfil", "Calidad de los datos"]
)

# --------------------------------------------------------------------------
# 1. Concurrencia y retencion
# --------------------------------------------------------------------------
with tab_ranking:
    meses_posibles = expandido["mes"].nunique()
    completos = int((ranking["meses_totales"] >= meses_posibles).sum())

    c1, c2, c3 = st.columns(3)
    c1.metric("Meses del periodo", f"{meses_posibles}")
    c2.metric("Con el periodo completo", f"{completos}",
              help=f"Personas con los {meses_posibles} meses contratados.")
    c3.metric("Mediana de meses por persona", f"{ranking['meses_totales'].median():.0f}")

    st.info(
        "**meses_totales** son meses calendario distintos con al menos un contrato vigente; "
        "**meses_continuos** es la racha mas larga sin interrupcion. "
        "**meses_declarados** suma el campo `numero_meses` del reporte: cuando supera a "
        "meses_totales, la persona tuvo contratos simultaneos (ver `dias_solapados`).",
        icon="ℹ️",
    )

    minimo = st.slider("Mostrar solo quienes superen N meses contratados", 0,
                       int(ranking["meses_totales"].max()), 0)
    vista = ranking[ranking["meses_totales"] >= minimo]

    st.altair_chart(
        barras_top(vista, "meses_totales", "nombre", "Mayor tiempo contratado (meses)"),
        width="stretch",
    )

    st.dataframe(
        vista[["nombre", "documento", "clase_persona", "meses_totales", "meses_continuos",
               "meses_declarados", "contratos", "valor_total", "primer_mes", "ultimo_mes",
               "dias_solapados", "n_perfiles", "perfiles"]],
        hide_index=True, width="stretch",
        column_config={
            "valor_total": st.column_config.NumberColumn("Valor total", format="$ %.0f"),
            "meses_totales": st.column_config.NumberColumn("Meses totales"),
            "meses_continuos": st.column_config.NumberColumn("Meses continuos"),
            "dias_solapados": st.column_config.NumberColumn("Dias solapados"),
        },
    )
    st.download_button("Descargar ranking (CSV)",
                       vista.to_csv(index=False).encode("utf-8-sig"),
                       "ranking_concurrencia.csv", "text/csv")

    st.altair_chart(
        linea_mensual(serie_mensual(expandido), "Contratistas activos por mes"),
        width="stretch",
    )

# --------------------------------------------------------------------------
# 2. Analisis por perfil
# --------------------------------------------------------------------------
with tab_perfil:
    perfiles = sorted(datos["perfil"].dropna().unique())
    perfil = st.selectbox("Perfil o cargo", perfiles,
                          index=perfiles.index("Medicina General") if "Medicina General" in perfiles else 0)

    detalle, kpis = analizar_perfil(datos, perfil, expandido)

    p1, p2, p3, p4 = st.columns(4)
    p1.metric("Meses contratados (total)", f"{kpis['meses_perfil']:,}",
              help="Suma de meses-persona: dos personas con 12 meses cada una son 24.")
    p2.metric("Valor total del perfil", pesos(kpis["valor_total"]))
    p3.metric("Personas", f"{kpis['personas']:,}")
    p4.metric("Costo por mes-persona", pesos(kpis["valor_promedio_mes"]))

    st.caption(
        f"{kpis['contratos']:,} contratos · el perfil estuvo activo en "
        f"{kpis['meses_calendario']} meses calendario · el maximo individual es "
        f"{kpis['meses_max_persona']} meses."
    )

    st.dataframe(
        detalle[["nombre", "documento", "meses", "contratos", "valor_total",
                 "valor_por_mes", "primer_anio", "ultimo_anio"]],
        hide_index=True, width="stretch",
        column_config={
            "meses": st.column_config.NumberColumn("Meses contratados"),
            "valor_total": st.column_config.NumberColumn("Valor total", format="$ %.0f"),
            "valor_por_mes": st.column_config.NumberColumn("Valor por mes", format="$ %.0f"),
        },
    )
    st.download_button("Descargar detalle del perfil (CSV)",
                       detalle.to_csv(index=False).encode("utf-8-sig"),
                       f"perfil_{perfil}.csv".replace(" ", "_"), "text/csv")

    izq, der = st.columns(2)
    with izq:
        st.altair_chart(barras_top(detalle, "meses", "nombre", f"{perfil}: meses por persona", n=12),
                        width="stretch")
    with der:
        st.altair_chart(linea_mensual(serie_mensual(expandido, perfil), f"{perfil}: personas activas por mes"),
                        width="stretch")

# --------------------------------------------------------------------------
# 3. Calidad de los datos
# --------------------------------------------------------------------------
with tab_calidad:
    st.subheader("De donde salio cada contrato")
    recuperados = paquete["archivos"][
        ~paquete["archivos"]["archivo"].str.contains("octubre-dic", case=False, na=False)
    ]
    if estrategia == "union" and not recuperados.empty:
        st.caption(
            f"{int(recuperados['contratos'].sum())} contratos no quedaron en el consolidado "
            "de oct-dic y se recuperaron de un trimestre previo. Sin la union, estos "
            "contratos y su valor no aparecerian en ningun calculo."
        )
        st.dataframe(recuperados, hide_index=True, width="stretch")
    elif estrategia == "union":
        st.success("Todos los contratos estaban en los consolidados de oct-dic.")
    else:
        st.warning(
            "Estas viendo solo los consolidados de oct-dic. Cambia la fuente en la "
            "barra lateral para incluir los contratos que solo existen en trimestres previos.",
            icon="⚠️",
        )

    conflictos = paquete["conflictos"]
    if not conflictos.empty:
        st.subheader("Contratos corregidos entre extracciones")
        st.caption(
            f"{len(conflictos):,} contratos aparecen en dos extracciones con distinta fecha "
            "final o distinto valor: son prorrogas y correcciones. Se conserva siempre la "
            "version mas reciente, que suele ser el valor finalmente ejecutado."
        )
        st.dataframe(conflictos, hide_index=True, width="stretch")

    st.subheader("Contratos con datos dudosos")
    dudosos = paquete["datos"][paquete["datos"]["anomalia"] != ""]
    if dudosos.empty:
        st.success("Ningun contrato disparo las reglas de validacion.")
    else:
        st.dataframe(dudosos["anomalia"].value_counts().rename_axis("motivo").reset_index(name="contratos"),
                     hide_index=True, width="stretch")
        st.dataframe(
            dudosos[["anio", "nombre_normalizado", "documento", "perfil", "f_inicio_contrato",
                     "f_final_contrato", "duracion_dias", "valor_total", "valor_mes", "anomalia"]],
            hide_index=True, width="stretch",
        )

    st.subheader("Contratos simultaneos")
    solapados = ranking[ranking["dias_solapados"] > 0]
    st.caption(
        f"{len(solapados):,} personas tuvieron dos o mas contratos vigentes el mismo dia. "
        "No es necesariamente un error (un mismo profesional puede tener dos perfiles), "
        "pero explica por que `meses_declarados` supera a `meses_totales`."
    )
    st.dataframe(
        solapados[["nombre", "documento", "dias_solapados", "meses_totales",
                   "meses_declarados", "contratos", "perfiles"]],
        hide_index=True, width="stretch",
    )

    st.subheader("Identidad de los contratistas")
    resumen = paquete["resumen"]
    i1, i2, i3 = st.columns(3)
    i1.metric("Cedulas con errata fusionadas", f"{len(resumen['fusiones']):,}",
              help="Mismo nombre y cedulas a distancia de edicion <= 2: la misma "
                   "persona digitada dos veces, que antes se contaba como dos.")
    i2.metric("Cedulas separadas", f"{len(resumen['separadas']):,}",
              help="Una cedula usada para dos personas distintas; las filas ajenas "
                   "pasan a una identidad propia en vez de sumarle meses a otro.")
    i3.metric("Homonimos sin fusionar", f"{len(resumen['homonimos']):,}",
              help="Mismo nombre pero cedulas muy distintas: se dejan separados "
                   "porque pueden ser dos personas reales. Revisalos a mano.")

    if resumen["fusiones"]:
        st.caption("**Cedulas fusionadas** — la misma persona aparecia con dos documentos.")
        st.dataframe(pd.DataFrame(resumen["fusiones"]), hide_index=True, width="stretch")
    if resumen["separadas"]:
        st.caption("**Cedulas separadas** — contratos de otra persona bajo el mismo documento.")
        st.dataframe(pd.DataFrame(resumen["separadas"]), hide_index=True, width="stretch")
    if resumen["homonimos"]:
        st.caption("**Homonimos** — mismo nombre, cedulas sin parecido. Requieren revision manual.")
        st.dataframe(pd.DataFrame(resumen["homonimos"]), hide_index=True, width="stretch")

    st.subheader("Grafias del nombre")
    st.caption(
        f"{resumen['invertidos']:,} nombres se reordenaron de APELLIDOS NOMBRES a "
        "NOMBRES APELLIDOS. La tabla lista los documentos que aparecieron con mas de "
        "una grafia; `revisar = SI` marca los casos donde una variante no comparte "
        "ninguna palabra con el nombre elegido."
    )
    auditoria = paquete["auditoria"]
    if auditoria.empty:
        st.success("Cada documento aparecio siempre con la misma grafia.")
    else:
        st.dataframe(auditoria, hide_index=True, width="stretch")
