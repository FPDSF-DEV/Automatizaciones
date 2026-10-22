# -*- coding: utf-8 -*-
"""
Pipeline de analisis de contratacion OPS.

Uso:
    python analisis_ops.py      # lee DATA/SIHO/.../Consultas_Detalladas/Reporte_Contratacion_Externa_desde_2020
                                # y escribe SALIDAS/ops_contratacion
    python analisis_ops.py --carpeta "OPS 2026" --salida resultados

Que hace:
  1. Recorre la carpeta buscando los CSV del reporte de contratacion externa.
  2. Por cada anio elige el reporte consolidado: el archivo que cubre mas meses
     del anio (los trimestrales son acumulativos, asi que el de oct-dic contiene
     todo el anio; la deteccion es por contenido, no por nombre de archivo).
  3. Normaliza nombres y resuelve la identidad de cada contratista.
  4. Escribe el consolidado normalizado, tablas de resumen y las graficas.
"""
import argparse
import re
import sys
from pathlib import Path

import pandas as pd

from normalizar_nombres import normalizar

# Las graficas usan el sistema de diseno de terridata (paleta, tipografia, maqueta),
# el mismo de los modulos terridata y pss.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "terridata"))
from terridata import graficas as g  # noqa: E402
from terridata.estilo import CLARO, TAMANO_BASE, formato_es  # noqa: E402

# --- Rutas del proyecto unificado -------------------------------------------
RAIZ_PROYECTO = Path(__file__).resolve().parents[2]
CARPETA_REPORTE = "Reporte_Contratacion_Externa_desde_2020"
SALIDA_POR_DEFECTO = RAIZ_PROYECTO / "SALIDAS" / "ops_contratacion"


def carpeta_por_defecto():
    """El reporte de contratacion dentro de DATA/SIHO (estructura de SJDC_SIHO):
    <SIHO>/Consultas_Detalladas/Reporte_Contratacion_Externa_desde_2020/."""
    siho = RAIZ_PROYECTO / "DATA" / "SIHO"
    halladas = sorted(siho.glob(f"**/Consultas_Detalladas/{CARPETA_REPORTE}"))
    return halladas[0] if len(halladas) == 1 else siho

# --- Tema de las graficas (lo usa tambien la app de streamlit) --------------
TEMA = CLARO
AZUL = TEMA.color(1)
SUPERFICIE = TEMA.superficie
TINTA_2 = TEMA.texto_secundario
PIE = "Fuente: SIHO — Reporte de contratación externa (consolidado de cada año)"

COLUMNAS_ESPERADAS = {
    "nombres_apellidos", "numero_cedula", "valor_total_contrato",
    "fecha_inicio_contrato", "perfil", "nombre_area", "clase_persona",
}


# --------------------------------------------------------------------------
# 1. Descubrimiento y seleccion de archivos
# --------------------------------------------------------------------------
def leer_csv(ruta):
    """Lee el CSV probando los encodings tipicos de estos reportes."""
    for enc in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            return pd.read_csv(ruta, dtype=str, encoding=enc)
        except UnicodeDecodeError:
            continue
    raise UnicodeDecodeError(f"No se pudo decodificar {ruta}")


def anio_de(df, ruta):
    """Anio del reporte: el mas frecuente en fecha_inicio, o el del nombre."""
    fechas = pd.to_datetime(
        df.get("fecha_inicio_contrato"), dayfirst=True, errors="coerce", format="mixed"
    )
    if fechas.notna().any():
        return int(fechas.dt.year.mode().iloc[0])
    hallados = re.findall(r"(20\d{2})", f"{ruta.parent.name} {ruta.name}")
    return int(hallados[-1]) if hallados else None


