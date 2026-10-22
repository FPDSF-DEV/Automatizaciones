"""Dashboard HTML de una sola página, autocontenido (§8 del PLAN).

Los SVG van **en línea**, no con `<img src>`: así el archivo abre con doble clic
desde el explorador, sin servidor y sin depender de rutas relativas. Sin CDN,
sin fuentes externas y con el mínimo de JavaScript — solo el que resalta la
sección activa en el índice lateral.
"""

from __future__ import annotations

import html
import io
import re
from datetime import datetime
from pathlib import Path

from .catalogo import CATALOGO
from .catalogo_graficas import SECCIONES
from .estilo import Tema, formato_es
from .resolucion import Resultado


def svg_en_linea(fig, prefijo: str) -> str:
    """La figura como marcado SVG listo para incrustar.

    Los ids internos de matplotlib (clips, gradientes) se renombran por gráfica:
    veinte SVG en la misma página compartirían nombres y un clip acabaría
    recortando el dibujo de otra tarjeta.
    """
    memoria = io.StringIO()
    fig.savefig(memoria, format="svg", facecolor=fig.get_facecolor(), edgecolor="none")
    marcado = memoria.getvalue()

    inicio = marcado.find("<svg")
    if inicio > 0:
        marcado = marcado[inicio:]

    # El bloque RDF de matplotlib (autor, fecha, licencia) no aporta nada dentro
    # del HTML y son 52 copias del mismo texto.
    marcado = re.sub(r"<metadata>.*?</metadata>", "", marcado, flags=re.S)

    ids = set(re.findall(r'id="([^"]+)"', marcado))
    for identificador in ids:
        nuevo = f"{prefijo}-{identificador}"
        marcado = marcado.replace(f'id="{identificador}"', f'id="{nuevo}"')
        marcado = marcado.replace(f"url(#{identificador})", f"url(#{nuevo})")
        marcado = marcado.replace(f'xlink:href="#{identificador}"', f'xlink:href="#{nuevo}"')
        marcado = marcado.replace(f'href="#{identificador}"', f'href="#{nuevo}"')

    # Que escale con la tarjeta: manda el viewBox, no los puntos.
    marcado = re.sub(r'(<svg[^>]*?)\swidth="[^"]*"', r"\1", marcado, count=1)
    marcado = re.sub(r'(<svg[^>]*?)\sheight="[^"]*"', r"\1", marcado, count=1)
    marcado = marcado.replace(
        "<svg ", '<svg style="width:100%;height:auto;display:block" ', 1
    )
    return marcado


def _tarjeta_dato(etiqueta: str, valor: str, nota: str = "") -> str:
    return (
        '<div class="tarjeta-dato">'
        f'<span class="dato-etiqueta">{html.escape(etiqueta)}</span>'
        f'<span class="dato-valor">{html.escape(valor)}</span>'
        f'<span class="dato-nota">{html.escape(nota)}</span>'
        "</div>"
    )


def _tabla(encabezados: list[str], filas: list[list[str]]) -> str:
    cabeza = "".join(f"<th>{html.escape(c)}</th>" for c in encabezados)
    cuerpo = "".join(
        "<tr>" + "".join(
            f"<td{' class=\"col-entidad\"' if i == 0 else ''}>{html.escape(c)}</td>"
            for i, c in enumerate(fila)
        ) + "</tr>"
        for fila in filas
    )
    return (
        '<div class="tabla-envoltura"><table>'
        f"<thead><tr>{cabeza}</tr></thead><tbody>{cuerpo}</tbody>"
        "</table></div>"
    )


