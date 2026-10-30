from __future__ import annotations

from pathlib import Path
from typing import Dict, List
import logging
import csv
import re

from .excel_reader import ExcelReader
from .template_processor import TemplateProcessor
from .utils.logging import setup_logging
from .utils.naming import slugify, ensure_unique_slug
from docx.opc.constants import RELATIONSHIP_TYPE
from docx.oxml.shared import OxmlElement, qn


PLACEHOLDERS_OFICIOS = [
    "{{DEPARTAMENTO}}",
    "{{MUNICIPIO}}",
    "{{HOSPITAL}}",
    "{{GERENTE}}",
    "{{ALCALDE}}",
    "{{EMAIL}}",           # compatibilidad: se asigna al email destinatario elegido
    "{{EMAIL_HOSPITAL}}",
    "{{EMAIL_ALCALDIA}}",
    "{{DIRECCION}}",
    "{{TELEFONO}}",
    "{{LUGAR_LINEA}}",
]

PLACEHOLDERS_ALCALDE = [
    "{{ALCALDE}}",
    "{{EMAIL_ALCALDIA}}",
    "{{DEPARTAMENTO}}",
    "{{MUNICIPIO}}",
    "{{LUGAR_LINEA}}",
    # Opcionales, por si se necesitan
    "{{DIRECCION}}",
    "{{TELEFONO}}",
]

PLACEHOLDERS_GERENTE = [
    "{{GERENTE}}",
    "{{EMAIL_HOSPITAL}}",
    "{{HOSPITAL}}",
    "{{DEPARTAMENTO}}",
    "{{MUNICIPIO}}",
    "{{LUGAR_LINEA}}",
    # Opcionales
    "{{DIRECCION}}",
    "{{TELEFONO}}",
]


def build_placeholders(row: Dict[str, str], recipient_email_key: str) -> Dict[str, str]:
    # Normaliza composiciones
    dep = row.get("departamento", "")
    mun = row.get("municipio", "")
    lugar_linea = f"{dep}, {mun}.".strip().strip(',')
    email_dest = row.get(recipient_email_key, "")
    ph: Dict[str, str] = {
        "{{DEPARTAMENTO}}": dep,
        "{{MUNICIPIO}}": mun,
    "{{HOSPITAL}}": row.get("hospital", "") or "",
    "{{GERENTE}}": row.get("gerente", "") or row.get("gerente_hospital", "") or "",
    "{{ALCALDE}}": row.get("alcalde", "") or "",
        "{{EMAIL}}": email_dest,  # compatibilidad
        "{{EMAIL_HOSPITAL}}": row.get("email_hospital", ""),
        "{{EMAIL_ALCALDIA}}": row.get("email_alcaldia", ""),
    "{{DIRECCION}}": row.get("direccion", "") or "",
    "{{TELEFONO}}": row.get("telefono", "") or "",
        "{{LUGAR_LINEA}}": lugar_linea,
    }
    # Filtra placeholders vacíos para no forzar en plantillas que no los usen
    return {k: (v or "") for k, v in ph.items()}


