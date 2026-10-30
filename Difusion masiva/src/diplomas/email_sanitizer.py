from __future__ import annotations

from typing import Dict, List, Tuple
import re
import unicodedata


EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")

# Token con forma de email dentro de texto libre (para extraer varios de un mismo campo)
EMAIL_TOKEN_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")

# Algo que quiso ser un email pero no valida (ej. dominio truncado sin punto)
BROKEN_TOKEN_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+")


def _strip_accents(s: str) -> str:
    s = unicodedata.normalize("NFKD", s)
    return "".join(c for c in s if not unicodedata.combining(c))


def _pre_repair(raw: str) -> str:
    """Repara errores de digitación frecuentes ANTES de extraer los emails."""
    s = _strip_accents(raw)              # boyacá.gov.co -> boyaca.gov.co
    s = s.replace("mailto:", " ")
    s = re.sub(r"@\s+", "@", s)          # "gestion@ dominio.gov.co" -> "gestion@dominio.gov.co"
    s = re.sub(r",\s*\.", ".", s)        # "gov,.co" -> "gov.co"
    s = re.sub(r"\.{2,}", ".", s)        # ".." -> "."
    # TLDs truncados o con typo al final de un token
    s = re.sub(r"\.gov\.c(?=[\s,;/]|$)", ".gov.co", s)
    s = re.sub(r"\.con(?=[\s,;/]|$)", ".com", s)
    return s


def _clean_candidate(email: str) -> str:
    return email.strip().strip(".-_,;")


def sanitize_email_value(raw: str) -> Dict[str, object]:
    """Sanea un campo de email sucio, rescatando todo lo posible.

    Maneja los patrones reales del directorio REPS: varios correos en un campo
    (separados por '-', '/', ',', ';' o espacios), espacio después de la arroba,
    puntos finales, tildes en el dominio, '.gov.c'/'.con' truncados y dominios
    cortados a mitad de palabra (se reparan si otro correo del mismo campo
    revela el dominio completo).

    Returns:
        {"primary": str, "alternates": [str], "changed": bool, "recovered": bool}
        - primary: primer email válido rescatado ("" si irrecuperable)
        - alternates: demás emails válidos encontrados en el mismo campo
        - changed: True si primary difiere del valor original
        - recovered: True si el valor original NO validaba pero se rescató algo
    """
    original = (raw or "").strip()
    repaired = _pre_repair(original)
    # Solo se considera intacto si valida Y la pre-reparación no encontró nada
    # que corregir (así un typo estructuralmente válido como gmail.con sí se repara)
    if EMAIL_RE.match(original) and repaired.strip() == original:
        return {"primary": original, "alternates": [], "changed": False, "recovered": False, "was_valid": True}
    candidates: List[str] = []
    for token in EMAIL_TOKEN_RE.findall(repaired):
        c = _clean_candidate(token)
        if EMAIL_RE.match(c) and c.lower() not in {x.lower() for x in candidates}:
            candidates.append(c)

    # Intentar reparar tokens rotos (dominio truncado) usando dominios de
    # candidatos válidos del mismo campo como referencia
    if candidates:
        valid_domains = {c.split("@", 1)[1].lower() for c in candidates}
        matched_spans = {m.group(0) for m in EMAIL_TOKEN_RE.finditer(repaired)}
        for m in BROKEN_TOKEN_RE.finditer(repaired):
            token = m.group(0)
            if any(token in ok for ok in matched_spans):
                continue  # ya forma parte de un email válido
            local, _, dom = token.partition("@")
            dom = dom.lower().rstrip(".-")
            local = _clean_candidate(local)
            if not local or not dom:
                continue
            for full in valid_domains:
                if full.startswith(dom) and dom != full:
                    fixed = f"{local}@{full}"
                    if EMAIL_RE.match(fixed) and fixed.lower() not in {x.lower() for x in candidates}:
                        candidates.append(fixed)
                    break

    primary = candidates[0] if candidates else ""
    return {
        "primary": primary,
        "alternates": candidates[1:],
        "changed": primary != original,
        "recovered": bool(primary),
        "was_valid": False,
    }


def sanitize_table(
    rows: List[Dict[str, str]],
    email_column: str,
    alternates_column: str = "emails_alternos",
) -> Tuple[List[Dict[str, str]], List[Dict[str, str]]]:
    """Sanea la columna de email de una tabla completa, sin perder información.

    El email principal rescatado reemplaza al valor sucio; los demás correos del
    mismo campo se conservan en `alternates_column`. Los valores ya válidos no
    se tocan.

    Returns:
        (rows_saneadas, reporte) donde reporte lista solo las filas modificadas
        o irrecuperables: {fila, original, corregido, alternos, estado}
    """
    out_rows: List[Dict[str, str]] = []
    report: List[Dict[str, str]] = []
    for idx, row in enumerate(rows, start=1):
        original = (row.get(email_column) or "").strip()
        result = sanitize_email_value(original)
        new_row = dict(row)
        new_row[email_column] = result["primary"]
        new_row.setdefault(alternates_column, "")
        if result["alternates"]:
            new_row[alternates_column] = "; ".join(result["alternates"])
        out_rows.append(new_row)

        if not result["was_valid"]:
            if result["recovered"]:
                estado = "reparado"
            elif original:
                estado = "irrecuperable"
            else:
                estado = "vacío"
            report.append({
                "fila": str(idx),
                "original": original,
                "corregido": result["primary"],
                "alternos": "; ".join(result["alternates"]),
                "estado": estado,
            })
    return out_rows, report


__all__ = ["sanitize_email_value", "sanitize_table", "EMAIL_RE"]
