from __future__ import annotations

from pathlib import Path
import logging
import csv
from typing import List

from docx2pdf import convert
from pypdf import PdfWriter, PdfReader


def convert_and_encrypt(docx_dir: Path, output_dir: Path | None = None, manifest: Path | None = None) -> None:
    """Convierte todos los .docx en docx_dir a PDF y aplica cifrado si hay manifest con cc.

    Manifest esperado (csv): index, filename, nombre, cc
    Password = cc (sin espacios). Si cc vacío => sin cifrado.
    """
    log = logging.getLogger("diplomas")
    if output_dir is None:
        output_dir = docx_dir / "pdf"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Mapear filename -> cc desde manifest si existe
    cc_map = {}
    if manifest and manifest.exists():
        try:
            with manifest.open("r", encoding="utf-8") as fh:
                reader = csv.DictReader(fh)
                for row in reader:
                    fn = row.get("filename")
                    cc = (row.get("cc") or "").strip()
                    if fn:
                        cc_map[fn] = cc
        except Exception as e:  # noqa: BLE001
            log.warning("No se pudo leer manifest para cifrado: %s", e)

    docx_files = sorted(docx_dir.glob("*.docx"))
    if not docx_files:
        log.info("No hay archivos DOCX para convertir en %s", docx_dir)
        return

    for docx_file in docx_files:
        pdf_temp = output_dir / (docx_file.stem + "_tmp.pdf")
        pdf_final = output_dir / (docx_file.stem + ".pdf")
        try:
            # Conversión (docx2pdf usa Word/COM en Windows; requiere Word instalado)
            convert(str(docx_file), str(pdf_temp))
            cc = cc_map.get(docx_file.name, "")
            if cc:
                # Cifrar
                writer = PdfWriter()
                reader = PdfReader(str(pdf_temp))
                for page in reader.pages:
                    writer.add_page(page)
                writer.encrypt(cc)
                with pdf_final.open("wb") as out_f:
                    writer.write(out_f)
                pdf_temp.unlink(missing_ok=True)
            else:
                # Renombrar si no se cifra
                pdf_temp.rename(pdf_final)
            log.info("PDF generado: %s%s", pdf_final.name, " (cifrado)" if cc else "")
        except Exception as e:  # noqa: BLE001
            log.error("Error convirtiendo %s: %s", docx_file.name, e)
            if pdf_temp.exists():
                pdf_temp.unlink(missing_ok=True)


__all__ = ["convert_and_encrypt"]