def run_oficios_generation(
    template: Path,
    excel: Path,
    sheet_name: str,
    outdir: Path,
    start_row: int = 1,
    limit: int = 0,
    verbose: int = 0,
    column_mapping: Dict[str, str] | None = None,
    base_name: str | None = None,
    recipient_email_key: str = "email",
    recipient_preference: str = "auto",  # auto | alcaldia | hospital
    contacts_csv_basename: str | None = None,
    contacts_csv_path: Path | None = None,
    flow_label: str | None = None,  # "alcaldia" | "hospital" | None
    append_copy_footer: bool = False,
    copy_footer_template: str | None = None,
    override_gerente_header_with_alcalde: bool = False,
) -> None:
    setup_logging(verbose)
    log = logging.getLogger("diplomas")
    outdir.mkdir(parents=True, exist_ok=True)

    reader = ExcelReader(excel)
    if column_mapping:
        rows = reader.load_oficios_rows_by_mapping(sheet_name, column_mapping, start_row=start_row, limit=limit)
    else:
        rows = reader.load_oficios_rows(sheet_name, start_row=start_row, limit=limit)
    if not rows:
        log.warning("No hay filas en la hoja '%s'", sheet_name)
        return

    ok = 0
    fail = 0
    TITLE = base_name or "OFICIO"
    # Acumulador de correos para CSV (deduplicado por email normalizado)
    correos: Dict[str, Dict[str, str | int]] = {}
    total_con_email = 0
    invalid_rows: List[Dict[str, str | int]] = []
    EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
    for idx, row in enumerate(rows, start=1):
        try:
            # Resolver email destinatario según preferencia
            chosen_key = recipient_email_key
            if recipient_preference in ("alcaldia", "hospital"):
                chosen_key = "email_alcaldia" if recipient_preference == "alcaldia" else "email_hospital"
            elif recipient_preference == "auto":
                # Priorizar alcaldía si existe, si no hospital, y si no, 'email' genérico
                if (row.get("email_alcaldia") or "").strip():
                    chosen_key = "email_alcaldia"
                elif (row.get("email_hospital") or "").strip():
                    chosen_key = "email_hospital"
                else:
                    chosen_key = recipient_email_key

            placeholders = build_placeholders(row, chosen_key)
            # Excepción: usar cabeceras de Alcaldía en documento de Gerente (ajuste nombre/email cabecera)
            if override_gerente_header_with_alcalde:
                if row.get("alcalde"):
                    placeholders["{{GERENTE}}"] = row.get("alcalde", "")
                if row.get("email_alcaldia"):
                    placeholders["{{EMAIL_HOSPITAL}}"] = row.get("email_alcaldia", "")

            proc = TemplateProcessor(template, placeholders)
            doc = proc.render()
            # Convertir el email en hipervínculo (mailto:)
            _hyperlink_email_in_doc(doc, row.get(chosen_key, ""))

            # Añadir línea de copia si aplica (opcional; no se usa en este caso excepcional)
            if append_copy_footer:
                try:
                    texto = copy_footer_template or "Copia: Entidad ({MUNICIPIO})"
                    mun = placeholders.get("{{MUNICIPIO}}", "")
                    dep = placeholders.get("{{DEPARTAMENTO}}", "")
                    texto = texto.replace("{MUNICIPIO}", mun or "").replace("{DEPARTAMENTO}", dep or "")
                    doc.add_paragraph("")
                    p = doc.add_paragraph(texto)
                    if p.runs:
                        p.runs[0].italic = True
                except Exception:
                    pass

            # Nombre fijo solicitado por el usuario (mantenemos índice para no sobrescribir)
            filename = f"{idx:03d}-{TITLE}.docx"
            doc.save(outdir / filename)
            ok += 1

            # Recolección de correos
            raw_email = (row.get(chosen_key) or "").strip()
            if raw_email:
                total_con_email += 1
                if not EMAIL_RE.match(raw_email):
                    invalid_rows.append({
                        "idx": idx,
                        "email": raw_email,
                        "gerente": row.get("gerente", "") or row.get("gerente_hospital", ""),
                        "alcalde": row.get("alcalde", ""),
                        "hospital": row.get("hospital", ""),
                        "departamento": row.get("departamento", ""),
                        "municipio": row.get("municipio", ""),
                        "direccion": row.get("direccion", ""),
                        "telefono": row.get("telefono", ""),
                        "filename": filename,
                        "motivo": "formato invalido",
                    })
                    # No agregar al CSV principal de válidos
                    continue
                key = raw_email.lower()
                if key not in correos:
                    correos[key] = {
                        "email": raw_email,
                        "email_hospital": row.get("email_hospital", ""),
                        "email_alcaldia": row.get("email_alcaldia", ""),
                        "gerente": row.get("gerente", "") or row.get("gerente_hospital", ""),
                        "alcalde": row.get("alcalde", ""),
                        "hospital": row.get("hospital", ""),
                        "departamento": row.get("departamento", ""),
                        "municipio": row.get("municipio", ""),
                        "direccion": row.get("direccion", ""),
                        "telefono": row.get("telefono", ""),
                        "ocurrencias": 1,
                        "idx_primero": idx,
                        "filename_primero": filename,
                        "has_alcaldia": "1" if chosen_key == "email_alcaldia" else "0",
                        "has_hospital": "1" if chosen_key == "email_hospital" else "0",
                    }
                else:
                    # Solo incrementa ocurrencias, conserva primeros metadatos
                    correos[key]["ocurrencias"] = int(correos[key]["ocurrencias"]) + 1
                    # Actualizar flags de flujo
                    if chosen_key == "email_alcaldia":
                        correos[key]["has_alcaldia"] = "1"
                    elif chosen_key == "email_hospital":
                        correos[key]["has_hospital"] = "1"
        except Exception as e:  # noqa: BLE001
            log.error("Error fila %d: %s", idx, e)
            fail += 1
    # Escribir/merge CSV de correos deduplicados (válidos)
    try:
        # Definir ruta de CSV: si se pasó absoluta, usarla; si no, usar basename en outdir
        csv_path = contacts_csv_path or (outdir / (contacts_csv_basename or "correos.csv"))
        # Leer existente (si hay) para merge
        existing: Dict[str, Dict[str, str]] = {}
        if csv_path.exists():
            try:
                with csv_path.open("r", encoding="utf-8-sig") as ef:
                    reader = csv.DictReader(ef)
                    for row in reader:
                        email_key = (row.get("email") or "").lower()
                        if not email_key:
                            continue
                        existing[email_key] = dict(row)
            except Exception:
                existing = {}

        # Consolidar: agregar/actualizar registros
        for key_email in correos:
            current = existing.get(key_email, {})
            new = correos[key_email]
            # merge con preferencia por nuevos campos no vacíos
            for field in [
                "email",
                "email_hospital",
                "email_alcaldia",
                "gerente",
                "alcalde",
                "hospital",
                "departamento",
                "municipio",
                "direccion",
                "telefono",
                "idx_primero",
                "filename_primero",
            ]:
                val = str(new.get(field, ""))
                if val:
                    current[field] = val
            # incrementar ocurrencias
            ocurr_prev = int(current.get("ocurrencias", 0) or 0)
            current["ocurrencias"] = str(ocurr_prev + int(new.get("ocurrencias", 0) or 0) or 1)
            # filename específico por flujo
            label = (flow_label or "").strip().lower()
            if label in ("alcaldia", "hospital"):
                fieldname = f"filename_primero_{label}"
                if new.get("filename_primero"):
                    current[fieldname] = str(new.get("filename_primero"))
            # flags de flujo
            if new.get("has_alcaldia") == "1":
                current["has_alcaldia"] = "1"
            if new.get("has_hospital") == "1":
                current["has_hospital"] = "1"
            existing[key_email] = current

        # Escribir CSV final con columnas extendidas
        headers = [
            "email",
            "email_hospital",
            "email_alcaldia",
            "gerente",
            "alcalde",
            "hospital",
            "departamento",
            "municipio",
            "direccion",
            "telefono",
            "ocurrencias",
            "idx_primero",
            "filename_primero",
            "filename_primero_alcaldia",
            "filename_primero_hospital",
            "has_alcaldia",
            "has_hospital",
        ]
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
            for key in sorted(existing.keys()):
                row_out = {h: existing[key].get(h, "") for h in headers}
                writer.writerow(row_out)
        # Escribir CSV de correos inválidos (si hay)
        invalid_csv_path = None
        if invalid_rows:
            invalid_csv_path = outdir / "correos_invalidos.csv"
            invalid_headers = [
                "idx",
                "email",
                "gerente",
                "alcalde",
                "hospital",
                "departamento",
                "municipio",
                "direccion",
                "telefono",
                "filename",
                "motivo",
            ]
            with invalid_csv_path.open("w", encoding="utf-8-sig", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=invalid_headers)
                writer.writeheader()
                for item in invalid_rows:
                    writer.writerow({h: item.get(h, "") for h in invalid_headers})

        log.info(
            "Oficios OK: %d | Fallidos: %d | Correos válidos únicos: %d | Filas con email: %d | Correos inválidos: %d. CSV válidos: %s | CSV inválidos: %s",
            ok,
            fail,
            len(correos),
            total_con_email,
            len(invalid_rows),
            csv_path,
            invalid_csv_path if invalid_rows else "N/A",
        )
    except Exception as e:  # noqa: BLE001
        log.error("No se pudo escribir el CSV de correos: %s", e)
        log.info("Oficios OK: %d | Fallidos: %d", ok, fail)


