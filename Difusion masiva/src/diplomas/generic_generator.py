from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Tuple
import csv
import re

from .template_processor import TemplateProcessor
from .utils.naming import slugify
from .oficios_generator import _hyperlink_email_in_doc

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")

# Fuente de un valor mapeado: columna de los datos o texto fijo escrito en la UI
SOURCE_COLUMN = "columna"
SOURCE_FIXED = "fijo"


def validate_rows(
    rows: List[Dict[str, str]],
    email_column: str | None,
) -> Tuple[List[Dict[str, str]], List[Dict[str, str]]]:
    """Separa avisos de saneamiento sin descartar filas (el flujo genérico no
    conoce el caso de uso, así que reporta en vez de imponer reglas).

    Returns:
        (avisos_email, avisos_duplicados)
    """
    invalid: List[Dict[str, str]] = []
    duplicates: List[Dict[str, str]] = []
    if not email_column:
        return invalid, duplicates
    seen: Dict[str, int] = {}
    for idx, row in enumerate(rows, start=1):
        email = (row.get(email_column) or "").strip()
        if not email:
            invalid.append({"fila": str(idx), "email": "", "detalle": "sin email"})
            continue
        if not EMAIL_RE.match(email):
            invalid.append({"fila": str(idx), "email": email, "detalle": "formato inválido"})
            continue
        key = email.lower()
        if key in seen:
            duplicates.append({
                "fila": str(idx), "email": email,
                "detalle": f"duplicado de la fila {seen[key]}",
            })
        else:
            seen[key] = idx
    return invalid, duplicates


def run_generic_generation(
    template: Path,
    rows: List[Dict[str, str]],
    outdir: Path,
    mapping: Dict[str, Tuple[str, str]],
    base_name: str = "DOCUMENTO",
    email_column: str | None = None,
    filename_column: str | None = None,
    skip_rows_without_email: bool = False,
) -> Dict[str, object]:
    """Genera documentos DOCX a partir de cualquier plantilla y cualquier dato tabular.

    Args:
        template: plantilla DOCX (sus placeholders se detectan con extract_placeholders)
        rows: registros con los nombres de columna originales de la fuente
        outdir: carpeta de salida
        mapping: {placeholder: (fuente, valor)} donde fuente es "columna" (valor =
            nombre de columna) o "fijo" (valor = texto literal para todas las filas)
        base_name: nombre base de los archivos generados
        email_column: columna con el email del destinatario (opcional). Si se indica,
            el email se convierte en hipervínculo mailto: dentro del documento y se
            guarda en el manifest para el paso de envío.
        filename_column: columna cuyo valor se agrega al nombre del archivo para
            identificarlo (ej. municipio o nombre de la persona)
        skip_rows_without_email: si True, no genera documento para filas sin email válido

    Returns:
        {"ok": n, "fail": n, "saltados": n, "con_email": n,
         "manifest": ruta, "errores": [detalle por fila fallida]}

    El manifest.csv resultante contiene TODAS las columnas originales más
    `_filename` y `_email`, y es la única entrada que necesitan los pasos de
    exportar PDF y enviar correos.
    """
    outdir.mkdir(parents=True, exist_ok=True)

    ok = 0
    fail = 0
    saltados = 0
    con_email = 0
    errores: List[str] = []
    manifest_rows: List[Dict[str, str]] = []

    columns: List[str] = []
    for row in rows:
        for k in row.keys():
            if k not in columns:
                columns.append(k)

    for idx, row in enumerate(rows, start=1):
        email = (row.get(email_column) or "").strip() if email_column else ""
        email_valido = bool(email and EMAIL_RE.match(email))

        if skip_rows_without_email and not email_valido:
            saltados += 1
            continue

        try:
            placeholders: Dict[str, str] = {}
            for ph, (source, value) in mapping.items():
                if source == SOURCE_FIXED:
                    placeholders[ph] = value
                else:
                    placeholders[ph] = (row.get(value) or "").strip()

            proc = TemplateProcessor(template, placeholders)
            doc = proc.render()

            if email_valido:
                _hyperlink_email_in_doc(doc, email)
                con_email += 1

            suffix = ""
            if filename_column and (row.get(filename_column) or "").strip():
                suffix = "-" + slugify(row[filename_column].strip())
            filename = f"{idx:04d}-{base_name}{suffix}.docx"
            doc.save(outdir / filename)
            ok += 1

            manifest_rows.append({
                **{c: row.get(c, "") for c in columns},
                "_filename": filename,
                "_email": email if email_valido else "",
            })
        except Exception as e:  # noqa: BLE001
            fail += 1
            errores.append(f"Fila {idx}: {e}")

    manifest_path = outdir / "manifest.csv"
    headers = columns + ["_filename", "_email"]
    with manifest_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        for m in manifest_rows:
            writer.writerow({h: m.get(h, "") for h in headers})

    return {
        "ok": ok,
        "fail": fail,
        "saltados": saltados,
        "con_email": con_email,
        "manifest": str(manifest_path),
        "errores": errores,
    }


def write_manifest_only(
    rows: List[Dict[str, str]],
    outdir: Path,
    email_column: str,
    skip_rows_without_email: bool = True,
) -> Dict[str, object]:
    """Crea el manifest.csv de una campaña SIN generar documentos.

    Pensado para difusiones donde todos reciben el mismo adjunto (ej. un oficio
    PDF único): el paso de envío solo necesita el manifest con las columnas
    originales más `_filename` (vacío) y `_email`.

    Returns:
        {"ok": n, "saltados": n, "manifest": ruta}
    """
    outdir.mkdir(parents=True, exist_ok=True)

    columns: List[str] = []
    for row in rows:
        for k in row.keys():
            if k not in columns and k not in ("_filename", "_email"):
                columns.append(k)

    manifest_rows: List[Dict[str, str]] = []
    saltados = 0
    for row in rows:
        email = (row.get(email_column) or "").strip()
        email_valido = bool(email and EMAIL_RE.match(email))
        if skip_rows_without_email and not email_valido:
            saltados += 1
            continue
        manifest_rows.append({
            **{c: row.get(c, "") for c in columns},
            "_filename": "",
            "_email": email if email_valido else "",
        })

    manifest_path = outdir / "manifest.csv"
    headers = columns + ["_filename", "_email"]
    with manifest_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        for m in manifest_rows:
            writer.writerow({h: m.get(h, "") for h in headers})

    return {"ok": len(manifest_rows), "saltados": saltados, "manifest": str(manifest_path)}


__all__ = [
    "run_generic_generation",
    "write_manifest_only",
    "validate_rows",
    "SOURCE_COLUMN",
    "SOURCE_FIXED",
    "EMAIL_RE",
]
