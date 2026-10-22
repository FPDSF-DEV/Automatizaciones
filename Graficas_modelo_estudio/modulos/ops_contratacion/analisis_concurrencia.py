# -*- coding: utf-8 -*-
"""
Concurrencia, retencion y analisis por perfil sobre el consolidado OPS.

La unidad de medida es el MES CALENDARIO cubierto por un contrato, no el campo
'numero_meses' del reporte: ese campo es fraccionario (2.97, 5.67) y, cuando
una persona tiene dos contratos simultaneos, sumarlo cuenta dos veces el mismo
mes. Aqui cada contrato aporta el conjunto de meses que toca y los conjuntos se
unen, asi que un mes con tres contratos vigentes sigue siendo un mes.

Identidad: se agrupa por 'id_persona', no por la cedula digitada. Una cedula
con errata parte a la persona en dos y una cedula compartida funde a dos
personas en una; normalizar_nombres.py resuelve ambos casos y deja el documento
original como dato, no como llave.
"""
import numpy as np
import pandas as pd

# Un contrato que toca un mes por menos de este numero de dias no cuenta como
# mes trabajado; evita que un contrato que arranca el 30 de junio sume junio.
DIAS_MINIMOS_EN_MES = 5

# Umbrales de datos mal registrados (req. 3). Un contrato OPS de estos reportes
# dura entre unos dias y un anio; fuera de ese rango hay error de digitacion.
DURACION_MAX_DIAS = 400
VALOR_MES_MAXIMO = 60_000_000


def _meses_del_contrato(inicio, fin, dias_minimos=DIAS_MINIMOS_EN_MES):
    """
    Conjunto de meses (periodos mensuales) que cubre un contrato.

    Un contrato del 14/07 al 31/12 cubre julio..diciembre. Los meses extremos
    solo entran si el contrato los cubre al menos 'dias_minimos' dias, salvo que
    el contrato entero viva dentro de un unico mes (ahi siempre cuenta).
    """
    if pd.isna(inicio) or pd.isna(fin) or fin < inicio:
        return set()

    meses = pd.period_range(inicio, fin, freq="M")
    if len(meses) == 1:
        return {meses[0]}

    cubiertos = set()
    for mes in meses:
        desde = max(inicio, mes.start_time)
        hasta = min(fin, mes.end_time)
        if (hasta - desde).days + 1 >= dias_minimos:
            cubiertos.add(mes)
    return cubiertos


def _racha_maxima(meses):
    """Mayor cantidad de meses consecutivos dentro del conjunto."""
    if not meses:
        return 0
    ordenados = sorted(meses)
    mejor = actual = 1
    for previo, siguiente in zip(ordenados, ordenados[1:]):
        actual = actual + 1 if (siguiente - previo).n == 1 else 1
        mejor = max(mejor, actual)
    return mejor


def _dias_solapados(intervalos):
    """Dias en los que la persona tuvo dos o mas contratos vigentes a la vez."""
    solape, fin_previo = 0, None
    for inicio, fin in sorted(intervalos):
        if fin_previo is not None and inicio <= fin_previo:
            solape += (min(fin, fin_previo) - inicio).days + 1
        fin_previo = fin if fin_previo is None else max(fin_previo, fin)
    return solape


def marcar_anomalias(datos):
    """
    Anade la columna 'anomalia' con el motivo por el que una fila es dudosa
    (cadena vacia si esta bien). No borra filas: excluirlas o no es decision del
    usuario, asi que se reportan aqui y se filtran en la interfaz.
    """
    datos = datos.copy()
    duracion = (datos["f_final_contrato"] - datos["f_inicio_contrato"]).dt.days
    motivos = pd.Series("", index=datos.index, dtype=object)

    reglas = [
        (datos["f_inicio_contrato"].isna() | datos["f_final_contrato"].isna(),
         "fecha faltante"),
        (duracion < 0, "fecha final anterior a la inicial"),
        (duracion > DURACION_MAX_DIAS, f"duracion mayor a {DURACION_MAX_DIAS} dias"),
        (datos["valor_total"].isna() | (datos["valor_total"] <= 0),
         "valor total nulo o no positivo"),
        (datos["valor_mes"] > VALOR_MES_MAXIMO, "honorario mensual atipico"),
        (datos["documento"].astype(str).str.len() < 5, "documento invalido"),
    ]
    for condicion, motivo in reglas:
        condicion = condicion.fillna(False)
        motivos = motivos.mask(condicion & (motivos == ""), motivo)
        motivos = motivos.mask(condicion & (motivos != "") & (~motivos.str.contains(motivo, regex=False)),
                               motivos + "; " + motivo)

    datos["duracion_dias"] = duracion
    datos["anomalia"] = motivos
    return datos


def expandir_meses(datos):
    """
    Una fila por (contrato, mes cubierto). Es la base de todo lo demas: permite
    contar meses sin duplicar y filtrar por perfil sin perder el mes.
    """
    columnas = ("id_persona", "documento", "nombre_normalizado", "perfil", "nombre_area",
                "clase_persona", "anio", "valor_total", "consecutivo")
    filas = []
    for fila in datos.itertuples(index=False):
        for mes in _meses_del_contrato(fila.f_inicio_contrato, fila.f_final_contrato):
            registro = {c: getattr(fila, c, None) for c in columnas}
            registro["mes"] = mes
            filas.append(registro)

    expandido = pd.DataFrame(filas)
    if expandido.empty:
        return expandido
    expandido["mes_str"] = expandido["mes"].astype(str)
    return expandido


