"""Descubrimiento y parseo de los .txt de TerriData.

El formato está verificado contra extracciones reales: texto plano separado por
`|`, UTF-8 (a veces con BOM), una línea de encabezado y trece columnas en orden
fijo. Cada regla de este módulo existe porque el parseo falla sin ella; ver §3
del PLAN.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger("terridata.lectura")

COLUMNAS = [
    "Código Departamento",
    "Departamento",
    "Código Entidad",
    "Entidad",
    "Dimensión",
    "Subcategoría",
    "Indicador",
    "Dato Numérico",
    "Dato Cualitativo",
    "Año",
    "Mes",
    "Fuente",
    "Unidad de Medida",
]

N_COLUMNAS = len(COLUMNAS)


@dataclass(frozen=True)
class Fila:
    cod_departamento: str
    departamento: str
    cod_entidad: str
    entidad: str
    dimension: str
    subcategoria: str
    indicador: str
    valor: float | None
    texto: str | None
    anio: int
    mes: int
    fuente: str
    unidad: str


@dataclass
class Lectura:
    """Resultado de leer una carpeta: filas únicas y el rastro de lo que pasó."""

    filas: list[Fila]
    entidades: list[str]           # en orden de primera aparición
    departamento: str
    archivos: list[Path]
    lineas_leidas: int = 0
    lineas_descartadas: int = 0
    duplicados: int = 0


def a_numero(txt: str) -> float | None:
    """Convierte el formato numérico colombiano (punto de miles, coma decimal).

    `22.395,00` -> 22395.0 · `-1.698,39` -> -1698.39 · `503,35` -> 503.35.
    Devuelve None para vacío o no numérico; nunca levanta excepción.
    """
    t = (txt or "").strip()
    if not t:
        return None
    t = t.replace(".", "").replace(",", ".")
    try:
        return float(t)
    except ValueError:
        return None


def _a_entero(txt: str, defecto: int = 0) -> int:
    t = (txt or "").strip()
    if not t:
        return defecto
    try:
        return int(float(t.replace(".", "").replace(",", ".")))
    except ValueError:
        return defecto


def _limpiar(txt: str) -> str:
    return (txt or "").strip()


def parsear_linea(linea: str) -> Fila | None:
    """Parsea una línea de datos. Devuelve None si no tiene 13 campos."""
    campos = linea.rstrip("\n").rstrip("\r").split("|")
    if len(campos) != N_COLUMNAS:
        return None
    c = [_limpiar(x) for x in campos]
    return Fila(
        cod_departamento=c[0],
        departamento=c[1],
        cod_entidad=c[2],
        entidad=c[3],
        dimension=c[4],
        subcategoria=c[5],
        indicador=c[6],
        valor=a_numero(c[7]),
        texto=c[8] or None,
        anio=_a_entero(c[9]),
        mes=_a_entero(c[10]),
        fuente=c[11],
        unidad=c[12],
    )


def _es_encabezado(linea: str) -> bool:
    campos = [_limpiar(x) for x in linea.split("|")]
    return campos[:4] == COLUMNAS[:4]


def descubrir(carpeta: str | Path) -> list[Path]:
    """Los .txt de la carpeta, ordenados alfabéticamente por nombre."""
    ruta = Path(carpeta)
    if not ruta.is_dir():
        return []
    return sorted(
        (p for p in ruta.iterdir() if p.is_file() and p.suffix.lower() == ".txt"),
        key=lambda p: p.name.lower(),
    )


def leer_archivo(ruta: Path) -> tuple[list[Fila], int, int]:
    """Lee un .txt. Devuelve (filas, líneas de datos vistas, descartadas)."""
    filas: list[Fila] = []
    vistas = 0
    descartadas = 0
    with open(ruta, encoding="utf-8-sig", errors="replace") as f:
        for n, linea in enumerate(f, start=1):
            if not linea.strip():
                continue
            if n == 1 and _es_encabezado(linea):
                continue
            vistas += 1
            fila = parsear_linea(linea)
            if fila is None:
                descartadas += 1
                log.warning(
                    "%s:%d descartada: %d campos, se esperaban %d",
                    ruta.name, n, len(linea.rstrip("\n").split("|")), N_COLUMNAS,
                )
                continue
            if not fila.entidad or not fila.indicador:
                descartadas += 1
                log.warning("%s:%d descartada: sin entidad o sin indicador", ruta.name, n)
                continue
            filas.append(fila)
    return filas, vistas, descartadas


def leer_carpeta(carpeta: str | Path, orden_entidades: str = "aparicion") -> Lectura:
    """Consolida todos los .txt de la carpeta en una sola lista de filas únicas.

    Deduplica por la tupla completa de las 13 columnas (un archivo puede traer
    varias entidades y varios archivos la misma entidad).
    """
    archivos = descubrir(carpeta)
    vistos: set[Fila] = set()
    filas: list[Fila] = []
    entidades: list[str] = []
    departamentos: list[str] = []
    leidas = 0
    descartadas = 0
    duplicados = 0

    for ruta in archivos:
        nuevas, vistas, desc = leer_archivo(ruta)
        leidas += vistas
        descartadas += desc
        for fila in nuevas:
            if fila in vistos:
                duplicados += 1
                continue
            vistos.add(fila)
            filas.append(fila)
            if fila.entidad not in entidades:
                entidades.append(fila.entidad)
            if fila.departamento and fila.departamento not in departamentos:
                departamentos.append(fila.departamento)

    if orden_entidades == "nombre":
        entidades = sorted(entidades, key=lambda e: e.lower())

    if len(departamentos) == 1:
        departamento = departamentos[0]
    elif departamentos:
        departamento = ", ".join(departamentos)
    else:
        departamento = ""

    return Lectura(
        filas=filas,
        entidades=entidades,
        departamento=departamento,
        archivos=archivos,
        lineas_leidas=leidas,
        lineas_descartadas=descartadas,
        duplicados=duplicados,
    )