def seleccionar_consolidados(carpeta):
    """
    Devuelve {anio: (ruta, df)} quedandose, por anio, con el reporte que cubre
    mas meses. Los reportes trimestrales son acumulativos del anio en curso,
    asi que el mas amplio es el consolidado anual.
    """
    candidatos = {}
    descartados = []
    for ruta in sorted(carpeta.rglob("*.csv")):
        try:
            df = leer_csv(ruta)
        except Exception as exc:                       # archivo ilegible o ajeno
            descartados.append((ruta, f"no se pudo leer: {exc}"))
            continue
        faltantes = COLUMNAS_ESPERADAS - set(df.columns)
        if faltantes:
            descartados.append((ruta, f"faltan columnas: {sorted(faltantes)}"))
            continue

        anio = anio_de(df, ruta)
        if anio is None:
            descartados.append((ruta, "sin anio identificable"))
            continue

        fechas = pd.to_datetime(
            df["fecha_inicio_contrato"], dayfirst=True, errors="coerce", format="mixed"
        )
        cobertura = fechas[fechas.dt.year == anio].dt.month.nunique()
        puntaje = (cobertura, len(df))
        if anio not in candidatos or puntaje > candidatos[anio][0]:
            candidatos[anio] = (puntaje, ruta, df)

    for ruta, motivo in descartados:
        print(f"  ! omitido {ruta.name}: {motivo}")
    return {a: (r, d) for a, (_, r, d) in sorted(candidatos.items())}


# --------------------------------------------------------------------------
# 1b. Union de los cuatro trimestres
# --------------------------------------------------------------------------
# El reporte de oct-dic es acumulativo del anio, pero no siempre completo: hay
# contratos que aparecen en un trimestre previo y no quedaron en el consolidado
# (35 en estos datos, $278 M). Por eso se unen los cuatro y se deduplica.
#
# El problema es que no hay identificador estable de contrato:
#   - 'consecutivo' se regenera en cada extraccion (cero coincidencias entre
#     trimestres, asi que no sirve para reconciliar)
#   - 'numero_contrato' se repite entre personas y dentro del mismo anio
#     (el contrato "2" lo comparten 94 personas en 2024); es un numero de lote
#
# La llave usada es documento + numero_contrato + fecha de inicio. Se elige la
# fecha de INICIO y no la final porque una prorroga cambia la final: si la llave
# la incluyera, el contrato prorrogado contaria dos veces.
LLAVE_CONTRATO = ["anio", "documento", "contrato_norm", "fecha_inicio_contrato"]


def _recencia(df, anio, ruta):
    """
    Que tan tardia es una extraccion. Gana la que alcanza a ver el mes mas
    avanzado del anio; se mide por contenido, con el nombre del archivo solo
    como respaldo si las fechas no sirven.
    """
    fechas = pd.to_datetime(df.get("fecha_inicio_contrato"), dayfirst=True,
                            errors="coerce", format="mixed")
    del_anio = fechas[fechas.dt.year == anio]
    if not del_anio.empty:
        return (int(del_anio.dt.month.max()), len(df))

    orden = {"enero-mar": 3, "abril-jun": 6, "julio-sep": 9, "octubre-dic": 12}
    for etiqueta, mes in orden.items():
        if etiqueta in ruta.name.lower():
            return (mes, len(df))
    return (0, len(df))


def _claves(df):
    """Columnas auxiliares de la llave de contrato."""
    df = df.copy()
    df["documento"] = df["numero_cedula"].astype(str).str.replace(r"\D", "", regex=True)
    df["contrato_norm"] = (df["numero_contrato"].astype(str).str.strip()
                           .str.lstrip("0").replace("", "0"))
    return df