def _estilos(tema: Tema) -> str:
    """El cromo de la página se adapta al sistema; las tarjetas conservan la superficie
    con la que se generaron los SVG."""
    oscuro = tema.nombre == "oscuro"
    chrome_fondo = "#15151a" if oscuro else "#f3f2ee"
    chrome_texto = "#f5f5f2" if oscuro else "#0b0b0b"
    chrome_suave = "#a3a29b" if oscuro else "#52514e"
    borde = "#2e2e2b" if oscuro else "#e6e5e1"
    return f"""
:root {{
  --fondo: {chrome_fondo};
  --texto: {chrome_texto};
  --suave: {chrome_suave};
  --borde: {borde};
  --superficie: {tema.superficie};
  --superficie-texto: {tema.texto_primario};
  --superficie-suave: {tema.texto_secundario};
  --acento: {tema.paleta[0]};
}}
/* Modo oscuro solo para el cromo de la página: los SVG se generaron con la
   paleta {tema.nombre}, así que las tarjetas de gráfica no cambian de fondo. */
@media (prefers-color-scheme: dark) {{
  :root {{
    --fondo: #15151a;
    --texto: #f5f5f2;
    --suave: #a3a29b;
    --borde: #2e2e2b;
  }}
}}
* {{ box-sizing: border-box; }}
body {{
  margin: 0;
  background: var(--fondo);
  color: var(--texto);
  font-family: "Segoe UI", system-ui, -apple-system, "Helvetica Neue", Arial, sans-serif;
  font-size: 15px;
  line-height: 1.5;
}}
a {{ color: inherit; }}
.envoltura {{ max-width: 1500px; margin: 0 auto; padding: 0 24px 64px; }}
header.principal {{ padding: 40px 0 20px; border-bottom: 1px solid var(--borde); }}
header.principal h1 {{ margin: 0 0 8px; font-size: 30px; line-height: 1.2; }}
header.principal p {{ margin: 0; color: var(--suave); }}
.tarjetas {{
  display: grid; gap: 14px; margin: 24px 0 8px;
  grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
}}
.tarjeta-dato {{
  background: var(--superficie); color: var(--superficie-texto);
  border: 1px solid var(--borde); border-radius: 10px; padding: 16px 18px;
  display: flex; flex-direction: column; gap: 2px;
}}
.dato-etiqueta {{ font-size: 12px; letter-spacing: .04em; text-transform: uppercase;
  color: var(--superficie-suave); }}
.dato-valor {{ font-size: 26px; font-weight: 600; }}
.dato-nota {{ font-size: 13px; color: var(--superficie-suave); }}
.cuerpo {{ display: grid; grid-template-columns: 230px minmax(0, 1fr); gap: 32px;
  align-items: start; margin-top: 28px; }}
nav.indice {{ position: sticky; top: 20px; }}
nav.indice ol {{ list-style: none; margin: 0; padding: 0; }}
nav.indice a {{
  display: block; padding: 9px 12px; border-radius: 8px; text-decoration: none;
  color: var(--suave); border-left: 3px solid transparent; font-size: 14px;
}}
nav.indice a:hover {{ background: color-mix(in srgb, var(--texto) 7%, transparent); }}
nav.indice a.activo {{ color: var(--texto); border-left-color: var(--acento); font-weight: 600; }}
section.bloque {{ padding-top: 8px; margin-bottom: 40px; scroll-margin-top: 20px; }}
section.bloque > h2 {{ font-size: 21px; margin: 0 0 4px; }}
section.bloque > p.conteo {{ margin: 0 0 18px; color: var(--suave); font-size: 14px; }}
.tarjeta-gráfica {{
  background: var(--superficie); color: var(--superficie-texto);
  border: 1px solid var(--borde); border-radius: 12px; padding: 18px 18px 12px;
  margin-bottom: 20px; overflow: hidden;
}}
.tarjeta-gráfica .figura {{ margin: 0; }}
details {{ margin-top: 10px; border-top: 1px solid var(--borde); padding-top: 10px; }}
summary {{ cursor: pointer; color: var(--superficie-suave); font-size: 14px; }}
summary:hover {{ color: var(--superficie-texto); }}
.tabla-envoltura {{ overflow-x: auto; margin-top: 12px; }}
table {{ border-collapse: collapse; font-size: 13px; min-width: 100%; }}
th, td {{ text-align: right; padding: 7px 12px; border-bottom: 1px solid var(--borde);
  white-space: nowrap; }}
th {{ color: var(--superficie-suave); font-weight: 600; text-align: right; }}
th:first-child, td.col-entidad {{ text-align: left; }}
.avisos {{ background: var(--superficie); color: var(--superficie-texto);
  border: 1px solid var(--borde); border-radius: 12px; padding: 18px 22px; }}
.avisos h3 {{ margin: 0 0 8px; font-size: 16px; }}
.avisos ul {{ margin: 0 0 14px; padding-left: 20px; color: var(--superficie-suave); }}
.avisos code {{ font-size: 12px; }}
footer.pie {{ margin-top: 32px; color: var(--suave); font-size: 13px; }}
@media (max-width: 900px) {{
  .cuerpo {{ grid-template-columns: minmax(0, 1fr); }}
  nav.indice {{ position: static; }}
  nav.indice ol {{ display: flex; flex-wrap: wrap; gap: 6px; }}
  nav.indice a {{ border-left: 0; border-bottom: 3px solid transparent; }}
  nav.indice a.activo {{ border-left-color: transparent; border-bottom-color: var(--acento); }}
}}
"""


