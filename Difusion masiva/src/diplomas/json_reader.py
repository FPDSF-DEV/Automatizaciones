from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Tuple
import json
import re
import unicodedata


EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")

# Campos sin los cuales un oficio no se puede generar ni enviar.
REQUIRED_FIELDS = ["gerente", "hospital", "email_hospital"]

# Todas las claves lógicas que el generador de oficios sabe interpretar
# (deben coincidir con las que usa build_placeholders en oficios_generator.py).
ALL_FIELDS = [
    "departamento",
    "municipio",
    "hospital",
    "gerente",
    "direccion",
    "telefono",
    "email_hospital",
    "alcalde",
    "email_alcaldia",
]

# Alias frecuentes para adivinar el mapeo cuando el JSON no usa nuestros nombres exactos.
FIELD_ALIASES: Dict[str, List[str]] = {
    "departamento": ["departamento", "depto", "department"],
    "municipio": ["municipio", "ciudad", "city", "town"],
    "hospital": ["hospital", "ese", "nombrehospital", "institucion", "entidad", "nombreese"],
    "gerente": ["gerente", "nombregerente", "manager", "director", "gerenteese"],
    "direccion": ["direccion", "address", "direccionhospital"],
    "telefono": ["telefono", "telefonos", "phone", "celular", "tel"],
    "email_hospital": ["emailhospital", "correohospital", "email", "correo", "correoelectronico", "mail"],
    "alcalde": ["alcalde", "mayor"],
    "email_alcaldia": ["emailalcaldia", "correoalcaldia"],
}


class JsonValidationError(Exception):
    pass


def _normalize_key(s: str) -> str:
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]", "", s.lower())


def guess_field_mapping(available_fields: List[str]) -> Dict[str, str]:
    """Adivina, por nombre, qué clave del JSON corresponde a cada campo lógico.

    Devuelve un dict {campo_logico: clave_json_detectada_o_""}. Pensado como
    punto de partida para que el usuario confirme/corrija en la UI, no como
    mapeo definitivo.
    """
    normalized = {_normalize_key(f): f for f in available_fields}
    mapping: Dict[str, str] = {}
    for logical, aliases in FIELD_ALIASES.items():
        found = ""
        for alias in aliases:
            if alias in normalized:
                found = normalized[alias]
                break
        mapping[logical] = found
    return mapping


class JsonReader:
    """Lee y sanea datos de gerentes/hospitales provistos en JSON por terceros.

    Acepta:
    - una lista de registros: [{...}, {...}]
    - un objeto con la lista bajo una clave común: {"data": [...]} / {"registros": [...]}
    - un objeto agrupado por departamento: {"Huila": [...], "Cesar": [...]}

    El resultado normalizado usa las mismas claves lógicas que el flujo Excel
    (departamento, municipio, hospital, gerente, direccion, telefono,
    email_hospital, ...) para poder alimentar `run_oficios_from_grouped_rows`
    sin cambios adicionales.
    """

    _LIST_KEYS = ("data", "registros", "records", "gerentes", "rows")

    def __init__(self, source: Path | str | bytes | list | dict):
        self._raw = self._load_raw(source)

    @staticmethod
    def _load_raw(source: Path | str | bytes | list | dict) -> Any:
        if isinstance(source, (list, dict)):
            return source
        if isinstance(source, Path):
            text = source.read_text(encoding="utf-8-sig")
        elif isinstance(source, bytes):
            text = source.decode("utf-8-sig")
        else:
            text = str(source)
        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            raise JsonValidationError(f"El archivo no es JSON válido: {e}") from e

    def _extract_records(self) -> List[Dict[str, Any]]:
        data = self._raw
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            for key in self._LIST_KEYS:
                if key in data and isinstance(data[key], list):
                    return data[key]
            if data and all(isinstance(v, list) for v in data.values()):
                flat: List[Dict[str, Any]] = []
                for dept, items in data.items():
                    for item in items:
                        if isinstance(item, dict):
                            item = {**item}
                            item.setdefault("departamento", dept)
                        flat.append(item)
                return flat
        raise JsonValidationError(
            "Estructura de JSON no reconocida: se esperaba una lista de registros, "
            "un objeto con una clave 'data'/'registros' con la lista, o un objeto "
            "agrupado por departamento (cada valor una lista de registros)."
        )

    def list_fields(self) -> List[str]:
        """Claves presentes en los registros (para armar el mapeo en la UI)."""
        fields: List[str] = []
        for r in self._extract_records()[:50]:
            if isinstance(r, dict):
                for k in r.keys():
                    if k not in fields:
                        fields.append(k)
        return fields

    def parse_and_validate(
        self,
        field_mapping: Dict[str, str] | None = None,
        group_by: str = "departamento",
    ) -> Tuple[Dict[str, List[Dict[str, str]]], List[Dict[str, str]], List[Dict[str, str]]]:
        """Normaliza y sanea los registros.

        Args:
            field_mapping: {campo_logico: clave_json}. Si se omite, se adivina
                con `guess_field_mapping` sobre las claves detectadas.
            group_by: campo lógico usado para agrupar (subcarpeta + CSV), igual
                que una hoja de departamento en el flujo Excel.

        Returns:
            (grouped_rows, rejected, warnings)
            - grouped_rows: {grupo: [fila_normalizada, ...]} lista para
              `run_oficios_from_grouped_rows`.
            - rejected: registros descartados, con motivo (faltan campos
              requeridos o email con formato inválido).
            - warnings: registros incluidos igualmente pero con alguna
              observación (por ahora, emails duplicados).
        """
        records = self._extract_records()
        mapping = field_mapping or guess_field_mapping(self.list_fields())

        grouped: Dict[str, List[Dict[str, str]]] = {}
        rejected: List[Dict[str, str]] = []
        warnings: List[Dict[str, str]] = []
        seen_emails: Dict[str, int] = {}

        for idx, raw in enumerate(records, start=1):
            if not isinstance(raw, dict):
                rejected.append({"idx": str(idx), "motivo": "el registro no es un objeto JSON"})
                continue

            row: Dict[str, str] = {}
            for logical_key in ALL_FIELDS:
                json_key = mapping.get(logical_key, "")
                val = raw.get(json_key) if json_key else None
                row[logical_key] = str(val).strip() if val not in (None, "") else ""

            missing = [f for f in REQUIRED_FIELDS if not row.get(f)]
            if missing:
                rejected.append({
                    "idx": str(idx),
                    "motivo": f"faltan campos requeridos: {', '.join(missing)}",
                    "gerente": row.get("gerente", ""),
                    "hospital": row.get("hospital", ""),
                })
                continue

            email = row["email_hospital"]
            if not EMAIL_RE.match(email):
                rejected.append({
                    "idx": str(idx),
                    "motivo": f"email con formato inválido: '{email}'",
                    "gerente": row.get("gerente", ""),
                    "hospital": row.get("hospital", ""),
                })
                continue

            email_key = email.lower()
            if email_key in seen_emails:
                warnings.append({
                    "idx": str(idx),
                    "motivo": f"email duplicado (ya visto en el registro #{seen_emails[email_key]}): '{email}'",
                    "gerente": row.get("gerente", ""),
                    "hospital": row.get("hospital", ""),
                })
            else:
                seen_emails[email_key] = idx

            group_key = row.get(group_by, "").strip() or "General"
            grouped.setdefault(group_key, []).append(row)

        return grouped, rejected, warnings


__all__ = ["JsonReader", "JsonValidationError", "guess_field_mapping", "ALL_FIELDS", "REQUIRED_FIELDS"]
