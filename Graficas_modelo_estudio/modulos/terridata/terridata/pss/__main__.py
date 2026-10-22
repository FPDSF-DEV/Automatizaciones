"""CLI del Modelo PSS: `python -m terridata.pss --datos DATA/TERRIDATA --excel "DATA/AFILIACION/CIFRAS ....xlsx"`."""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date, datetime
from pathlib import Path

from .. import graficas as g
from ..dashboard import _tarjeta_dato, construir_html_general, svg_en_linea
from ..estilo import TEMAS, formato_es
from ..lectura import leer_carpeta
from ..resolucion import resolver
from .afiliacion import buscar_excel, leer_cobertura
from .ambito import (
    anios_disponibles_quinquenios,
    datos_piramide,
    detectar_ambito,
    municipios_de,
    promedio_ponderado,
)
from .catalogo_pss import CATALOGO_PSS, SECCIONES_PSS, Datos
from .graficos_pss import DEFINICION_ODS, ESPECIFICACIONES, generar

CODIGO_OK = 0
CODIGO_ERROR_ENTRADA = 1
CODIGO_PARCIAL = 2

# Raíz del proyecto unificado: TerriData en DATA/TERRIDATA, el Excel de afiliación en
# DATA/AFILIACION y los resultados en SALIDAS/.
RAIZ_PROYECTO = Path(__file__).resolve().parents[4]
DATOS_POR_DEFECTO = RAIZ_PROYECTO / "DATA" / "TERRIDATA"
AFILIACION_POR_DEFECTO = RAIZ_PROYECTO / "DATA" / "AFILIACION"
SALIDA_POR_DEFECTO = RAIZ_PROYECTO / "SALIDAS" / "terridata_pss"

TITULO = ("Modelo de Prestación de Servicios de Salud — "
          "ESE Hospital San Antonio, Gigante (Huila)")


def _consola_utf8() -> None:
    for flujo in (sys.stdout, sys.stderr):
        try:
            flujo.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


def construir_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m terridata.pss",
        description="Los 32 gráficos del Inventario del Modelo PSS, a partir de "
                    "las extracciones de TerriData y del Excel de afiliación de ADRES.",
    )
    p.add_argument("--datos", default=str(DATOS_POR_DEFECTO),
                   help="carpeta con los .txt de TerriData (por defecto DATA/TERRIDATA)")
    p.add_argument("--excel", default=None,
                   help="Excel de afiliación de ADRES (por defecto, el más reciente "
                        "de DATA/AFILIACION)")
    p.add_argument("--salida", default=str(SALIDA_POR_DEFECTO),
                   help="carpeta de salida (por defecto SALIDAS/terridata_pss)")
    p.add_argument("--anio", type=int, default=date.today().year,
                   help="año de referencia de las proyecciones (por defecto, el actual)")
    p.add_argument("--titulo", default=TITULO)
    p.add_argument("--graficos", default="",
                   help="números a generar, separados por coma (por defecto, los 32)")
    p.add_argument("--formatos", default="png,svg,html")
    p.add_argument("--tema", choices=sorted(TEMAS), default="claro")
    p.add_argument("--verboso", action="store_true")
    return p


