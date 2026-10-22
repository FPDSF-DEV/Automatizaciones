#!/usr/bin/env python3
"""
Genera el PDF "Primera Fase Ajuste de Cultura Corporativa" con el membrete de
Fundasaberes a partir de un JSON de contenido.

Uso:
    python3 build_pdf.py <contenido.json> <salida.pdf>

Estructura del JSON (ver references/plantilla_documento.md):
{
  "titulo": "Primera Fase Ajuste de Cultura Corporativa para la ESE ...",
  "intro": ["párrafo", ...],
  "contexto": [{"titulo": "Ley 100 de 1993:", "texto": "..."}, ...],
  "antes_resultados": ["párrafo", ...],
  "pasos_skill": ["paso", ...],            # opcional
  "entidad_negrita": "La Empresa Social del Estado ...",
  "mision": "texto que sigue al nombre de la entidad",
  "vision_anio": 2031,
  "vision": "texto que sigue al nombre de la entidad",
  "cierre": ["párrafo", ...],
  "lugar_fecha": "Para mayor constancia se firma en ...",
  "firmantes": [{"cargo": "Psicóloga de Fundasaberes", "cc": "CC. ... de Cartagena", "firma": "ruta/opcional.png"}, ...]
}
Propósitos y valores NO van en este JSON: son fijos y se leen siempre de
assets/contenido_fijo.json (si vienen en el JSON, se ignoran).
Los textos admiten el marcado de ReportLab: <b>, <i>, <u>.
"""
import json
import sys
from pathlib import Path

from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (Image, KeepTogether, ListFlowable, ListItem, Paragraph,
                                SimpleDocTemplate, Spacer, Table, TableStyle)

ASSETS = Path(__file__).resolve().parent.parent / "assets"
HEADER = ASSETS / "header.png"
FOOTER = ASSETS / "footer.png"
FIJO = ASSETS / "contenido_fijo.json"

PAGE_W, PAGE_H = letter
HEADER_H = PAGE_W * 335 / 1699            # proporción de la imagen del membrete
FOOTER_W = 17.6 * cm
FOOTER_H = FOOTER_W * 216 / 1385
MARGIN_X = 2.85 * cm

base = ParagraphStyle("base", fontName="Helvetica", fontSize=11, leading=15.2,
                      alignment=TA_JUSTIFY, spaceAfter=9)
titulo = ParagraphStyle("titulo", parent=base, fontName="Helvetica-Bold", fontSize=14,
                        leading=17, alignment=TA_CENTER, spaceAfter=6)
item = ParagraphStyle("item", parent=base, spaceAfter=2)


def membrete(canvas, doc):
    canvas.saveState()
    canvas.drawImage(str(HEADER), 0, PAGE_H - HEADER_H, width=PAGE_W, height=HEADER_H, mask="auto")
    canvas.drawImage(str(FOOTER), (PAGE_W - FOOTER_W) / 2, 0.55 * cm, width=FOOTER_W, height=FOOTER_H, mask="auto")
    canvas.restoreState()


def P(t, st=base):
    return Paragraph(t, st)


def viñetas(textos, simbolo="bullet", start=None):
    items = [ListItem(P(t, item), leftIndent=18) for t in textos]
    kw = dict(bulletType="bullet", start="•" if simbolo == "bullet" else "-",
              leftIndent=18, bulletFontSize=10, spaceAfter=8)
    return ListFlowable(items, **kw)


def construir(c, salida):
    doc = SimpleDocTemplate(str(salida), pagesize=letter,
                            leftMargin=MARGIN_X, rightMargin=MARGIN_X,
                            topMargin=HEADER_H + 0.4 * cm, bottomMargin=FOOTER_H + 1.3 * cm,
                            title=c.get("titulo", ""), author="Fundasaberes")
    s = [P(c["titulo"], titulo)]
    s += [P(t) for t in c.get("intro", [])]
    if c.get("contexto"):
        s.append(viñetas([f"<b>{x['titulo']}</b> {x['texto']}" for x in c["contexto"]]))
    s += [P(t) for t in c.get("antes_resultados", [])]
    if c.get("pasos_skill"):
        s.append(viñetas([f"<b>Paso {i}.</b> {p}" for i, p in enumerate(c["pasos_skill"], 1)]))
    s.append(P("<b>Resultados:</b>"))

    ent = c["entidad_negrita"]
    s.append(P(f"<b><i>Misión:</i> {ent}</b>; {c['mision']}"))
    s.append(P(f"<b><i>Visión:</i></b> Para el año {c['vision_anio']}, <b>{ent}</b>, {c['vision']}"))
    fijo = json.loads(FIJO.read_text(encoding="utf-8"))
    s.append(P(f"<b>PROPÓSITOS:</b> {fijo['propositos_intro']}"))
    s.append(viñetas(fijo["propositos"], simbolo="dash"))

    s.append(P(f"<b>VALORES:</b> {fijo['valores_intro']}"))
    s.append(viñetas([f"{v['nombre']}: {v['definicion']}" for v in fijo["valores"]], simbolo="dash"))

    s += [P(t) for t in c.get("cierre", [])]
    if c.get("lugar_fecha"):
        s.append(P(c["lugar_fecha"]))

    firmas = c.get("firmantes", [])
    if firmas:
        celdas = []
        for f in firmas:
            bloque = []
            if f.get("firma") and Path(f["firma"]).exists():
                bloque.append(Image(f["firma"], width=4.5 * cm, height=1.6 * cm, kind="proportional"))
            else:
                bloque.append(Spacer(1, 1.6 * cm))
            bloque.append(P("_" * 32, ParagraphStyle("l", parent=base, spaceAfter=0, alignment=0)))
            bloque.append(P(f"<b>{f['cargo']}</b>", ParagraphStyle("c", parent=base, spaceAfter=0, alignment=0)))
            bloque.append(P(f.get("cc", ""), ParagraphStyle("d", parent=base, spaceAfter=0, alignment=0)))
            celdas.append(bloque)
        ancho = (PAGE_W - 2 * MARGIN_X) / len(celdas)
        t = Table([celdas], colWidths=[ancho] * len(celdas))
        t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
        s.append(KeepTogether([Spacer(1, 0.6 * cm), t]))

    doc.build(s, onFirstPage=membrete, onLaterPages=membrete)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    contenido = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    construir(contenido, Path(sys.argv[2]))
    print("PDF generado:", sys.argv[2])
