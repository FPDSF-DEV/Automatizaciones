from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import List, Dict
from datetime import date, datetime

from .config import Settings
import csv
from .excel_reader import ExcelReader
from .template_processor import TemplateProcessor
from .utils.logging import setup_logging
from .utils.naming import slugify, ensure_unique_slug


def _build_placeholders(row: Dict[str, str], settings: Settings) -> Dict[str, str]:
    today = date.today()
    meses = [
        "enero", "febrero", "marzo", "abril", "mayo", "junio",
        "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"
    ]
    mes_nombre = meses[today.month - 1].capitalize()
    # Rango de fechas
    rango = ""
    if settings.start_date:
        try:
            d_ini = datetime.strptime(settings.start_date, "%Y-%m-%d").date()
            mes_ini = meses[d_ini.month - 1]
            rango = f"del {d_ini.day} de {mes_ini} al {today.day} de {mes_nombre} de {today.year}"
        except Exception:  # noqa: BLE001
            rango = f"hasta el {today.day} de {mes_nombre} de {today.year}"
    else:
        rango = f"al {today.day} de {mes_nombre} de {today.year}"

    placeholders = {
        "{{NOMBRE}}": row["nombre"],
        "{{CC}}": row.get("cc", ""),
        "{{INTENSIDAD}}": str(settings.intensity_hours),
        "{{LUGAR}}": settings.location,
        "{{FECHA_RANGO}}": rango,
        "{{FECHA_HOY_LARGO}}": f"{mes_nombre} {today.day} de {today.year}",
    }
    return placeholders


def _render_one(idx: int, row: Dict[str, str], settings: Settings, slug_registry: set[str]) -> tuple[str, bool, str | None, str, str]:
    try:
        name = row["nombre"]
        slug = slugify(name, preserve_accents=settings.preserve_accents)
        slug = ensure_unique_slug(slug, slug_registry)
        placeholders = _build_placeholders(row, settings)
        processor = TemplateProcessor(settings.template, placeholders)
        doc = processor.render()
        if settings.fail_on_missing_placeholder:
            missing = set(placeholders.keys()) - processor.found_placeholders
            if missing:
                raise ValueError(f"Placeholders no encontrados en la plantilla: {', '.join(sorted(missing))}")
        filename = settings.filename_pattern.format(index=idx, slug=slug, original=name)
        output_path = settings.outdir / filename
        if not settings.dry_run:
            doc.save(output_path)
        return (name, True, None, slug, row.get("cc", ""))
    except Exception as e:  # noqa: BLE001
        return (row.get("nombre", "?"), False, str(e), "", row.get("cc", ""))


def run_generation(settings: Settings) -> None:
    setup_logging(settings.verbose)
    log = logging.getLogger("diplomas")
    settings.outdir.mkdir(parents=True, exist_ok=True)

    reader = ExcelReader(settings.excel)
    rows = reader.load_rows(
        name_col=settings.name_col or settings.column,
        id_col=settings.id_col,
        start_row=settings.start_row,
        limit=settings.limit,
        dedupe=settings.dedupe,
        first_name_col=settings.first_name_col,
        last_name_col=settings.last_name_col,
        email_col=settings.email_col,
    )
    if not rows:
        log.error("No se encontraron filas válidas en el Excel")
        return

    log.info("Total filas: %d", len(rows))
    slug_registry: set[str] = set()
    results: List[tuple[str, bool, str | None, str, str]] = []

    if settings.concurrency == 1:
        for idx, row in enumerate(rows, start=1):
            results.append(_render_one(idx, row, settings, slug_registry))
    else:
        with ThreadPoolExecutor(max_workers=settings.concurrency) as pool:
            futures = {
                pool.submit(_render_one, idx, row, settings, slug_registry): row
                for idx, row in enumerate(rows, start=1)
            }
            for fut in as_completed(futures):
                results.append(fut.result())

    ok = sum(1 for _, success, *_rest in results if success)
    fail = len(results) - ok
    for name, success, error, _, _ in results:
        if not success:
            log.error("Fallo '%s': %s", name, error)
    log.info("Generados OK: %d | Fallidos: %d", ok, fail)

    # Crear manifest para siguiente paso (PDF/cifrado)
    manifest_path = settings.outdir / "manifest.csv"
    try:
        with manifest_path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(["index", "filename", "nombre", "cc", "email"])
            # Escribimos solo los exitosos en el orden de generación usando la fila original
            idx_counter = 1
            for (row, result) in zip(rows, results, strict=False):
                name, success, error, slug, cc = result
                if not success:
                    continue
                filename = settings.filename_pattern.format(index=idx_counter, slug=slug, original=name)
                writer.writerow([idx_counter, filename, name, cc, row.get("email", "")])
                idx_counter += 1
        log.info("Manifest generado: %s", manifest_path)
    except Exception as e:  # noqa: BLE001
        log.warning("No se pudo crear manifest.csv: %s", e)


__all__ = ["run_generation"]