__all__ = [
    "run_oficios_generation",
    "run_oficios_multi_sheet_generation",
    "run_oficios_from_grouped_rows",
    "PLACEHOLDERS_OFICIOS",
    "PLACEHOLDERS_ALCALDE",
    "PLACEHOLDERS_GERENTE",
    "COLUMN_MAPPING_GERENTE_DEFAULT",
]

# Mapeo de columnas por defecto para el directorio de hospitales (estructura estándar)
COLUMN_MAPPING_GERENTE_DEFAULT = {
    "departamento": "Departamento",
    "municipio": "Municipio",
    "hospital": "Hospital",
    "gerente": "Gerente",
    "direccion": "Dirección",
    "telefono": "Teléfono(s)/Fax",
    "email_hospital": "Correo Electrónico",
}


def run_oficios_multi_sheet_generation(
    template: Path,
    excel: Path,
    selected_sheets: List[str],
    outdir: Path,
    start_row: int = 1,
    limit_per_sheet: int = 0,
    verbose: int = 0,
    column_mapping: Dict[str, str] | None = None,
    base_name: str | None = None,
    recipient_email_key: str = "email_hospital",
    flow_label: str = "hospital",
) -> Dict[str, Dict[str, int]]:
    """Genera oficios desde múltiples hojas del Excel (una por departamento).

    Args:
        template: Ruta a la plantilla Word
        excel: Ruta al Excel con múltiples hojas
        selected_sheets: Lista de hojas (departamentos) a procesar
        outdir: Carpeta base de salida
        start_row: Fila inicial de datos
        limit_per_sheet: Límite de filas por hoja
        verbose: Nivel de logging
        column_mapping: Mapeo de columnas (usa COLUMN_MAPPING_GERENTE_DEFAULT si no se especifica)
        base_name: Nombre base para los archivos
        recipient_email_key: Campo de email a usar
        flow_label: Etiqueta del flujo (hospital/alcaldia)

    Returns:
        Dict con estadísticas por departamento: {sheet_name: {"ok": n, "fail": n, "emails": n}}
    """
    # Usar mapeo por defecto si no se especifica
    mapping = column_mapping or COLUMN_MAPPING_GERENTE_DEFAULT

    reader = ExcelReader(excel)

    # Cargar datos de todas las hojas seleccionadas
    all_data = reader.load_all_sheets_by_mapping(
        mapping,
        selected_sheets=selected_sheets,
        start_row=start_row,
        limit_per_sheet=limit_per_sheet,
    )

    return run_oficios_from_grouped_rows(
        template,
        all_data,
        outdir,
        verbose=verbose,
        base_name=base_name,
        recipient_email_key=recipient_email_key,
        flow_label=flow_label,
    )