def seleccionar_union(carpeta):
    """
    Une todos los reportes de cada anio y deduplica por LLAVE_CONTRATO,
    conservando la version de la extraccion mas reciente.

    Devuelve (por_anio, informe, conflictos):
      por_anio    -> {anio: DataFrame deduplicado}
      informe     -> que aporto cada archivo y cuantas filas eran exclusivas
      conflictos  -> contratos cuya fecha final o valor cambio entre extracciones
                     (prorrogas y correcciones); se conserva la version reciente
    """
    por_archivo = []
    descartados = []
    for ruta in sorted(carpeta.rglob("*.csv")):
        try:
            df = leer_csv(ruta)
        except Exception as exc:
            descartados.append((ruta, f"no se pudo leer: {exc}"))
            continue
        faltantes = COLUMNAS_ESPERADAS - set(df.columns)
        if faltantes:
            descartados.append((ruta, f"faltan columnas: {sorted(faltantes)}"))
            continue
        anio = anio_de(df, ruta)
        if anio is None:
            descartados.append((ruta, "sin anio identificable"))
            continue

        df = _claves(df)
        df["anio"] = anio
        df["archivo_origen"] = ruta.name
        df["_recencia"] = _recencia(df, anio, ruta)[0]
        por_archivo.append(df)

    for ruta, motivo in descartados:
        print(f"  ! omitido {ruta.name}: {motivo}")
    if not por_archivo:
        return {}, pd.DataFrame(), pd.DataFrame()

    todo = pd.concat(por_archivo, ignore_index=True)
    # La extraccion mas reciente queda de ultima, para que keep='last' la elija.
    todo = todo.sort_values(["_recencia", "archivo_origen"], kind="stable")

    # Conflictos: misma llave con fecha final o valor distintos entre archivos.
    conflictos = _detectar_conflictos(todo)

    union = todo.drop_duplicates(subset=LLAVE_CONTRATO, keep="last")

    informe = (union.groupby(["anio", "archivo_origen"])
               .size().rename("contratos_aportados").reset_index()
               .sort_values(["anio", "archivo_origen"]))

    por_anio = {int(a): g.drop(columns=["_recencia"]).reset_index(drop=True)
                for a, g in union.groupby("anio")}
    return dict(sorted(por_anio.items())), informe, conflictos


def _detectar_conflictos(todo):
    """
    Contratos que aparecen en varias extracciones con fecha final o valor
    distintos. No son errores: son prorrogas o correcciones. Se reportan para
    que quede claro por que un contrato cambio de duracion o de monto.
    """
    repetidos = todo[todo.duplicated(LLAVE_CONTRATO, keep=False)]
    filas = []
    for llave, grupo in repetidos.groupby(LLAVE_CONTRATO, sort=False):
        if grupo["fecha_final_contrato"].nunique() < 2 and \
           grupo["valor_total_contrato"].nunique() < 2:
            continue                                   # fila identica repetida
        grupo = grupo.sort_values("_recencia")
        previo, vigente = grupo.iloc[0], grupo.iloc[-1]
        filas.append({
            "anio": llave[0],
            "documento": llave[1],
            "nombre": vigente["nombres_apellidos"],
            "perfil": vigente.get("perfil", ""),
            "fecha_inicio": llave[3],
            "fin_previo": previo["fecha_final_contrato"],
            "fin_vigente": vigente["fecha_final_contrato"],
            "valor_previo": previo["valor_total_contrato"],
            "valor_vigente": vigente["valor_total_contrato"],
            "archivo_previo": previo["archivo_origen"],
            "archivo_vigente": vigente["archivo_origen"],
        })
    return pd.DataFrame(filas)


