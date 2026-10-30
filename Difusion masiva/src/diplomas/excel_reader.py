from __future__ import annotations

from pathlib import Path
from typing import Iterable, List, Dict, Tuple

import pandas as pd


class ExcelReader:
    def __init__(self, path: Path):
        self.path = path

    def load_rows(
        self,
        name_col: str | None = None,
        id_col: str | None = None,
        start_row: int = 1,
        limit: int = 0,
        dedupe: bool = True,
        first_name_col: str | None = None,
        last_name_col: str | None = None,
        email_col: str | None = None,
    ) -> List[Dict[str, str]]:
        df = pd.read_excel(self.path, dtype=str)
        if df.empty:
            return []

        # Determinar estrategia de nombre
        combined_mode = first_name_col and last_name_col
        if combined_mode:
            for col in (first_name_col, last_name_col):
                if col not in df.columns:
                    raise ValueError(f"Columna '{col}' no existe en el Excel")
        else:
            if name_col is None:
                name_col = df.columns[0]
            if name_col not in df.columns:
                raise ValueError(f"Columna de nombre '{name_col}' no existe en el Excel")

        if id_col and id_col not in df.columns:
            raise ValueError(f"Columna de CC '{id_col}' no existe en el Excel")
        if email_col and email_col not in df.columns:
            raise ValueError(f"Columna de email '{email_col}' no existe en el Excel")

        sub = df.iloc[start_row - 1 :]
        if limit > 0:
            sub = sub.head(limit)

        rows: List[Dict[str, str]] = []
        seen = set()
        for _, r in sub.iterrows():
            if combined_mode:
                raw_first = r.get(first_name_col)
                raw_last = r.get(last_name_col)
                if not isinstance(raw_first, str) or not raw_first.strip():
                    continue
                name_parts = []
                if isinstance(raw_first, str):
                    name_parts.append(self._clean_name(raw_first))
                if isinstance(raw_last, str) and raw_last.strip():
                    name_parts.append(self._clean_name(raw_last))
                full_name_raw = " ".join(name_parts)
            else:
                raw_name = r.get(name_col)
                if not isinstance(raw_name, str) or not raw_name.strip():
                    continue
                full_name_raw = self._clean_name(raw_name)

            name = self._title_case(full_name_raw)
            cc_val = r.get(id_col) if id_col else None
            if isinstance(cc_val, str):
                cc_val = self._clean_name(cc_val)
            key = name if dedupe else f"{name}|{cc_val or ''}"
            if dedupe and key in seen:
                continue
            seen.add(key)
            email_val = r.get(email_col) if email_col else None
            if isinstance(email_val, str):
                email_val = email_val.strip()
            rows.append({"nombre": name, "cc": cc_val or "", "email": email_val or ""})
        return rows

    def load_oficios_rows(
        self,
        sheet_name: str,
        start_row: int = 1,
        limit: int = 0,
    ) -> List[Dict[str, str]]:
        """Carga filas para cartas/oficios con estructura fija A-G.

        Columnas requeridas (texto exacto):
        - Departamento
        - Municipio
        - Hospital
        - Gerente
        - Dirección
        - Teléfono(s)/Fax
        - Correo Electrónico
        """
        required = [
            "Departamento",
            "Municipio",
            "Hospital",
            "Gerente",
            "Dirección",
            "Teléfono(s)/Fax",
            "Correo Electrónico",
        ]
        df = pd.read_excel(self.path, sheet_name=sheet_name, dtype=str)
        if df.empty:
            return []
        missing = [c for c in required if c not in df.columns]
        if missing:
            raise ValueError(f"Faltan columnas en la hoja '{sheet_name}': {', '.join(missing)}")

        sub = df.iloc[start_row - 1 :]
        if limit > 0:
            sub = sub.head(limit)

        rows: List[Dict[str, str]] = []
        for _, r in sub.iterrows():
            def g(col: str) -> str:
                v = r.get(col)
                return (str(v).strip() if isinstance(v, str) else "")

            rows.append(
                {
                    "departamento": g("Departamento"),
                    "municipio": g("Municipio"),
                    "hospital": g("Hospital"),
                    "gerente": g("Gerente"),
                    "direccion": g("Dirección"),
                    "telefono": g("Teléfono(s)/Fax"),
                    "email": g("Correo Electrónico"),
                }
            )
        return rows

    def load_oficios_rows_by_mapping(
        self,
        sheet_name: str,
        column_mapping: Dict[str, str],
        start_row: int = 1,
        limit: int = 0,
    ) -> List[Dict[str, str]]:
        """Carga filas para cartas/oficios usando un mapeo dinámico de columnas.

        column_mapping: dict con claves lógicas (ej.: "departamento", "municipio", "hospital",
        "gerente", "alcalde", "email_hospital", "email_alcaldia", "direccion", "telefono", ...)
        y valores = nombre exacto de la columna en el Excel.
        """
        if not column_mapping:
            # Si no se especifica mapeo, retorna vacío (caller puede decidir lanzar fallback)
            return []

        df = pd.read_excel(self.path, sheet_name=sheet_name, dtype=str)
        if df.empty:
            return []

        # Validar columnas declaradas existen en el Excel (ignorar opcionales no presentes)
        missing_cols = [col for col in column_mapping.values() if col and col not in df.columns]
        # No fallamos, solo avisar en logs si fuera necesario (silencioso para UI)

        sub = df.iloc[start_row - 1 :]
        if limit > 0:
            sub = sub.head(limit)

        rows: List[Dict[str, str]] = []
        keys = list(column_mapping.keys())
        for _, r in sub.iterrows():
            out: Dict[str, str] = {}
            for k in keys:
                col = column_mapping.get(k, "")
                v = r.get(col) if col in df.columns else None
                out[k] = (str(v).strip() if isinstance(v, str) else "")
            rows.append(out)
        return rows

    # Retrocompatibilidad
    def load_names(
        self,
        column: str | None = None,
        start_row: int = 1,
        limit: int = 0,
        dedupe: bool = True,
    ) -> List[str]:
        return [r["nombre"] for r in self.load_rows(name_col=column, start_row=start_row, limit=limit, dedupe=dedupe)]

    @staticmethod
    def _clean_name(raw: str) -> str:
        return " ".join(raw.replace("\xa0", " ").split())

    @staticmethod
    def _title_case(name: str) -> str:
        # Capitalizar cada palabra manteniendo acrónimos si todos eran mayúsculas (< = 3 letras) se deja.
        parts = name.lower().split()
        fixed = []
        for p in parts:
            if p.isupper() and len(p) <= 3:
                fixed.append(p)  # deja siglas cortas
            else:
                fixed.append(p[:1].upper() + p[1:])
        return " ".join(fixed)

    def list_sheets(self) -> List[str]:
        """Lista todas las hojas del Excel."""
        xl = pd.ExcelFile(self.path)
        return xl.sheet_names

    def load_all_sheets_by_mapping(
        self,
        column_mapping: Dict[str, str],
        selected_sheets: List[str] | None = None,
        start_row: int = 1,
        limit_per_sheet: int = 0,
        skip_header_rows: bool = True,
    ) -> Dict[str, List[Dict[str, str]]]:
        """Carga filas de múltiples hojas usando el mismo mapeo de columnas.
        
        Útil para Excels con un directorio por departamento donde cada hoja
        tiene la misma estructura (Departamento, Municipio, Hospital, etc.).
        
        Args:
            column_mapping: Mapeo de claves lógicas a nombres de columnas
            selected_sheets: Lista de hojas a procesar. Si es None, procesa todas.
            start_row: Fila inicial de datos (1 = primera fila después de encabezados)
            limit_per_sheet: Límite de filas por hoja (0 = sin límite)
            skip_header_rows: Si True, omite filas que parecen encabezados repetidos
            
        Returns:
            Dict con clave=nombre_hoja y valor=lista de registros
        """
        xl = pd.ExcelFile(self.path)
        all_sheets = xl.sheet_names
        
        # Filtrar hojas si se especificaron
        sheets_to_process = selected_sheets if selected_sheets else all_sheets
        
        result: Dict[str, List[Dict[str, str]]] = {}
        
        for sheet in sheets_to_process:
            if sheet not in all_sheets:
                continue
            
            try:
                rows = self._load_sheet_with_header_detection(
                    sheet, column_mapping, start_row, limit_per_sheet, skip_header_rows
                )
                if rows:
                    result[sheet] = rows
            except Exception:
                # Si una hoja falla, continuar con las demás
                continue
        
        return result

    def _load_sheet_with_header_detection(
        self,
        sheet_name: str,
        column_mapping: Dict[str, str],
        start_row: int = 1,
        limit: int = 0,
        skip_header_rows: bool = True,
    ) -> List[Dict[str, str]]:
        """Carga una hoja detectando y omitiendo filas de encabezado repetidas."""
        if not column_mapping:
            return []
        
        df = pd.read_excel(self.path, sheet_name=sheet_name, dtype=str)
        if df.empty:
            return []
        
        # Obtener nombres de columnas del mapeo para detectar encabezados
        header_values = {v.lower().strip() for v in column_mapping.values() if v}
        
        sub = df.iloc[start_row - 1:]
        if limit > 0:
            sub = sub.head(limit)
        
        rows: List[Dict[str, str]] = []
        keys = list(column_mapping.keys())
        
        for _, r in sub.iterrows():
            out: Dict[str, str] = {}
            is_header_row = False
            
            for k in keys:
                col = column_mapping.get(k, "")
                v = r.get(col) if col in df.columns else None
                val = str(v).strip() if isinstance(v, str) else ""
                
                # Detectar si es una fila de encabezado repetida
                if skip_header_rows and val.lower() in header_values:
                    is_header_row = True
                
                out[k] = val
            
            # Omitir filas vacías o que parecen encabezados
            if is_header_row:
                continue
            
            # Omitir filas completamente vacías o con solo valores nan
            primary_fields = ["gerente", "hospital", "municipio"]
            has_data = any(
                out.get(f, "").strip() and out.get(f, "").lower() not in ("nan", "none", "")
                for f in primary_fields if f in out
            )
            
            if has_data:
                rows.append(out)
        
        return rows

    def get_departments_from_sheets(self) -> List[str]:
        """Obtiene la lista de departamentos basándose en los nombres de las hojas.
        
        Asume que cada hoja representa un departamento.
        Excluye hojas con nombres genéricos como 'Resumen', 'Índice', etc.
        """
        excluded = {'resumen', 'indice', 'índice', 'index', 'total', 'consolidado', 'clave', 'x'}
        sheets = self.list_sheets()
        return [s for s in sheets if s.lower().strip() not in excluded]


__all__ = ["ExcelReader"]