def ranking_concurrencia(datos, expandido=None):
    """
    Ranking de retencion por persona (req. 3).

    meses_totales    -> meses calendario distintos con al menos un contrato
    meses_continuos  -> la racha mas larga de meses consecutivos
    meses_declarados -> suma de numero_meses del reporte, para contrastar
    dias_solapados   -> dias con dos o mas contratos vigentes a la vez
    """
    if expandido is None:
        expandido = expandir_meses(datos)

    meses_por_doc = (expandido.groupby("id_persona")["mes"].apply(set)
                     if not expandido.empty else pd.Series(dtype=object))

    filas = []
    for doc, grupo in datos.groupby("id_persona"):
        meses = meses_por_doc.get(doc, set())
        intervalos = [
            (i, f) for i, f in zip(grupo["f_inicio_contrato"], grupo["f_final_contrato"])
            if pd.notna(i) and pd.notna(f) and f >= i
        ]
        nombres = grupo["nombre_normalizado"].dropna()
        clases = grupo["clase_persona"].dropna()
        perfiles = sorted(grupo["perfil"].dropna().unique())
        filas.append({
            "id_persona": doc,
            "documento": " | ".join(sorted(grupo["documento"].dropna().unique())),
            "nombre": nombres.iloc[0] if not nombres.empty else "",
            "clase_persona": clases.iloc[0] if not clases.empty else "",
            "meses_totales": len(meses),
            "meses_continuos": _racha_maxima(meses),
            "meses_declarados": round(float(grupo["meses"].sum(skipna=True)), 2),
            "contratos": len(grupo),
            "valor_total": float(grupo["valor_total"].sum(skipna=True)),
            "primer_mes": str(min(meses)) if meses else "",
            "ultimo_mes": str(max(meses)) if meses else "",
            "anios": int(grupo["anio"].nunique()),
            "dias_solapados": _dias_solapados(intervalos),
            "n_perfiles": len(perfiles),
            "perfiles": " | ".join(perfiles),
            "contratos_con_anomalia": int((grupo["anomalia"] != "").sum()) if "anomalia" in grupo else 0,
        })

    ranking = pd.DataFrame(filas)
    if ranking.empty:
        return ranking
    return (ranking.sort_values(["meses_totales", "meses_continuos", "valor_total"],
                                ascending=False)
            .reset_index(drop=True))


def analizar_perfil(datos, perfil, expandido=None):
    """
    Detalle de un perfil (req. 4): quienes lo ejercieron, cuantos meses cada
    uno, el total de meses contratados del perfil y el valor asociado.

    Ojo con los totales: 'meses_perfil' suma meses-persona (dos personas con 12
    meses cada una son 24), mientras que 'meses_calendario' son los meses
    distintos en que el perfil estuvo activo. Son preguntas diferentes.
    """
    if expandido is None:
        expandido = expandir_meses(datos)

    contratos = datos[datos["perfil"] == perfil]
    meses_perfil = (expandido[expandido["perfil"] == perfil]
                    if not expandido.empty else expandido)

    if contratos.empty:
        vacio = pd.DataFrame(columns=["id_persona", "documento", "nombre", "meses", "contratos", "valor_total"])
        return vacio, {"perfil": perfil, "personas": 0, "contratos": 0, "meses_perfil": 0,
                       "meses_calendario": 0, "valor_total": 0.0, "meses_max_persona": 0,
                       "valor_promedio_mes": 0.0}

    meses_por_persona = meses_perfil.groupby("id_persona")["mes"].nunique().rename("meses")
    agregado = contratos.groupby("id_persona").agg(
        nombre=("nombre_normalizado", "first"),
        documento=("documento", "first"),
        contratos=("consecutivo", "count"),
        valor_total=("valor_total", "sum"),
        primer_anio=("anio", "min"),
        ultimo_anio=("anio", "max"),
    )
    detalle = agregado.join(meses_por_persona, how="left").fillna({"meses": 0}).reset_index()
    detalle["meses"] = detalle["meses"].astype(int)
    detalle["valor_por_mes"] = np.where(detalle["meses"] > 0,
                                        detalle["valor_total"] / detalle["meses"], np.nan)
    detalle = (detalle.sort_values(["meses", "valor_total"], ascending=False)
               .reset_index(drop=True))

    total_meses = int(detalle["meses"].sum())
    total_valor = float(contratos["valor_total"].sum(skipna=True))
    kpis = {
        "perfil": perfil,
        "personas": int(detalle["id_persona"].nunique()),
        "contratos": int(len(contratos)),
        "meses_perfil": total_meses,
        "meses_calendario": int(meses_perfil["mes"].nunique()),
        "valor_total": total_valor,
        "meses_max_persona": int(detalle["meses"].max()) if not detalle.empty else 0,
        "valor_promedio_mes": total_valor / total_meses if total_meses else 0.0,
    }
    return detalle, kpis


def serie_mensual(expandido, perfil=None):
    """Personas distintas activas en cada mes calendario, para graficar."""
    base = expandido if perfil is None else expandido[expandido["perfil"] == perfil]
    if base.empty:
        return pd.DataFrame(columns=["mes_str", "personas"])
    return (base.groupby("mes_str")["id_persona"].nunique()
            .rename("personas").reset_index().sort_values("mes_str"))
