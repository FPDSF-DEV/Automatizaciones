"""CLI: `python -m terridata --datos DATA/TERRIDATA --salida SALIDAS/terridata` (§9 del PLAN)."""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date
from pathlib import Path

from . import graficas as g
from .catalogo import CATALOGO
from .catalogo_graficas import SECCIONES, generar
from .dashboard import escribir_dashboard, svg_en_linea
from .derivados import agregar_derivados
from .estilo import TEMAS, formato_es
from .lectura import leer_carpeta
from .resolucion import resolver, tabla_texto

CODIGO_OK = 0
CODIGO_ERROR_ENTRADA = 1
CODIGO_PARCIAL = 2

IDS_SECCIONES = [s for s, _ in SECCIONES]

# Raíz del proyecto unificado: los .txt viven en DATA/TERRIDATA y los resultados en SALIDAS/.
RAIZ_PROYECTO = Path(__file__).resolve().parents[3]
DATOS_POR_DEFECTO = RAIZ_PROYECTO / "DATA" / "TERRIDATA"
SALIDA_POR_DEFECTO = RAIZ_PROYECTO / "SALIDAS" / "terridata"


def _consola_utf8() -> None:
    """La consola de Windows no habla UTF-8 por defecto y los municipios llevan tilde."""
    for flujo in (sys.stdout, sys.stderr):
        try:
            flujo.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


def construir_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m terridata",
        description="Gráficas y dashboard a partir de extracciones .txt de TerriData (DNP).",
    )
    p.add_argument("--datos", default=str(DATOS_POR_DEFECTO),
                   help="carpeta con los .txt (por defecto DATA/TERRIDATA)")
    p.add_argument("--salida", default=str(SALIDA_POR_DEFECTO),
                   help="carpeta de salida (por defecto SALIDAS/terridata)")
    p.add_argument("--anio-corte", type=int, default=date.today().year,
                   help="año de corte (por defecto, el año actual)")
    p.add_argument("--titulo", default="Análisis comparativo TerriData",
                   help="título del análisis")
    p.add_argument("--secciones", default=",".join(IDS_SECCIONES),
                   help=f"secciones separadas por coma ({', '.join(IDS_SECCIONES)})")
    p.add_argument("--formatos", default="png,svg,html", help="png,svg,html")
    p.add_argument("--tema", choices=sorted(TEMAS), default="claro")
    p.add_argument("--orden-entidades", choices=["aparicion", "nombre"], default="aparicion")
    p.add_argument("--verboso", action="store_true",
                   help="log detallado de resolución de indicadores y matriz resuelta")
    return p


def _lista(texto: str) -> list[str]:
    return [x.strip().lower() for x in texto.split(",") if x.strip()]


def main(argv: list[str] | None = None) -> int:
    _consola_utf8()
    args = construir_parser().parse_args(argv)

    logging.basicConfig(
        level=logging.INFO if args.verboso else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
    )

    secciones = [s for s in _lista(args.secciones) if s in IDS_SECCIONES]
    desconocidas = [s for s in _lista(args.secciones) if s not in IDS_SECCIONES]
    if desconocidas:
        print(f"Sección desconocida: {', '.join(desconocidas)}", file=sys.stderr)
        print(f"Disponibles: {', '.join(IDS_SECCIONES)}", file=sys.stderr)
        return CODIGO_ERROR_ENTRADA
    if not secciones:
        print("No se pidió ninguna sección válida.", file=sys.stderr)
        return CODIGO_ERROR_ENTRADA

    formatos = _lista(args.formatos)
    formatos_imagen = [f for f in formatos if f in ("png", "svg")]

    # --- 1. leer
    carpeta = Path(args.datos)
    if not carpeta.is_dir():
        print(f"La carpeta de datos no existe: {carpeta}", file=sys.stderr)
        return CODIGO_ERROR_ENTRADA

    lectura = leer_carpeta(carpeta, orden_entidades=args.orden_entidades)
    if not lectura.archivos:
        print(f"No hay archivos .txt en {carpeta}.", file=sys.stderr)
        print("Pon ahí las extracciones de TerriData y vuelve a correr.", file=sys.stderr)
        return CODIGO_ERROR_ENTRADA
    if not lectura.filas:
        print(f"Se leyeron {len(lectura.archivos)} archivo(s) pero ninguna fila es válida.",
              file=sys.stderr)
        print("Revisa que estén separados por '|' y con 13 columnas.", file=sys.stderr)
        return CODIGO_ERROR_ENTRADA

    # --- 2. resolver
    res = resolver(
        lectura.filas,
        CATALOGO,
        anio_corte=args.anio_corte,
        entidades=lectura.entidades,
        departamento=lectura.departamento,
    )
    agregar_derivados(res)

    resueltos = sum(1 for i in CATALOGO if res.disponible(i.id))

    if args.verboso:
        print(tabla_texto(res, [i.id for i in CATALOGO]))
        print()

    # --- 3. graficar
    tema = TEMAS[args.tema]
    salida = Path(args.salida)
    renders = []
    omitidas = []
    guardadas = {"png": 0, "svg": 0}
    for spec, render in generar(res, tema, secciones):
        if render is None:
            omitidas.append(spec)
            continue
        for formato in formatos_imagen:
            g.guardar(render.fig, salida / formato / render.archivo, formatos=(formato,))
            guardadas[formato] += 1
        if "html" in formatos:
            render.svg = svg_en_linea(render.fig, render.archivo)
        # Se cierra aquí, no al final: no hace falta tener 52 figuras abiertas.
        g.cerrar(render.fig)
        render.fig = None
        renders.append(render)

    # --- 4. dashboard
    ruta_dashboard = None
    if "html" in formatos:
        ruta_dashboard = escribir_dashboard(
            salida / "dashboard.html",
            renders=renders,
            omitidas=omitidas,
            res=res,
            tema=tema,
            titulo=args.titulo,
            anio_corte=args.anio_corte,
            filas_leidas=len(lectura.filas),
            archivos=len(lectura.archivos),
        )

    # --- 5. resumen
    print(f"Entidades: {len(res.entidades)} ({', '.join(res.entidades)})")
    print(
        f"Departamento: {res.departamento or '—'} | "
        f"Filas leídas: {formato_es(len(lectura.filas))} | "
        f"Año de corte: {args.anio_corte}"
    )
    if lectura.lineas_descartadas:
        print(f"Líneas descartadas: {formato_es(lectura.lineas_descartadas)} "
              f"(no tenían 13 campos)")
    print(f"Indicadores resueltos: {resueltos}/{len(CATALOGO)}")
    detalle = " · ".join(f"{f} {guardadas[f]}" for f in formatos_imagen)
    print(f"Gráficas generadas: {len(renders)}" + (f"  ({detalle})" if detalle else ""))
    if omitidas:
        print(f"Gráficas omitidas por falta de datos: {len(omitidas)} "
              f"({', '.join(o.id for o in omitidas)})")
    if ruta_dashboard:
        print(f"Dashboard: {ruta_dashboard}")

    return CODIGO_PARCIAL if (omitidas or res.faltantes) else CODIGO_OK


if __name__ == "__main__":
    raise SystemExit(main())