# --------------------------------------------------------------------------
# 2. Consolidacion y normalizacion
# --------------------------------------------------------------------------
def consolidar(por_anio):
    """
    por_anio acepta {anio: DataFrame} (union) o {anio: (ruta, DataFrame)}
    (un solo consolidado por anio), para no romper el uso anterior.
    """
    partes = []
    for anio, valor in por_anio.items():
        if isinstance(valor, tuple):
            ruta, df = valor
            df = df.copy()
            df["archivo_origen"] = ruta.name
        else:
            df = valor.copy()
        df["anio"] = anio
        partes.append(df)
    datos = pd.concat(partes, ignore_index=True)

    datos["documento"] = datos["numero_cedula"].astype(str).str.replace(r"\D", "", regex=True)
    datos["valor_total"] = pd.to_numeric(datos["valor_total_contrato"], errors="coerce")
    datos["valor_mes"] = pd.to_numeric(datos.get("valor_honorarios_mes"), errors="coerce")
    datos["meses"] = pd.to_numeric(datos.get("numero_meses"), errors="coerce")
    for col in ("fecha_inicio_contrato", "fecha_final_contrato"):
        datos[col.replace("fecha_", "f_")] = pd.to_datetime(
            datos[col], dayfirst=True, errors="coerce", format="mixed"
        )
    datos["mes_inicio"] = datos["f_inicio_contrato"].dt.month

    ids, nombres, reporte, resumen = normalizar(datos.to_dict("records"))
    # id_persona, no documento: una cedula con errata parte a la persona en dos
    # y una cedula compartida funde a dos personas en una. Ver normalizar().
    datos["id_persona"] = ids
    datos["nombre_normalizado"] = nombres
    return datos, pd.DataFrame(reporte), resumen


# --------------------------------------------------------------------------
# 3. Graficas
# --------------------------------------------------------------------------
def _millones(valor):
    if abs(valor) >= 1e9:
        return f"$ {formato_es(valor / 1e9, 1)} mil M"
    return f"$ {formato_es(valor / 1e6, 0)} M"


def _guardar(fig, destino, nombre):
    g.guardar(fig, destino / nombre, formatos=("png",))
    g.cerrar(fig)
    print(f"  grafica: {nombre}.png")


