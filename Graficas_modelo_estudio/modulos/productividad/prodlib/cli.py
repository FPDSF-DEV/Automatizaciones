"""Punto de entrada: lee los CSV, calcula, dibuja y arma el informe."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

from .carga import ErrorDeDatos, cargar, guardar_consolidado, nombre_hospital
from .config import DATOS, SALIDA
from .graficas import barras, comparativa, generar
from .indicadores import (
    INDICADORES,
    ConceptoNoEncontrado,
    resumen,
)


def ejecutar(carpeta_datos: Path, carpeta_salida: Path) -> int:
    datos = cargar(carpeta_datos)
    hospital = nombre_hospital(carpeta_datos)
    carpeta_graficas = carpeta_salida / "graficas"
    carpeta_tablas = carpeta_salida / "tablas"
    carpeta_salida.mkdir(parents=True, exist_ok=True)
    carpeta_tablas.mkdir(parents=True, exist_ok=True)
    guardar_consolidado(datos, carpeta_salida / "datos_consolidados")
    if hospital:
        print(f"Entidad: {hospital}")

    tablas: dict[str, pd.DataFrame] = {}
    graficas: dict[str, dict] = {}
    for ind in INDICADORES:
        tabla = ind.calcular(datos)
        tablas[ind.clave] = tabla
        graficas[ind.clave] = generar(ind, tabla, carpeta_graficas)
        tabla.to_csv(carpeta_tablas / f"{ind.clave}.csv", float_format="%.6f")
        print(f"  · {ind.titulo}: {len(tabla)} años")

    # Oferta de talento humano OPS: contratos por año, apoyo frente a operativo.
    oferta_ops = datos["ops"].loc[["APOYO", "OPERATIVO"]].T.rename_axis("Año")
    oferta_ops.to_csv(carpeta_tablas / "oferta_ops.csv", float_format="%.0f")
    titulo_oferta = "Oferta de talento humano (OPS)" + (f" - {hospital}" if hospital else "")

    consultorios = [i for i in INDICADORES if i.clave in ("consulta_externa", "urgencias")]
    comparativas = [
        (
            "Oferta de talento humano (OPS) — contratos por año",
            barras(
                oferta_ops, ["APOYO", "OPERATIVO"], titulo_oferta, "Contratos",
                carpeta_graficas, "oferta_ops",
            ),
        ),
        (
            "Consultas por consultorio por día",
            comparativa(
                tablas, consultorios,
                "Consultas por consultorio por día", "Consultas / consultorio / día",
                carpeta_graficas, "comparativa_consultorios",
            ),
        )
    ]

    tabla_resumen = resumen(datos)
    tabla_resumen.to_csv(carpeta_tablas / "resumen.csv", float_format="%.6f")

    from .informe import construir

    informe = construir(
        INDICADORES, tablas, graficas, comparativas,
        carpeta_salida / "informe.html", carpeta_datos, hospital,
    )
    print(f"\nInforme: {informe}")
    print(f"Gráficas (PNG y SVG): {carpeta_graficas}")
    print(f"Tablas calculadas: {carpeta_tablas}")
    print(f"Datos consolidados de los reportes: {carpeta_salida / 'datos_consolidados'}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="productividad",
        description="Calcula los indicadores de productividad y genera las gráficas.",
    )
    parser.add_argument("--datos", type=Path, default=DATOS,
                        help="carpeta SIHO con Formularios_Anuales/ y Consultas_Detalladas/ (por defecto: DATA/SIHO/)")
    parser.add_argument("--salida", type=Path, default=SALIDA,
                        help="carpeta donde se escriben los resultados (por defecto: SALIDAS/productividad/)")
    args = parser.parse_args(argv)
    try:
        return ejecutar(args.datos, args.salida)
    except (ErrorDeDatos, ConceptoNoEncontrado) as exc:
        print(f"Error en los datos: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
