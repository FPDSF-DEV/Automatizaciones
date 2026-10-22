"""Informe HTML: tablas y gráficas en una sola página autocontenida."""
from __future__ import annotations

import datetime as _dt
import html
from pathlib import Path

import pandas as pd

from .config import PARAMETROS
from .indicadores import Indicador

CSS = """
:root {
  color-scheme: light;
  --fondo: #f7f7f5; --tarjeta: #ffffff; --tinta: #0b0b0b;
  --tinta-suave: #52514e; --borde: #e5e4e0; --acento: #1c5cab;
  --franja: #fafaf8;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-tema="claro"]) {
    color-scheme: dark;
    --fondo: #111110; --tarjeta: #1a1a19; --tinta: #ffffff;
    --tinta-suave: #c3c2b7; --borde: #383835; --acento: #86b6ef;
    --franja: #1f1f1e;
  }
}
* { box-sizing: border-box; }
body {
  margin: 0; padding: 32px 16px 64px; background: var(--fondo); color: var(--tinta);
  font: 15px/1.6 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif;
}
.envoltura { max-width: 1120px; margin: 0 auto; }
h1 { font-size: 26px; margin: 0 0 4px; letter-spacing: -0.01em; }
h2 { font-size: 19px; margin: 44px 0 12px; color: var(--acento); }
h3 { font-size: 16px; margin: 0 0 2px; }
.meta { color: var(--tinta-suave); font-size: 13px; margin: 0 0 28px; }
.tarjeta {
  background: var(--tarjeta); border: 1px solid var(--borde); border-radius: 12px;
  padding: 20px; margin-bottom: 18px;
}
.desc { color: var(--tinta-suave); font-size: 13.5px; margin: 0 0 14px; }
.graficas { display: grid; gap: 16px; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); align-items: start; }
.graficas.una { grid-template-columns: minmax(320px, 560px); justify-content: center; }
.figura { max-width: 560px; width: 100%; }
.figura img { width: 100%; height: auto; display: block; }
.tabla-envoltura { overflow-x: auto; margin-top: 16px; }
table { border-collapse: collapse; width: 100%; font-size: 13px; }
th, td { padding: 7px 10px; text-align: right; border-bottom: 1px solid var(--borde); white-space: nowrap; }
th:first-child, td:first-child { text-align: left; }
thead th { background: var(--acento); color: #fff; font-size: 12px; text-transform: uppercase; letter-spacing: 0.03em; }
tbody tr:nth-child(even) { background: var(--franja); }
.destacado { font-weight: 700; color: var(--tinta); }
.pie { color: var(--tinta-suave); font-size: 12.5px; margin-top: 40px; border-top: 1px solid var(--borde); padding-top: 16px; }
.parametros { display: flex; flex-wrap: wrap; gap: 10px; margin: 0 0 8px; padding: 0; list-style: none; }
.parametros li { background: var(--franja); border: 1px solid var(--borde); border-radius: 999px; padding: 4px 12px; font-size: 12.5px; }
@media (max-width: 640px) { body { padding: 20px 12px 48px; } .graficas { grid-template-columns: 1fr; } }
"""


def _fmt(valor, formato: str) -> str:
    if pd.isna(valor):
        return "—"
    texto = formato.format(valor)
    # separador de miles con punto y decimales con coma
    return texto.replace(",", "@").replace(".", ",").replace("@", ".")


def _tabla_html(tabla: pd.DataFrame, formatos: dict[str, str], destacada: str) -> str:
    cabeceras = "".join(f"<th>{html.escape(c)}</th>" for c in tabla.columns)
    filas = []
    for anio, fila in tabla.iterrows():
        celdas = []
        for col in tabla.columns:
            clase = ' class="destacado"' if col == destacada else ""
            celdas.append(f"<td{clase}>{_fmt(fila[col], formatos.get(col, '{:,.0f}'))}</td>")
        filas.append(f"<tr><td>{anio}</td>{''.join(celdas)}</tr>")
    return (
        '<div class="tabla-envoltura"><table><thead><tr><th>Año</th>'
        f"{cabeceras}</tr></thead><tbody>{''.join(filas)}</tbody></table></div>"
    )


def _img(ruta: Path, base: Path, alt: str) -> str:
    rel = ruta.relative_to(base).as_posix()
    return (
        f'<div class="figura"><img src="{rel}" alt="{html.escape(alt)}" '
        'loading="lazy"></div>'
    )


def construir(
    indicadores: list[Indicador],
    tablas: dict[str, pd.DataFrame],
    graficas: dict[str, dict[str, dict[str, Path]]],
    comparativas: list[tuple[str, dict[str, Path]]],
    destino: Path,
    origen_datos: Path,
    hospital: str = "",
) -> Path:
    base = destino.parent
    grupos: dict[str, list[Indicador]] = {}
    for ind in indicadores:
        grupos.setdefault(ind.grupo, []).append(ind)

    partes = [
        "<!doctype html><html lang='es'><head><meta charset='utf-8'>",
        "<meta name='viewport' content='width=device-width, initial-scale=1'>",
        "<title>Informe de productividad</title>",
        f"<style>{CSS}</style></head><body><div class='envoltura'>",
        "<h1>Informe de productividad</h1>",
        f"<p class='meta'>{html.escape(hospital) + ' · ' if hospital else ''}"
        f"Generado el {_dt.date.today():%d/%m/%Y} a partir de los reportes "
        f"de <code>{html.escape(origen_datos.name)}/</code>. "
        "Cada gráfica está también en PNG y SVG dentro de <code>graficas/</code>.</p>",
        "<ul class='parametros'>"
        + "".join(
            f"<li><strong>{html.escape(k)}</strong> = {v:g}</li>"
            for k, v in PARAMETROS.items()
        )
        + "</ul>",
    ]

    for titulo_comp, rutas in comparativas:
        partes.append(
            f"<div class='tarjeta'><h3>{html.escape(titulo_comp)}</h3>"
            f"<div class='graficas una'>{_img(rutas['svg'], base, titulo_comp)}</div></div>"
        )

    for grupo, lista in grupos.items():
        partes.append(f"<h2>{html.escape(grupo)}</h2>")
        for ind in lista:
            tabla = tablas[ind.clave]
            imgs = graficas[ind.clave]
            bloque = "".join(
                _img(r["svg"], base, f"{ind.titulo} {clave}") for clave, r in imgs.items()
            )
            partes.append(
                f"<div class='tarjeta'><h3>{html.escape(ind.titulo)}</h3>"
                f"<p class='desc'>{html.escape(ind.descripcion)}</p>"
                f"<div class='graficas'>{bloque}</div>"
                f"{_tabla_html(tabla, ind.formatos(), ind.indicador)}</div>"
            )

    partes.append(
        "<p class='pie'>Los parámetros de arriba son supuestos de cálculo, no datos "
        "medidos; se cambian en <code>prodlib/config.py</code>. Las cifras de "
        "capacidad, producción, nómina y OPS provienen de los CSV de entrada y no "
        "se modifican en ningún momento.</p>"
    )
    partes.append("</div></body></html>")

    destino.write_text("".join(partes), encoding="utf-8")
    return destino
