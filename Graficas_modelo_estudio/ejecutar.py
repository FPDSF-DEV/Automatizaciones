#!/usr/bin/env python3
"""Punto de entrada único: genera todas las gráficas a partir de DATA/.

Uso:
    python ejecutar.py                    # corre todos los módulos
    python ejecutar.py ops productividad  # solo los módulos indicados
    python ejecutar.py --siho SJDC_SIHO   # elige el hospital si hay varios en DATA/SIHO
    python ejecutar.py --listar           # muestra los módulos y qué datos usa cada uno
    python ejecutar.py app                # abre la app web de contratación OPS (streamlit)

Fuentes de datos (ver DATA/README.md):
    DATA/SIHO/<HOSPITAL>_SIHO/   reportes del SIHO, con la estructura de SJDC_SIHO
    DATA/TERRIDATA/*.txt         extracciones de TerriData (DNP)
    DATA/AFILIACION/*.xlsx       cifras de afiliación de MinSalud / ADRES

Cada módulo escribe en su propia carpeta dentro de SALIDAS/.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

RAIZ = Path(__file__).resolve().parent
MODULOS = RAIZ / "modulos"
DATA = RAIZ / "DATA"
SALIDAS = RAIZ / "SALIDAS"

DATA_SIHO = DATA / "SIHO"
DATA_TERRIDATA = DATA / "TERRIDATA"
DATA_AFILIACION = DATA / "AFILIACION"

REPORTE_OPS = Path("Consultas_Detalladas") / "Reporte_Contratacion_Externa_desde_2020"

# Terridata termina con 2 cuando generó todo lo posible pero faltaron indicadores.
CODIGO_PARCIAL = 2


class FaltanDatos(Exception):
    """La fuente que necesita un módulo no está en DATA/."""


@dataclass
class Fuentes:
    siho_elegido: str | None

    def siho(self) -> Path:
        """Carpeta del hospital: DATA/SIHO/<HOSPITAL>_SIHO, o DATA/SIHO si los
        reportes se copiaron directamente ahí."""
        if (DATA_SIHO / "Formularios_Anuales").is_dir() and not self.siho_elegido:
            return DATA_SIHO
        hospitales = sorted(
            d for d in DATA_SIHO.iterdir() if (d / "Formularios_Anuales").is_dir()
        ) if DATA_SIHO.is_dir() else []
        if self.siho_elegido:
            elegido = DATA_SIHO / self.siho_elegido
            if elegido not in hospitales:
                raise FaltanDatos(
                    f"No existe '{elegido.relative_to(RAIZ)}' con Formularios_Anuales/. "
                    f"Disponibles: {', '.join(h.name for h in hospitales) or 'ninguno'}"
                )
            return elegido
        if not hospitales:
            raise FaltanDatos(
                "No hay datos del SIHO. Copie la carpeta del hospital (con la estructura "
                "de SJDC_SIHO) dentro de DATA/SIHO/."
            )
        if len(hospitales) > 1:
            raise FaltanDatos(
                f"Hay varios hospitales en DATA/SIHO ({', '.join(h.name for h in hospitales)}). "
                "Indique cuál con --siho NOMBRE."
            )
        return hospitales[0]

    def reporte_ops(self) -> Path:
        carpeta = self.siho() / REPORTE_OPS
        if not carpeta.is_dir():
            raise FaltanDatos(f"No existe '{carpeta.relative_to(RAIZ)}'.")
        return carpeta

    def terridata(self) -> Path:
        if not any(DATA_TERRIDATA.glob("*.txt")):
            raise FaltanDatos("No hay archivos .txt de TerriData en DATA/TERRIDATA/.")
        return DATA_TERRIDATA

    def afiliacion(self) -> Path | None:
        """El Excel de afiliación más reciente; es opcional (sin él, el modelo PSS
        omite los gráficos 8 a 12)."""
        excels = [p for p in DATA_AFILIACION.glob("*.xlsx") if not p.name.startswith("~$")]
        return max(excels, key=lambda p: p.stat().st_mtime) if excels else None


@dataclass
class Paso:
    descripcion: str
    carpeta: Path
    argumentos: Callable[[Fuentes], list[str]]


@dataclass
class Modulo:
    nombre: str
    titulo: str
    fuentes: str
    salida: str
    pasos: list[Paso]


def _pss(f: Fuentes) -> list[str]:
    args = ["-m", "terridata.pss", "--datos", str(f.terridata()),
            "--salida", str(SALIDAS / "terridata_pss")]
    excel = f.afiliacion()
    if excel:
        args += ["--excel", str(excel)]
    else:
        print("  ! No hay Excel de afiliación en DATA/AFILIACION/: se omiten los gráficos 8 a 12.")
    return args


MODULOS_DISPONIBLES = [
    Modulo(
        "ops", "Contratación OPS: normalización de contratistas y gráficas",
        "DATA/SIHO/<HOSPITAL>/Consultas_Detalladas/Reporte_Contratacion_Externa_desde_2020",
        "ops_contratacion",
        [Paso("análisis OPS", MODULOS / "ops_contratacion", lambda f: [
            "analisis_ops.py", "--carpeta", str(f.reporte_ops()),
            "--salida", str(SALIDAS / "ops_contratacion")])],
    ),
    Modulo(
        "produccion", "Producción: una gráfica por concepto y tabla por año",
        "DATA/SIHO/<HOSPITAL>/Formularios_Anuales/<año>/Produccion",
        "produccion",
        [
            Paso("gráficas de producción", MODULOS / "produccion", lambda f: [
                "generator.py", "--input-dir", str(f.siho()),
                "--output-dir", str(SALIDAS / "produccion")]),
            Paso("tabla Excel de producción", MODULOS / "produccion", lambda f: [
                "generar_tabla_excel.py", "--input-dir", str(f.siho()),
                "--output-file", str(SALIDAS / "produccion" / "tabla_conceptos_por_anio.xlsx")]),
        ],
    ),
    Modulo(
        "productividad", "Productividad frente a capacidad instalada y talento humano",
        "DATA/SIHO/<HOSPITAL>/Formularios_Anuales y Consultas_Detalladas",
        "productividad",
        [Paso("indicadores e informe", MODULOS / "productividad", lambda f: [
            "main.py", "--datos", str(f.siho()),
            "--salida", str(SALIDAS / "productividad")])],
    ),
    Modulo(
        "terridata", "Análisis comparativo municipal (TerriData)",
        "DATA/TERRIDATA/*.txt",
        "terridata",
        [Paso("gráficas TerriData", MODULOS / "terridata", lambda f: [
            "-m", "terridata", "--datos", str(f.terridata()),
            "--salida", str(SALIDAS / "terridata")])],
    ),
    Modulo(
        "pss", "Modelo PSS: TerriData + cifras de afiliación",
        "DATA/TERRIDATA/*.txt y DATA/AFILIACION/*.xlsx",
        "terridata_pss",
        [Paso("gráficos del Modelo PSS", MODULOS / "terridata", _pss)],
    ),
]
POR_NOMBRE = {m.nombre: m for m in MODULOS_DISPONIBLES}


def _entorno() -> dict[str, str]:
    entorno = dict(os.environ)
    # La consola de Windows no habla UTF-8 por defecto y los reportes llevan tildes.
    entorno["PYTHONIOENCODING"] = "utf-8"
    entorno["PYTHONUTF8"] = "1"
    entorno["MPLBACKEND"] = "Agg"
    return entorno


def correr(modulo: Modulo, fuentes: Fuentes) -> str:
    """Corre los pasos del módulo y devuelve 'ok', 'parcial', 'omitido' o 'error'."""
    print(f"\n=== {modulo.nombre}: {modulo.titulo}")
    estado = "ok"
    for paso in modulo.pasos:
        try:
            argumentos = paso.argumentos(fuentes)
        except FaltanDatos as exc:
            print(f"  - Omitido: {exc}")
            return "omitido"
        print(f"  > {paso.descripcion}")
        codigo = subprocess.call([sys.executable, *argumentos], cwd=paso.carpeta, env=_entorno())
        if codigo == CODIGO_PARCIAL and modulo.nombre in ("terridata", "pss"):
            estado = "parcial"
        elif codigo != 0:
            print(f"  ! '{paso.descripcion}' terminó con código {codigo}")
            return "error"
    return estado


def abrir_app(fuentes: Fuentes) -> int:
    carpeta = MODULOS / "ops_contratacion"
    try:
        print(f"Datos OPS: {fuentes.reporte_ops()}")
    except FaltanDatos as exc:
        print(f"Aviso: {exc}")
    return subprocess.call(
        [sys.executable, "-m", "streamlit", "run", str(carpeta / "app_streamlit.py")],
        cwd=carpeta, env=_entorno(),
    )


def listar() -> None:
    print("Módulos disponibles:\n")
    for m in MODULOS_DISPONIBLES:
        print(f"  {m.nombre:<14} {m.titulo}")
        print(f"  {'':<14} datos:  {m.fuentes}")
        print(f"  {'':<14} salida: SALIDAS/{m.salida}/\n")
    print(f"  {'app':<14} App web interactiva de contratación OPS (streamlit)")


def main(argv: list[str] | None = None) -> int:
    for flujo in (sys.stdout, sys.stderr):
        try:
            # line_buffering: los encabezados salen antes que la salida de cada módulo.
            flujo.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
        except (AttributeError, ValueError):
            pass

    parser = argparse.ArgumentParser(
        description="Genera todas las gráficas a partir de las fuentes en DATA/.",
    )
    parser.add_argument("modulos", nargs="*", metavar="MODULO",
                        help=f"módulos a correr: {', '.join(POR_NOMBRE)} o 'app' (por defecto, todos)")
    parser.add_argument("--siho", help="carpeta del hospital dentro de DATA/SIHO, si hay varias")
    parser.add_argument("--listar", action="store_true", help="lista los módulos y sale")
    args = parser.parse_args(argv)

    if args.listar:
        listar()
        return 0

    fuentes = Fuentes(args.siho)
    if args.modulos == ["app"]:
        return abrir_app(fuentes)

    desconocidos = [n for n in args.modulos if n not in POR_NOMBRE]
    if desconocidos:
        parser.error(f"módulo desconocido: {', '.join(desconocidos)}. "
                     f"Disponibles: {', '.join(POR_NOMBRE)}, app")
    elegidos = [POR_NOMBRE[n] for n in args.modulos] or MODULOS_DISPONIBLES

    SALIDAS.mkdir(exist_ok=True)
    inicio = time.time()
    resultados = {m.nombre: correr(m, fuentes) for m in elegidos}

    print(f"\n=== Resumen ({time.time() - inicio:.0f} s) — resultados en {SALIDAS}")
    etiquetas = {"ok": "OK", "parcial": "OK (faltaron indicadores)",
                 "omitido": "OMITIDO (faltan datos)", "error": "ERROR"}
    for nombre, estado in resultados.items():
        print(f"  {nombre:<14} {etiquetas[estado]}")
    return 1 if "error" in resultados.values() else 0


if __name__ == "__main__":
    raise SystemExit(main())