def run_oficios_from_grouped_rows(
    template: Path,
    all_data: Dict[str, List[Dict[str, str]]],
    outdir: Path,
    verbose: int = 0,
    base_name: str | None = None,
    recipient_email_key: str = "email_hospital",
    flow_label: str = "hospital",
) -> Dict[str, Dict[str, int]]:
    """Genera oficios a partir de filas ya cargadas y agrupadas (por departamento u otro criterio).

    Es la lógica compartida entre el flujo Excel (multi-hoja) y cualquier otra fuente
    de datos ya normalizada a la misma estructura de filas (por ejemplo, JSON vía
    `JsonReader`). Cada grupo produce su propia subcarpeta y CSV de trazabilidad,
    igual que una hoja de departamento en el flujo Excel.

    Args:
        template: Ruta a la plantilla Word
        all_data: Dict {grupo: [fila_normalizada, ...]} (fila con claves lógicas:
            departamento, municipio, hospital, gerente, direccion, telefono,
            email_hospital, etc.)
        outdir: Carpeta base de salida
        verbose: Nivel de logging
        base_name: Nombre base para los archivos
        recipient_email_key: Campo de email a usar
        flow_label: Etiqueta del flujo (hospital/alcaldia)

    Returns:
        Dict con estadísticas por grupo: {grupo: {"ok": n, "fail": n, "emails": n}}
    """
    setup_logging(verbose)
    log = logging.getLogger("diplomas")
    outdir.mkdir(parents=True, exist_ok=True)

    stats: Dict[str, Dict[str, int]] = {}
    global_idx = 0

    for sheet_name, rows in all_data.items():
        if not rows:
            stats[sheet_name] = {"ok": 0, "fail": 0, "emails": 0}
            continue
        
        # Crear subdirectorio por departamento
        dept_outdir = outdir / slugify(sheet_name)
        dept_outdir.mkdir(parents=True, exist_ok=True)
        
        ok = 0
        fail = 0
        emails_found = 0
        
        TITLE = base_name or "OFICIO"
        
        # Guardar el índice global inicial para este departamento (para el CSV)
        dept_start_idx = global_idx
        
        for idx, row in enumerate(rows, start=1):
            global_idx += 1
            try:
                placeholders = build_placeholders(row, recipient_email_key)
                proc = TemplateProcessor(template, placeholders)
                doc = proc.render()
                
                # Convertir email a hipervínculo
                email_val = row.get(recipient_email_key, "")
                if email_val:
                    _hyperlink_email_in_doc(doc, email_val)
                    emails_found += 1
                
                # Nombre de archivo incluye departamento para trazabilidad
                filename = f"{global_idx:04d}-{TITLE}-{slugify(sheet_name)}.docx"
                doc.save(dept_outdir / filename)
                ok += 1
                
            except Exception as e:
                log.error("Error en hoja %s, fila %d: %s", sheet_name, idx, e)
                fail += 1
        
        # Generar CSV de correos por departamento (pasamos el índice inicial para coincidir con archivos)
        _write_department_csv(dept_outdir, rows, recipient_email_key, sheet_name, base_name or "OFICIO", dept_start_idx)
        
        stats[sheet_name] = {"ok": ok, "fail": fail, "emails": emails_found}
        log.info("Hoja %s: OK=%d, Fail=%d, Emails=%d", sheet_name, ok, fail, emails_found)
    
    # Generar CSV consolidado (pasamos el base_name para generar filenames correctos)
    _write_consolidated_csv(outdir, all_data, recipient_email_key, flow_label, base_name or "OFICIO")
    
    return stats


