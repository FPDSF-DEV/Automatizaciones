from __future__ import annotations

from pathlib import Path
from typing import Dict, List
import csv
import re
import shutil
import unicodedata


def _normalize(s: str) -> str:
    s = unicodedata.normalize("NFKD", (s or "").strip())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", s).strip().upper()


def _row_matches_filter(row: Dict[str, str], flt: Dict[str, str]) -> bool:
    """True si TODAS las columnas del filtro coinciden (comparación normalizada:
    sin tildes, sin importar mayúsculas/espacios extra) con el valor de la fila."""
    return all(_normalize(row.get(col, "")) == _normalize(val) for col, val in flt.items())


def parse_exclusion_pairs(text: str, columns: List[str]) -> List[Dict[str, str]]:
    """Convierte líneas pegadas por el usuario en filtros de exclusión.

    Cada línea es una lista separada por comas de valores, en el mismo orden
    que `columns` (ej. columns=["municipio","departamento"] y la línea
    "Manaure, Cesar" produce {"municipio": "Manaure", "departamento": "Cesar"}).
    Si una línea trae menos valores que columnas, solo se filtra por las
    columnas presentes (match más laxo); las líneas vacías se ignoran.
    """
    filters: List[Dict[str, str]] = []
    for line in text.splitlines():
        parts = [p.strip() for p in line.split(",") if p.strip() != ""]
        if not parts:
            continue
        flt = {columns[i]: parts[i] for i in range(min(len(parts), len(columns)))}
        if flt:
            filters.append(flt)
    return filters


def find_matches(rows: List[Dict[str, str]], filters: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """Filas que coincidirían con `exclude_records` para estos filtros, sin tocar nada.

    Pensado para mostrar una vista previa en la UI antes de mover archivos.
    """
    return [r for r in rows if any(_row_matches_filter(r, flt) for flt in filters)]


def exclude_records(
    outdir: Path,
    filters: List[Dict[str, str]],
    manifest_name: str = "manifest.csv",
    pdf_subdir: str = "pdf",
    archive_subdir: str = "excluidos",
) -> Dict[str, object]:
    """Excluye registros de una carpeta ya generada por el módulo genérico.

    No borra nada de forma irreversible: mueve el DOCX y el PDF (si existen)
    de cada registro excluido a `outdir/excluidos/` (y `.../excluidos/pdf/`),
    reescribe el manifest.csv dejando solo lo que sí se debe enviar, y guarda
    `excluidos/manifest_excluidos.csv` con las filas quitadas y por qué
    filtro coincidieron, para tener trazabilidad de por qué no se envió algo.

    Args:
        outdir: carpeta de salida de una generación previa (contiene manifest.csv)
        filters: lista de filtros; una fila se excluye si coincide con
            CUALQUIERA de ellos (OR entre filtros, AND dentro de cada filtro)
        manifest_name: nombre del manifest dentro de outdir
        pdf_subdir: subcarpeta de PDFs dentro de outdir
        archive_subdir: subcarpeta donde se archivan los excluidos

    Returns:
        {"total": n, "excluidos": n, "restantes": n,
         "sin_archivo_docx": [...], "sin_archivo_pdf": [...],
         "detalle": [{"fila", "motivo_filtro", **datos_fila}]}
    """
    manifest_path = outdir / manifest_name
    if not manifest_path.exists():
        raise FileNotFoundError(f"No existe el manifest: {manifest_path}")

    with manifest_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        rows = list(reader)

    archive_dir = outdir / archive_subdir
    archive_pdf_dir = archive_dir / pdf_subdir
    pdf_dir = outdir / pdf_subdir

    keep: List[Dict[str, str]] = []
    excluded_detail: List[Dict[str, str]] = []
    missing_docx: List[str] = []
    missing_pdf: List[str] = []

    for idx, row in enumerate(rows, start=1):
        matched_filter = None
        for flt in filters:
            if _row_matches_filter(row, flt):
                matched_filter = flt
                break

        if matched_filter is None:
            keep.append(row)
            continue

        filename = (row.get("_filename") or "").strip()
        if filename:
            archive_dir.mkdir(parents=True, exist_ok=True)
            docx_src = outdir / filename
            if docx_src.exists():
                shutil.move(str(docx_src), str(archive_dir / filename))
            else:
                missing_docx.append(filename)

            pdf_name = Path(filename).with_suffix(".pdf").name
            pdf_src = pdf_dir / pdf_name
            if pdf_src.exists():
                archive_pdf_dir.mkdir(parents=True, exist_ok=True)
                shutil.move(str(pdf_src), str(archive_pdf_dir / pdf_name))
            elif pdf_dir.exists():
                missing_pdf.append(pdf_name)

        excluded_detail.append({
            "fila": str(idx),
            "motivo_filtro": ", ".join(f"{k}={v}" for k, v in matched_filter.items()),
            **row,
        })

    with manifest_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in keep:
            writer.writerow({c: r.get(c, "") for c in fieldnames})

    if excluded_detail:
        archive_dir.mkdir(parents=True, exist_ok=True)
        excl_headers = ["fila", "motivo_filtro"] + fieldnames
        with (archive_dir / "manifest_excluidos.csv").open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=excl_headers)
            writer.writeheader()
            for r in excluded_detail:
                writer.writerow({h: r.get(h, "") for h in excl_headers})

    return {
        "total": len(rows),
        "excluidos": len(excluded_detail),
        "restantes": len(keep),
        "sin_archivo_docx": missing_docx,
        "sin_archivo_pdf": missing_pdf,
        "detalle": excluded_detail,
    }


__all__ = ["exclude_records", "parse_exclusion_pairs", "find_matches"]