def graficar(datos, destino):
    # --- Contratos por anio ---
    por_anio = datos.groupby("anio").agg(
        contratos=("consecutivo", "count"),
        valor=("valor_total", "sum"),
        personas=("id_persona", "nunique"),
    ).reset_index()
    anios = [str(a) for a in por_anio["anio"]]

    fig = g.columnas(anios, por_anio["contratos"].tolist(), TEMA,
                     "Contratos OPS suscritos por año",
                     "Conteo de contratos en el reporte consolidado de cada año", PIE,
                     decimales=0)
    _guardar(fig, destino, "01_contratos_por_anio")

    # --- Valor contratado por anio ---
    fig = g.columnas(anios, (por_anio["valor"] / 1e6).tolist(), TEMA,
                     "Valor total contratado por año",
                     "Millones de pesos corrientes · suma de valor_total_contrato", PIE,
                     decimales=0)
    _guardar(fig, destino, "02_valor_por_anio")

    # --- Personas distintas por anio ---
    fig = g.lineas([("Contratistas", dict(zip(por_anio["anio"].astype(int),
                                              por_anio["personas"].astype(float))))],
                   TEMA, "Contratistas distintos por año",
                   "Documentos únicos tras normalizar los nombres", PIE,
                   decimales=0, tamano=TAMANO_BASE, etiquetas_puntos=True)
    _guardar(fig, destino, "03_contratistas_por_anio")

    # --- Valor por area y anio (apilado) ---
    areas = datos.pivot_table(index="anio", columns="nombre_area",
                              values="valor_total", aggfunc="sum").fillna(0)
    fig = g.columnas_apiladas(
        [str(a) for a in areas.index],
        [(str(col), (areas[col] / 1e6).tolist()) for col in areas.columns],
        TEMA, "Valor contratado por área y año",
        "Millones de pesos corrientes · apoyo administrativo frente a operativo asistencial",
        PIE, decimales=0)
    _guardar(fig, destino, "04_valor_por_area")

    # --- Valor por clase de persona y anio (apilado) ---
    clases = datos.pivot_table(index="anio", columns="clase_persona",
                               values="valor_total", aggfunc="sum").fillna(0)
    fig = g.columnas_apiladas(
        [str(a) for a in clases.index],
        [(str(col), (clases[col] / 1e6).tolist()) for col in clases.columns],
        TEMA, "Valor contratado por clase de persona",
        "Millones de pesos corrientes · personas naturales frente a jurídicas",
        PIE, decimales=0)
    _guardar(fig, destino, "05_valor_por_clase_persona")

    # --- Top perfiles ---
    perfiles = (datos.groupby("perfil")["valor_total"].sum()
                .sort_values(ascending=False).head(15))
    nombres = [str(p) for p in perfiles.index]
    fig = g.barras_ranking(
        nombres, perfiles.tolist(), TEMA,
        "Perfiles con mayor valor contratado",
        "Millones de pesos · acumulado de todos los años del reporte · top 15", PIE,
        tamano=(TAMANO_BASE[0], 7.0), orden="desc", margen_izq_max=3.4,
        etiquetas_valor={n: _millones(v) for n, v in zip(nombres, perfiles)})
    _formato_millones(fig.axes[0])
    _guardar(fig, destino, "06_top_perfiles")

    # --- Top contratistas ---
    top = (datos.groupby("nombre_normalizado")
           .agg(valor=("valor_total", "sum"), contratos=("consecutivo", "count"))
           .sort_values("valor", ascending=False).head(20))
    nombres = [str(n) for n in top.index]
    fig = g.barras_ranking(
        nombres, top["valor"].tolist(), TEMA,
        "Contratistas con mayor valor acumulado",
        "Millones de pesos · agrupado por documento, con el nombre ya normalizado · top 20", PIE,
        tamano=(TAMANO_BASE[0], 8.5), orden="desc", margen_izq_max=3.4,
        etiquetas_valor={n: f"{_millones(v)} · {int(c)} contratos"
                         for n, v, c in zip(nombres, top["valor"], top["contratos"])})
    _formato_millones(fig.axes[0])
    _guardar(fig, destino, "07_top_contratistas")

    # --- Estacionalidad: contratos por mes de inicio ---
    meses = datos.pivot_table(index="mes_inicio", columns="anio",
                              values="consecutivo", aggfunc="count").reindex(range(1, 13))
    etiquetas = ["E", "F", "M", "A", "M", "J", "J", "A", "S", "O", "N", "D"]
    # Un panel por anio: seis lineas superpuestas se vuelven ilegibles.
    columnas_grid = 3
    filas = -(-len(meses.columns) // columnas_grid)
    paneles = [(str(anio), etiquetas, meses[anio].fillna(0).tolist(), 0)
               for anio in meses.columns]
    fig = g.panel(paneles, TEMA, "Contratos por mes de inicio",
                  "Un panel por año, cada uno con su escala", PIE,
                  filas=filas, columnas_grid=columnas_grid,
                  tamano=(TAMANO_BASE[0], 2.2 * filas + 1.6))
    _guardar(fig, destino, "08_estacionalidad")

    return por_anio


def _formato_millones(ax):
    """El eje de pesos de los rankings, en millones (la unidad va en el subtitulo)."""
    from matplotlib.ticker import FuncFormatter

    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _pos: formato_es(v / 1e6, 0)))


# --------------------------------------------------------------------------
# 4. Tablas de resumen
# --------------------------------------------------------------------------
def escribir_tablas(datos, por_anio, destino):
    def csv(df, nombre, **kw):
        ruta = destino / nombre
        df.to_csv(ruta, index=kw.pop("index", False), encoding="utf-8-sig")
        print(f"  tabla:   {ruta.name}")

    resumen = por_anio.copy()
    resumen["valor_promedio_contrato"] = resumen["valor"] / resumen["contratos"]
    resumen["contratos_por_persona"] = resumen["contratos"] / resumen["personas"]
    csv(resumen, "resumen_por_anio.csv")

    csv(datos.pivot_table(index="anio", columns="nombre_area", values="valor_total",
                          aggfunc="sum").fillna(0).reset_index(),
        "valor_por_area_anio.csv")

    csv(datos.pivot_table(index="perfil", columns="anio", values="consecutivo",
                          aggfunc="count").fillna(0).astype(int).reset_index(),
        "contratos_por_perfil_anio.csv")

    contratistas = (datos.groupby(["id_persona", "nombre_normalizado"])
                    .agg(contratos=("consecutivo", "count"),
                         valor_total=("valor_total", "sum"),
                         anios=("anio", "nunique"),
                         primer_anio=("anio", "min"),
                         ultimo_anio=("anio", "max"))
                    .reset_index().sort_values("valor_total", ascending=False))
    csv(contratistas, "contratistas_consolidado.csv")