def main(argv: list[str] | None = None) -> int:
    _consola_utf8()
    args = construir_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.INFO if args.verboso else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
    )

    formatos = [f.strip().lower() for f in args.formatos.split(",") if f.strip()]
    formatos_imagen = [f for f in formatos if f in ("png", "svg")]
    numeros = [int(n) for n in args.graficos.split(",") if n.strip().isdigit()]

    # --- 1. TerriData
    carpeta = Path(args.datos)
    if not carpeta.is_dir():
        print(f"La carpeta de datos no existe: {carpeta}", file=sys.stderr)
        return CODIGO_ERROR_ENTRADA
    lectura = leer_carpeta(carpeta)
    if not lectura.filas:
        print(f"No hay filas válidas de TerriData en {carpeta}.", file=sys.stderr)
        return CODIGO_ERROR_ENTRADA

    # --- 2. Excel de afiliación
    ruta_excel = Path(args.excel) if args.excel else buscar_excel(AFILIACION_POR_DEFECTO)
    cobertura = None
    if ruta_excel is None:
        print("Aviso: no encontré el Excel de afiliación de ADRES; los gráficos 8 a 12 "
              "se omitirán.", file=sys.stderr)
    else:
        try:
            cobertura = leer_cobertura(ruta_excel)
        except (FileNotFoundError, ValueError) as error:
            print(f"No pude leer el Excel de afiliación: {error}", file=sys.stderr)
            return CODIGO_ERROR_ENTRADA

    # --- 3. resolver
    res = resolver(lectura.filas, CATALOGO_PSS, anio_corte=args.anio,
                   entidades=lectura.entidades, departamento=lectura.departamento)
    ambito = detectar_ambito(lectura.entidades, lectura.departamento)
    municipios = municipios_de(ambito)
    codigos = {}
    cod_departamento = ""
    for fila in lectura.filas:
        codigos.setdefault(fila.entidad, fila.cod_entidad)
        cod_departamento = cod_departamento or fila.cod_departamento

    datos = Datos(
        lectura=lectura, res=res, cobertura=cobertura, ambito=ambito,
        municipios=municipios, anio=args.anio, codigos=codigos,
        cod_departamento=cod_departamento,
    )

    # --- 4. gráficos
    tema = TEMAS[args.tema]
    salida = Path(args.salida)
    renders, omitidos = [], []
    guardadas = {"png": 0, "svg": 0}
    for spec, render in generar(datos, tema, numeros or None):
        if render is None:
            omitidos.append(spec)
            continue
        for formato in formatos_imagen:
            g.guardar(render.fig, salida / formato / render.archivo, formatos=(formato,))
            guardadas[formato] += 1
        if "html" in formatos:
            render.svg = svg_en_linea(render.fig, render.archivo)
        g.cerrar(render.fig)
        render.fig = None
        renders.append(render)

    # --- 5. dashboard
    ruta_dashboard = None
    if "html" in formatos and renders:
        ruta_dashboard = _escribir_dashboard(
            salida / "dashboard.html", renders, omitidos, datos, tema, args
        )

    # --- 6. resumen
    print(f"Municipios: {len(municipios)} ({', '.join(municipios)})")
    print(f"Ámbito de los gráficos 1 a 7: {ambito.titulo}")
    if cobertura:
        print(f"Afiliación: {ruta_excel.name} · corte {cobertura.corte}")
    poblacion = datos.dep_poblacion()
    print(f"Población {args.anio}: {formato_es(poblacion, 0) if poblacion else '—'} "
          f"| Filas TerriData: {formato_es(len(lectura.filas))}")
    detalle = " · ".join(f"{f} {guardadas[f]}" for f in formatos_imagen)
    print(f"Gráficos generados: {len(renders)}/{len(numeros) or len(ESPECIFICACIONES)}"
          + (f"  ({detalle})" if detalle else ""))
    if omitidos:
        print("Gráficos omitidos: "
              + ", ".join(f"#{o.numero} {o.id}" for o in omitidos))
    if ruta_dashboard:
        print(f"Dashboard: {ruta_dashboard}")

    return CODIGO_PARCIAL if omitidos else CODIGO_OK


