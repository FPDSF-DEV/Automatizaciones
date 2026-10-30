from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Tuple
import json

import pandas as pd


class DataLoadError(Exception):
    pass


def list_excel_sheets(path: Path) -> List[str]:
    try:
        return list(pd.ExcelFile(str(path)).sheet_names)
    except Exception as e:
        raise DataLoadError(f"No se pudo abrir el Excel: {e}") from e


def _df_to_records(df: pd.DataFrame) -> Tuple[List[Dict[str, str]], List[str]]:
    df = df.fillna("")
    columns = [str(c) for c in df.columns]
    records: List[Dict[str, str]] = []
    for _, row in df.iterrows():
        rec = {str(c): str(row[c]).strip() for c in df.columns}
        # Omitir filas completamente vacías
        if any(v for v in rec.values()):
            records.append(rec)
    return records, columns


def _read_text_best_effort(path: Path) -> str:
    raw = path.read_bytes()
    for enc in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    raise DataLoadError("No se pudo decodificar el archivo con las codificaciones habituales")


def _json_to_records(data) -> List[Dict[str, str]]:
    """Acepta lista de objetos, objeto con la lista bajo una clave común, u
    objeto agrupado (cada valor una lista); el nombre del grupo se anexa como campo '_grupo'."""
    if isinstance(data, list):
        items = data
    elif isinstance(data, dict):
        for key in ("data", "registros", "records", "rows", "items"):
            if isinstance(data.get(key), list):
                items = data[key]
                break
        else:
            if data and all(isinstance(v, list) for v in data.values()):
                items = []
                for group, group_items in data.items():
                    for item in group_items:
                        if isinstance(item, dict):
                            item = {**item}
                            item.setdefault("_grupo", str(group))
                        items.append(item)
            else:
                raise DataLoadError(
                    "Estructura JSON no reconocida: se esperaba una lista de objetos, "
                    "un objeto con la lista bajo 'data'/'registros', o un objeto agrupado."
                )
    else:
        raise DataLoadError("El JSON debe ser una lista u objeto en su nivel superior")

    records: List[Dict[str, str]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        rec = {str(k): ("" if v is None else str(v).strip()) for k, v in item.items()}
        if any(rec.values()):
            records.append(rec)
    return records


def load_records(path: Path, sheet_name: str | None = None) -> Tuple[List[Dict[str, str]], List[str]]:
    """Carga registros desde Excel, CSV o JSON conservando los nombres de columna originales.

    Devuelve (registros, columnas). Todos los valores son str ya limpiados.
    Es la entrada única del flujo genérico: no impone ninguna estructura.
    """
    suffix = path.suffix.lower()
    if suffix in (".xlsx", ".xls", ".xlsm"):
        try:
            df = pd.read_excel(str(path), sheet_name=sheet_name or 0, dtype=str)
        except Exception as e:
            raise DataLoadError(f"No se pudo leer el Excel: {e}") from e
        return _df_to_records(df)
    if suffix == ".csv":
        text = _read_text_best_effort(path)
        import io as _io
        try:
            df = pd.read_csv(_io.StringIO(text), dtype=str, sep=None, engine="python")
        except Exception as e:
            raise DataLoadError(f"No se pudo leer el CSV: {e}") from e
        return _df_to_records(df)
    if suffix == ".json":
        text = _read_text_best_effort(path)
        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            raise DataLoadError(f"JSON inválido: {e}") from e
        records = _json_to_records(data)
        columns: List[str] = []
        for rec in records:
            for k in rec.keys():
                if k not in columns:
                    columns.append(k)
        # Homogeneizar: todas las filas con todas las columnas
        for rec in records:
            for k in columns:
                rec.setdefault(k, "")
        return records, columns
    raise DataLoadError(f"Formato no soportado: {suffix} (usa .xlsx, .csv o .json)")


__all__ = ["load_records", "list_excel_sheets", "DataLoadError"]