# --------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description="Analisis de contratacion OPS")
    ap.add_argument("--carpeta", default=str(carpeta_por_defecto()),
                    help=f"carpeta con los CSV (default: DATA/SIHO/.../{CARPETA_REPORTE})")
    ap.add_argument("--salida", default=str(SALIDA_POR_DEFECTO),
                    help="carpeta de resultados (default: SALIDAS/ops_contratacion)")
    args = ap.parse_args()

    carpeta = Path(args.carpeta)
    if not carpeta.is_dir():
        sys.exit(f"No existe la carpeta '{carpeta}'")
    destino = Path(args.salida)
    destino.mkdir(parents=True, exist_ok=True)

    print(f"Leyendo {carpeta.resolve()}")
    por_anio, informe, conflictos = seleccionar_union(carpeta)
    if not por_anio:
        sys.exit("No se encontro ningun reporte con las columnas esperadas.")
    for anio, df in por_anio.items():
        archivos = df["archivo_origen"].nunique()
        print(f"  {anio}: {len(df):,} contratos de {archivos} archivo(s)")
    recuperados = informe[~informe["archivo_origen"].str.contains("octubre-dic", case=False)]
    if not recuperados.empty:
        print(f"  recuperados de trimestres previos: "
              f"{int(recuperados['contratos_aportados'].sum()):,} contratos")

    datos, auditoria, resumen = consolidar(por_anio)
    print(f"\nConsolidado: {len(datos):,} contratos, "
          f"{datos['id_persona'].nunique():,} contratistas distintos "
          f"({resumen['cedulas']:,} cedulas digitadas)")
    print(f"Nombres unificados desde varias grafias: {len(auditoria):,}")
    print(f"Nombres reordenados a NOMBRES APELLIDOS: {resumen['invertidos']:,}")
    print(f"Cedulas con errata fusionadas: {len(resumen['fusiones']):,}")
    print(f"Cedulas que cargaban a otra persona, separadas: {len(resumen['separadas']):,}")
    print(f"Homonimos con cedulas distintas, sin fusionar: {len(resumen['homonimos']):,}")

    datos.to_csv(destino / "ops_consolidado_normalizado.csv",
                 index=False, encoding="utf-8-sig")
    print(f"  tabla:   ops_consolidado_normalizado.csv")
    if not auditoria.empty:
        auditoria.to_csv(destino / "auditoria_nombres.csv",
                         index=False, encoding="utf-8-sig")
        print(f"  tabla:   auditoria_nombres.csv")
    if not conflictos.empty:
        conflictos.to_csv(destino / "contratos_corregidos.csv",
                          index=False, encoding="utf-8-sig")
        print(f"  tabla:   contratos_corregidos.csv")
    for clave, archivo in (("fusiones", "identidad_cedulas_fusionadas.csv"),
                           ("separadas", "identidad_cedulas_separadas.csv"),
                           ("homonimos", "identidad_homonimos.csv")):
        if resumen[clave]:
            pd.DataFrame(resumen[clave]).to_csv(destino / archivo, index=False,
                                                encoding="utf-8-sig")
            print(f"  tabla:   {archivo}")

    resumen = graficar(datos, destino)
    escribir_tablas(datos, resumen, destino)
    print(f"\nListo. Resultados en {destino.resolve()}")


if __name__ == "__main__":
    main()