_JS = """
// Lo único que hace JavaScript aquí: marcar en el índice la sección visible.
(function () {
  var enlaces = Array.prototype.slice.call(document.querySelectorAll('nav.indice a'));
  var secciones = enlaces
    .map(function (a) { return document.querySelector(a.getAttribute('href')); })
    .filter(Boolean);
  if (!secciones.length || !('IntersectionObserver' in window)) return;
  var observador = new IntersectionObserver(function (entradas) {
    entradas.forEach(function (entrada) {
      if (!entrada.isIntersecting) return;
      enlaces.forEach(function (a) {
        a.classList.toggle('activo', a.getAttribute('href') === '#' + entrada.target.id);
      });
    });
  }, { rootMargin: '-10% 0px -75% 0px' });
  secciones.forEach(function (s) { observador.observe(s); });
})();
"""


def construir_html(
    renders,
    omitidas,
    res: Resultado,
    tema: Tema,
    titulo: str,
    anio_corte: int,
    filas_leidas: int,
    archivos: int,
) -> str:
    generado = datetime.now().strftime("%d/%m/%Y %H:%M")

    poblaciones = [res.numero("POB_TOTAL", e) for e in res.entidades]
    poblacion_total = sum(p for p in poblaciones if p is not None)
    coberturas = [res.numero("COBERTURA_SGSSS", e) for e in res.entidades]
    coberturas = [c for c in coberturas if c is not None]
    cobertura_media = sum(coberturas) / len(coberturas) if coberturas else None
    resueltos = sum(1 for i in CATALOGO if res.disponible(i.id))

    tarjetas = [
        _tarjeta_dato("Entidades analizadas", str(len(res.entidades)),
                      res.departamento or ""),
        _tarjeta_dato("Población del conjunto", formato_es(poblacion_total, 0),
                      f"dato {res.anios.get('POB_TOTAL') or '—'}"),
        _tarjeta_dato(
            "Cobertura SGSSS promedio",
            f"{formato_es(cobertura_media, 1)} %" if cobertura_media is not None else "—",
            "afiliados sobre población",
        ),
        _tarjeta_dato("Indicadores resueltos", f"{resueltos}/{len(CATALOGO)}",
                      f"{len(res.faltantes)} sin datos"),
    ]

    # --- avisos
    avisos: list[tuple[str, list[str]]] = []
    if res.faltantes:
        avisos.append((
            f"Indicadores no disponibles en los datos cargados ({len(res.faltantes)})",
            [f"{res.etiqueta(i)} <code>{html.escape(i)}</code>" for i in res.faltantes],
        ))
    if omitidas:
        avisos.append((
            f"Gráficas omitidas por falta de datos ({len(omitidas)})",
            [f"#{o.numero} {html.escape(o.titulo)} "
             f"<code>{html.escape(', '.join(o.series))}</code>" for o in omitidas],
        ))
    if not avisos:
        avisos.append(("Sin avisos", [
            "Todos los indicadores del catálogo se resolvieron y las 52 gráficas "
            "se generaron."
        ]))

    return construir_html_general(
        renders=renders,
        titulo=titulo,
        resumen=(
            f"{html.escape(res.departamento or 'Departamento sin identificar')} · "
            f"{len(res.entidades)} entidades · año de corte {anio_corte} · "
            f"{formato_es(filas_leidas, 0)} filas de {archivos} archivo(s) · "
            f"generado el {generado}"
        ),
        tarjetas=tarjetas,
        secciones=SECCIONES,
        avisos=avisos,
        tema=tema,
        nota_pie=(
            "Fuente de todos los datos: TerriData (DNP). Las gráficas se generaron "
            f"con el tema <strong>{tema.nombre}</strong>; los PNG y SVG equivalentes "
            "están en <code>png/</code> y <code>svg/</code>."
        ),
    )