def _write_department_csv(
    outdir: Path,
    rows: List[Dict[str, str]],
    email_key: str,
    sheet_name: str,
    base_name: str,
    start_idx: int = 0,
) -> None:
    """Escribe un CSV de correos para un departamento específico."""
    csv_path = outdir / "correos.csv"
    headers = [
        "email",
        "gerente",
        "hospital",
        "departamento",
        "municipio",
        "direccion",
        "telefono",
        "filename",
    ]
    
    EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
    
    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        
        for idx, row in enumerate(rows, start=1):
            email = row.get(email_key, "").strip()
            if not email or not EMAIL_RE.match(email):
                continue
            
            # Usar índice global (start_idx + idx) para coincidir con los archivos generados
            global_idx = start_idx + idx
            filename = f"{global_idx:04d}-{base_name}-{slugify(sheet_name)}.docx"
            
            writer.writerow({
                "email": email,
                "gerente": row.get("gerente", ""),
                "hospital": row.get("hospital", ""),
                "departamento": row.get("departamento", "") or sheet_name,
                "municipio": row.get("municipio", ""),
                "direccion": row.get("direccion", ""),
                "telefono": row.get("telefono", ""),
                "filename": filename,
            })


def _write_consolidated_csv(
    outdir: Path,
    all_data: Dict[str, List[Dict[str, str]]],
    email_key: str,
    flow_label: str,
    base_name: str = "OFICIO",
) -> None:
    """Escribe un CSV consolidado con todos los departamentos."""
    csv_path = outdir / "correos_consolidado.csv"
    headers = [
        "email",
        "gerente",
        "hospital",
        "departamento",
        "municipio",
        "direccion",
        "telefono",
        "sheet_name",
        "sheet_name_slug",
        "filename",
        "flow",
    ]
    
    EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
    
    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        
        global_idx = 0
        for sheet_name, rows in all_data.items():
            sheet_slug = slugify(sheet_name)
            for idx, row in enumerate(rows, start=1):
                global_idx += 1
                email = row.get(email_key, "").strip()
                if not email or not EMAIL_RE.match(email):
                    continue
                
                # Generar el filename que corresponde a este registro
                filename = f"{global_idx:04d}-{base_name}-{sheet_slug}.docx"
                
                writer.writerow({
                    "email": email,
                    "gerente": row.get("gerente", ""),
                    "hospital": row.get("hospital", ""),
                    "departamento": row.get("departamento", "") or sheet_name,
                    "municipio": row.get("municipio", ""),
                    "direccion": row.get("direccion", ""),
                    "telefono": row.get("telefono", ""),
                    "sheet_name": sheet_name,
                    "sheet_name_slug": sheet_slug,
                    "filename": filename,
                    "flow": flow_label,
                })


