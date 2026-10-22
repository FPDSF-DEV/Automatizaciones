"""Lectura de los reportes crudos y consolidación por año.

Estructura esperada dentro de la carpeta de datos (la misma para cualquier
hospital; los nombres de los archivos .csv no importan):

    DATA/SIHO/<HOSPITAL>_SIHO/          (estructura de SJDC_SIHO)
    ├── Formularios_Anuales/
    │   └── <año>/
    │       ├── Capacidad_Instalada/*.csv
    │       ├── Produccion/*.csv
    │       ├── Recursos_Humanos/*.csv
    │       └── ... (las demás carpetas se ignoran)
    └── Consultas_Detalladas/
        └── Reporte_Contratacion_Externa_desde_2020/
            └── <año>/   (opcional: también se aceptan los CSV sueltos)
                └── Reporte_Contratacion_Externa_..._<año>_octubre-dic.csv
                    (los demás trimestres se ignoran)

El resultado es el mismo formato de siempre para los indicadores:
{clave: DataFrame} con los conceptos en el índice y los años en las columnas.
"""
from __future__ import annotations

import re
import unicodedata
from pathlib import Path

import pandas as pd

from .config import (
    CARPETA_FORMULARIOS,
    CARPETA_OPS,
    DATOS,
    FORMULARIOS,
    OPS,
    RECURSOS_HUMANOS,
)


class ErrorDeDatos(Exception):
    """Falta un archivo o no tiene la forma esperada."""


def normalizar(texto) -> str:
    """Minúsculas, sin tildes y sin espacios repetidos: así una tilde o un
    espacio de más en el reporte no rompe la búsqueda del concepto."""
    t = unicodedata.normalize("NFKD", str(texto))
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", t).strip().lower()


def _leer_csv(archivo: Path) -> pd.DataFrame:
    for codificacion in ("utf-8-sig", "latin-1"):
        try:
            df = pd.read_csv(archivo, encoding=codificacion, dtype=str)
            break
        except UnicodeDecodeError:
            continue
    df.columns = [str(c).strip() for c in df.columns]
    return df


def _exigir(df: pd.DataFrame, columnas: list[str], archivo: Path) -> None:
    faltan = [c for c in columnas if c not in df.columns]
    if faltan:
        raise ErrorDeDatos(f"{archivo.name}: faltan las columnas {faltan}.")


def _numero(serie: pd.Series) -> pd.Series:
    return pd.to_numeric(serie.str.strip(), errors="coerce").fillna(0.0)


def _anios_formularios(carpeta: Path) -> dict[int, Path]:
    raiz = carpeta / CARPETA_FORMULARIOS
    if not raiz.is_dir():
        raise ErrorDeDatos(f"No existe la carpeta '{raiz}'.")
    return {
        int(d.name): d
        for d in sorted(raiz.iterdir())
        if d.is_dir() and re.fullmatch(r"\d{4}", d.name)
    }


def _csvs(carpeta: Path) -> list[Path]:
    return sorted(carpeta.glob("*.csv")) if carpeta.is_dir() else []


# --------------------------------------------------------------------------
# Formularios con filas "concepto" (Capacidad_Instalada, Produccion)
# --------------------------------------------------------------------------
def _formulario_por_concepto(carpeta: Path, subcarpeta: str, columna_valor: str) -> pd.DataFrame:
    columnas: dict[int, pd.Series] = {}
    for anio, dir_anio in _anios_formularios(carpeta).items():
        archivos = _csvs(dir_anio / subcarpeta)
        if not archivos:
            continue
        partes = []
        for archivo in archivos:
            df = _leer_csv(archivo)
            _exigir(df, ["concepto", columna_valor], archivo)
            partes.append(pd.DataFrame({
                "concepto": df["concepto"].str.strip(),
                "valor": _numero(df[columna_valor]),
            }))
        unido = pd.concat(partes)
        columnas[anio] = unido.groupby("concepto", sort=False)["valor"].sum()
    if not columnas:
        raise ErrorDeDatos(
            f"No hay ningún CSV en '{CARPETA_FORMULARIOS}/<año>/{subcarpeta}/'."
        )
    return pd.DataFrame(columnas).fillna(0.0).sort_index(axis=1)


# --------------------------------------------------------------------------
# Recursos humanos de planta (nómina)
# --------------------------------------------------------------------------
def _nomina(carpeta: Path) -> pd.DataFrame:
    tipo, cantidad = RECURSOS_HUMANOS["col_tipo"], RECURSOS_HUMANOS["col_cantidad"]
    columnas: dict[int, pd.Series] = {}
    for anio, dir_anio in _anios_formularios(carpeta).items():
        archivos = _csvs(dir_anio / RECURSOS_HUMANOS["carpeta"])
        if not archivos:
            continue
        partes = []
        for archivo in archivos:
            df = _leer_csv(archivo)
            _exigir(df, [tipo, cantidad], archivo)
            partes.append(pd.DataFrame({
                "tipo": df[tipo].fillna("").str.strip().str.upper(),
                "valor": _numero(df[cantidad]),
            }))
        unido = pd.concat(partes)
        serie = unido.groupby("tipo")["valor"].sum()
        serie = serie.reindex(["APOYO", "OPERATIVO"], fill_value=0.0)
        # TOTAL suma todos los cargos, aunque traigan un tipo distinto o vacío.
        serie["TOTAL"] = float(unido["valor"].sum())
        columnas[anio] = serie
    if not columnas:
        raise ErrorDeDatos(
            f"No hay ningún CSV en '{CARPETA_FORMULARIOS}/<año>/"
            f"{RECURSOS_HUMANOS['carpeta']}/'."
        )
    return pd.DataFrame(columnas).sort_index(axis=1)


