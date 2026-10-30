from __future__ import annotations

from pathlib import Path
from typing import List
import re
import unicodedata

from docx import Document


PLACEHOLDER_RE = re.compile(r"\{\{[^{}]+\}\}")


def _iter_paragraph_texts(doc: Document):
    """Itera el texto completo de cada párrafo del documento: cuerpo, tablas y
    encabezados/pies. Une los runs para detectar placeholders partidos por Word."""
    for p in doc.paragraphs:
        yield "".join(r.text for r in p.runs) or p.text
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for p in cell.paragraphs:
                    yield "".join(r.text for r in p.runs) or p.text
    for section in doc.sections:
        for container in (section.header, section.footer):
            for p in container.paragraphs:
                yield "".join(r.text for r in p.runs) or p.text


def extract_placeholders(template_path: Path) -> List[str]:
    """Devuelve los placeholders {{...}} presentes en la plantilla, en orden de aparición.

    Esto permite que la UI muestre exactamente lo que la plantilla necesita,
    en lugar de listas fijas por defecto que no siempre coinciden.
    """
    doc = Document(str(template_path))
    found: List[str] = []
    for text in _iter_paragraph_texts(doc):
        for match in PLACEHOLDER_RE.findall(text):
            if match not in found:
                found.append(match)
    return found


def _normalize(s: str) -> str:
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^a-z0-9]", "", s.lower())
    # Unificar sinónimos frecuentes en directorios en español
    s = s.replace("correoelectronico", "email").replace("correo", "email").replace("mail", "email")
    return s


def guess_placeholder_column(placeholder: str, columns: List[str]) -> str:
    """Sugiere la columna de datos que mejor coincide con un placeholder por nombre.

    Compara nombres normalizados (sin acentos/símbolos y con sinónimos de email
    unificados). Puntúa: igualdad > prefijo > contención, y ante empate gana el
    solapamiento más largo. Devuelve "" si no hay candidato razonable.
    """
    target = _normalize(placeholder.strip("{}"))
    if not target:
        return ""
    best_col = ""
    best_score = 0.0
    for col in columns:
        norm = _normalize(col)
        if not norm:
            continue
        if norm == target:
            score = 300.0
        elif target.startswith(norm) or norm.startswith(target):
            score = 200.0 + min(len(norm), len(target))
        elif target in norm or norm in target:
            score = 100.0 + min(len(norm), len(target))
        else:
            continue
        if score > best_score:
            best_score = score
            best_col = col
    return best_col


__all__ = ["extract_placeholders", "guess_placeholder_column", "PLACEHOLDER_RE"]