def _add_hyperlink(paragraph, url: str, text: str) -> None:
    """Inserta un hipervínculo en el párrafo (estilo estándar 'Hyperlink')."""
    # Crear la relación
    part = paragraph.part
    r_id = part.relate_to(url, RELATIONSHIP_TYPE.HYPERLINK, is_external=True)

    # <w:hyperlink r:id="..."><w:r><w:rPr><w:rStyle w:val="Hyperlink"/></w:rPr><w:t>text</w:t></w:r></w:hyperlink>
    hyperlink = OxmlElement("w:hyperlink")
    hyperlink.set(qn("r:id"), r_id)

    new_run = OxmlElement("w:r")
    r_pr = OxmlElement("w:rPr")
    # Estilo 'Hyperlink' + forzar color azul y subrayado para apariencia clásica
    r_style = OxmlElement("w:rStyle"); r_style.set(qn("w:val"), "Hyperlink")
    r_color = OxmlElement("w:color"); r_color.set(qn("w:val"), "0000FF")
    r_u = OxmlElement("w:u"); r_u.set(qn("w:val"), "single")
    r_pr.append(r_style)
    r_pr.append(r_color)
    r_pr.append(r_u)
    new_run.append(r_pr)

    w_t = OxmlElement("w:t")
    w_t.text = text
    new_run.append(w_t)
    hyperlink.append(new_run)

    paragraph._p.append(hyperlink)


def _hyperlink_email_in_doc(doc, email: str) -> None:
    if not email:
        return

    def process_paragraph(paragraph) -> bool:
        full = paragraph.text or ""
        idx = full.find(email)
        if idx == -1:
            return False
        # Borrar runs actuales
        for run in list(paragraph.runs):
            paragraph._p.remove(run._element)
        pre = full[:idx]
        post = full[idx + len(email) :]
        if pre:
            paragraph.add_run(pre)
        _add_hyperlink(paragraph, f"mailto:{email}", email)
        if post:
            paragraph.add_run(post)
        return True

    # Parrafos fuera de tablas
    for p in doc.paragraphs:
        if process_paragraph(p):
            return
    # Parrafos dentro de tablas
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for p in cell.paragraphs:
                    if process_paragraph(p):
                        return