def construir_html_general(
    *,
    renders,
    titulo: str,
    resumen: str,
    tarjetas: list[str],
    secciones: list[tuple[str, str]],
    avisos: list[tuple[str, list[str]]],
    tema: Tema,
    nota_pie: str = "",
    sustantivo: tuple[str, str] = ("gráfica", "gráficas"),
) -> str:
    """El motor del dashboard, compartido por los dos entregables.

    `tarjetas` viene ya armado con `_tarjeta_dato`; `avisos` es una lista de
    (título, viñetas) y `secciones` fija el orden y los nombres de los bloques.
    """
    por_seccion: dict[str, list] = {}
    for render in renders:
        por_seccion.setdefault(render.spec.seccion, []).append(render)

    indice = []
    bloques = []
    for id_seccion, nombre in secciones:
        del_bloque = por_seccion.get(id_seccion)
        if not del_bloque:
            continue
        indice.append(
            f'<li><a href="#{id_seccion}">{html.escape(nombre)}</a></li>'
        )
        tarjetas_graficas = []
        for render in del_bloque:
            svg = render.svg or svg_en_linea(render.fig, render.archivo)
            tarjetas_graficas.append(
                '<article class="tarjeta-gráfica">'
                f'<figure class="figura">{svg}</figure>'
                "<details><summary>Ver los datos que alimentan esta figura</summary>"
                f"{_tabla(render.encabezados, render.filas)}</details>"
                "</article>"
            )
        plural = sustantivo[0] if len(del_bloque) == 1 else sustantivo[1]
        bloques.append(
            f'<section class="bloque" id="{id_seccion}">'
            f"<h2>{html.escape(nombre)}</h2>"
            f'<p class="conteo">{len(del_bloque)} {plural}</p>'
            + "".join(tarjetas_graficas)
            + "</section>"
        )

    avisos_html = "".join(
        f"<h3>{titulo_aviso}</h3><ul>"
        + "".join(f"<li>{v}</li>" for v in viñetas)
        + "</ul>"
        for titulo_aviso, viñetas in avisos
    )
    bloque_avisos = (
        '<section class="bloque" id="avisos"><h2>Avisos</h2>'
        f'<div class="avisos">{avisos_html}</div></section>'
    )
    indice.append('<li><a href="#avisos">Avisos</a></li>')

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(titulo)}</title>
<style>{_estilos(tema)}</style>
</head>
<body>
<div class="envoltura">
  <header class="principal">
    <h1>{html.escape(titulo)}</h1>
    <p>{resumen}</p>
    <div class="tarjetas">{''.join(tarjetas)}</div>
  </header>
  <div class="cuerpo">
    <nav class="indice"><ol>{''.join(indice)}</ol></nav>
    <main>
      {''.join(bloques)}
      {bloque_avisos}
      <footer class="pie">{nota_pie}</footer>
    </main>
  </div>
</div>
<script>{_JS}</script>
</body>
</html>
"""


def escribir_dashboard(destino, **kwargs) -> Path:
    ruta = Path(destino)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(construir_html(**kwargs), encoding="utf-8")
    return ruta