def _escribir_dashboard(destino, renders, omitidos, datos: Datos, tema, args) -> Path:
    """Arma el HTML con las tarjetas, los avisos y las notas de este entregable."""
    poblacion = datos.dep_poblacion()
    afiliaciones = [datos.afiliacion_municipio(e) for e in datos.municipios]
    coberturas = [a.cobertura_pct for a in afiliaciones if a and a.cobertura_pct is not None]
    pesos = [a.poblacion for a in afiliaciones if a and a.cobertura_pct is not None]
    cobertura_media, _ = promedio_ponderado(coberturas, pesos) if coberturas else (None, 0)
    sin_sisben = sum(
        a.subsidiado_sin_sisben for a in afiliaciones
        if a and a.subsidiado_sin_sisben is not None
    )

    tarjetas = [
        _tarjeta_dato("Municipios analizados", str(len(datos.municipios)),
                      datos.lectura.departamento or ""),
        _tarjeta_dato(f"Población {args.anio}",
                      formato_es(poblacion, 0) if poblacion else "—",
                      "proyecciones DANE (PPED)"),
        _tarjeta_dato("Cobertura SGSSS",
                      f"{formato_es(cobertura_media, 1)} %" if cobertura_media else "—",
                      "promedio ponderado por población"),
        _tarjeta_dato("Subsidiados sin SISBÉN IV", formato_es(sin_sisben, 0),
                      "riesgo de continuidad del aseguramiento"),
    ]

    avisos: list[tuple[str, list[str]]] = []

    if not datos.ambito.es_departamento:
        avisos.append((
            "Los gráficos 1 a 7 son del área de influencia, no del departamento",
            ["Entre los archivos cargados no hay una extracción de TerriData del "
             "departamento, así que esos gráficos se arman sumando los conteos de los "
             f"{len(datos.municipios)} municipios y promediando las tasas por población. "
             "Para obtener las cifras departamentales, descarga de TerriData la "
             "extracción del Huila y ponla en la misma carpeta de datos.",
             "El gráfico 8 sí es departamental: sale del Excel de ADRES, que trae una "
             "fila por departamento."],
        ))

    piramide = datos_piramide(datos.lectura.filas,
                             [datos.ambito.nombre] if datos.ambito.es_departamento
                             else datos.municipios, args.anio)
    if piramide.anio and piramide.anio != args.anio:
        anios = anios_disponibles_quinquenios(datos.lectura.filas, datos.municipios)
        avisos.append((
            f"La pirámide poblacional quedó en {piramide.anio}, no en {args.anio}",
            [f"En los archivos cargados la serie por quinquenios está completa para "
             f"ambos sexos únicamente en {piramide.anio} "
             f"({piramide.dimension}). La serie masculina de "
             f"'Demografía y población' solo trae {', '.join(str(a) for a in anios['H'][-2:])}, "
             "mientras la femenina va de 2018 a 2042.",
             "Mezclar sexos de años distintos daría una pirámide falsa, así que se usa "
             "el año más reciente con los dos completos. Si vuelves a descargar los "
             ".txt con la serie masculina completa, la pirámide sale sola en el año pedido."],
        ))

    sustituciones = [
        f"#{numero} {titulo}: {nota}"
        for numero, _id, titulo, _ind, _anio, _lectura, nota in DEFINICION_ODS
        if nota and "no viene en las extracciones" in nota
    ]
    if sustituciones:
        avisos.append((
            "Dos indicadores ODS no están en las extracciones y se reemplazaron",
            sustituciones,
        ))

    if omitidos:
        avisos.append((
            f"Gráficos omitidos por falta de datos ({len(omitidos)})",
            [f"#{o.numero} {o.titulo}" for o in omitidos],
        ))
    if not omitidos:
        avisos.append((
            "Los 32 gráficos del inventario se generaron",
            ["Cada gráfico lleva en el subtítulo la unidad, el año del dato y la fuente; "
             "los datos que lo alimentan están en la tabla plegada debajo."],
        ))

    resumen = (
        f"{len(datos.municipios)} municipios · "
        f"{datos.lectura.departamento} · año de referencia {args.anio} · "
        f"{formato_es(len(datos.lectura.filas))} filas de TerriData"
        + (f" · afiliación ADRES corte {datos.cobertura.corte}" if datos.cobertura else "")
        + f" · generado el {datetime.now().strftime('%d/%m/%Y %H:%M')}"
    )

    html_texto = construir_html_general(
        renders=renders,
        titulo=args.titulo,
        resumen=resumen,
        tarjetas=tarjetas,
        secciones=SECCIONES_PSS,
        avisos=avisos,
        tema=tema,
        sustantivo=("gráfico", "gráficos"),
        nota_pie=(
            "Fuentes: TerriData (DNP) para lo territorial y ADRES para la afiliación al "
            f"SGSSS. Gráficos generados con el tema <strong>{tema.nombre}</strong>; "
            "los PNG y SVG equivalentes están en <code>png/</code> y <code>svg/</code>."
        ),
    )
    ruta = Path(destino)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(html_texto, encoding="utf-8")
    return ruta


if __name__ == "__main__":
    raise SystemExit(main())