# --------------------------------------------------------------------------
# Contratación externa (OPS)
# --------------------------------------------------------------------------
def _anio_de_archivo(archivo: Path, df: pd.DataFrame) -> int:
    """El año es el último número de 4 cifras del nombre del archivo
    ('..._desde_2020_2025_octubre-dic.csv' -> 2025). Si el nombre no trae
    año, se toma el año más frecuente de la fecha de inicio de los contratos."""
    encontrados = re.findall(r"(?<!\d)(20\d{2})(?!\d)", archivo.stem)
    if encontrados:
        return int(encontrados[-1])
    col = OPS["col_fecha_inicio"]
    if col in df.columns:
        fechas = pd.to_datetime(df[col].str.slice(0, 10).str.strip(),
                                dayfirst=True, errors="coerce").dropna()
        if len(fechas):
            return int(fechas.dt.year.mode().iloc[0])
    raise ErrorDeDatos(f"{archivo.name}: no se pudo saber a qué año corresponde.")


def _ops(carpeta: Path) -> pd.DataFrame:
    dir_ops = carpeta / CARPETA_OPS
    # Los reportes pueden estar sueltos o en subcarpetas por año. Solo se usa
    # el de octubre-dic de cada año; los demás trimestres se ignoran.
    trimestre = normalizar(OPS["trimestre_anual"])
    archivos = sorted(
        a for a in dir_ops.rglob("*.csv") if trimestre in normalizar(a.stem)
    ) if dir_ops.is_dir() else []
    if not archivos:
        raise ErrorDeDatos(
            f"No hay ningún CSV de {OPS['trimestre_anual']} en '{dir_ops}'."
        )
    area, meses = OPS["col_area"], OPS["col_meses"]
    columnas: dict[int, pd.Series] = {}
    origen: dict[int, Path] = {}
    for archivo in archivos:
        df = _leer_csv(archivo)
        _exigir(df, [area, meses], archivo)
        anio = _anio_de_archivo(archivo, df)
        if anio in origen:
            raise ErrorDeDatos(
                f"Hay dos reportes OPS para {anio}: {origen[anio].name} y "
                f"{archivo.name}. Deje solo uno por año."
            )
        origen[anio] = archivo
        areas = df[area].map(normalizar)
        operativo = areas.str.contains(normalizar(OPS["texto_operativo"]), regex=False)
        apoyo = areas.str.contains(normalizar(OPS["texto_apoyo"]), regex=False)
        n_meses = _numero(df[meses])
        columnas[anio] = pd.Series({
            "APOYO": float(apoyo.sum()),
            "OPERATIVO": float(operativo.sum()),
            "MESES CONTRATADOS APOYO": float(n_meses[apoyo].sum()),
            "MESES CONTRATADOS OPERATIVOS": float(n_meses[operativo].sum()),
            # Cada reporte trae todos los contratos del año, sin importar el
            # área: el total no depende de la clasificación apoyo/operativo.
            "CONTRATOS TOTAL": float(len(df)),
            "MESES CONTRATADOS TOTAL": float(n_meses.sum()),
        })
    return pd.DataFrame(columnas).sort_index(axis=1)


# --------------------------------------------------------------------------
def cargar(carpeta: Path | None = None) -> dict[str, pd.DataFrame]:
    """Devuelve {clave: DataFrame} con los conceptos en el índice y los años en
    las columnas. Los años se detectan solos: agregar la carpeta
    Formularios_Anuales/2026 y el reporte OPS de 2026 basta para que aparezcan
    en todas las tablas y en todas las gráficas."""
    carpeta = Path(carpeta) if carpeta else DATOS
    if not carpeta.is_dir():
        raise ErrorDeDatos(f"No existe la carpeta de datos '{carpeta}'.")
    datos = {
        clave: _formulario_por_concepto(carpeta, subcarpeta, col)
        for clave, (subcarpeta, col) in FORMULARIOS.items()
    }
    datos["nomina"] = _nomina(carpeta)
    datos["ops"] = _ops(carpeta)
    return datos


def nombre_hospital(carpeta: Path | None = None) -> str:
    """Nombre de la entidad según la columna 'nombre' de los formularios."""
    carpeta = Path(carpeta) if carpeta else DATOS
    try:
        anios = _anios_formularios(carpeta)
    except ErrorDeDatos:
        return ""
    for dir_anio in reversed(list(anios.values())):
        for archivo in _csvs(dir_anio / FORMULARIOS["capacidad"][0]):
            df = _leer_csv(archivo)
            if "nombre" in df.columns and df["nombre"].notna().any():
                return str(df["nombre"].dropna().iloc[0]).strip()
    return ""


def guardar_consolidado(datos: dict[str, pd.DataFrame], destino: Path) -> None:
    """Escribe lo que el programa entendió de los reportes crudos, una tabla
    por fuente, para poder revisarlo a mano."""
    destino.mkdir(parents=True, exist_ok=True)
    for clave, df in datos.items():
        df.rename_axis("concepto").to_csv(destino / f"{clave}.csv", encoding="utf-8-sig")
