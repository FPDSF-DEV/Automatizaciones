"""Parámetros de cálculo y rutas del proyecto."""
from __future__ import annotations

from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
# Raíz del proyecto unificado: los datos viven en DATA/ y los resultados en SALIDAS/.
RAIZ_PROYECTO = RAIZ.parent.parent


def _carpeta_siho(base: Path) -> Path:
    """DATA/SIHO puede traer los reportes directamente o dentro de una sola
    carpeta por hospital (p. ej. DATA/SIHO/SJDC_SIHO/)."""
    if (base / "Formularios_Anuales").is_dir() or not base.is_dir():
        return base
    hospitales = [d for d in sorted(base.iterdir()) if (d / "Formularios_Anuales").is_dir()]
    return hospitales[0] if len(hospitales) == 1 else base


DATOS = _carpeta_siho(RAIZ_PROYECTO / "DATA" / "SIHO")
SALIDA = RAIZ_PROYECTO / "SALIDAS" / "productividad"

# --- Parámetros de cálculo -------------------------------------------------
# Son supuestos, no datos medidos. Cámbielos aquí y todo el informe se recalcula.
PARAMETROS: dict[str, float] = {
    # Días calendario al año. Supuesto: servicio de 24 horas, 365 días.
    "DIAS_ANIO": 365,
    # Semanas al año. Se usa para los pacientes por cama de observación.
    "SEMANAS_ANIO": 52,
    # Días hábiles al año. Supuesto: 5 días por semana x 52 semanas.
    "DIAS_HABILES": 260,
    # Meses al año. Convierte las personas de nómina en meses contratados.
    "MESES_ANIO": 12,
}

# --- Reportes de entrada ---------------------------------------------------
# Solo se leen estas carpetas; las demás de Formularios_Anuales se ignoran.
CARPETA_FORMULARIOS = "Formularios_Anuales"
# Ruta dentro de la carpeta SIHO (estructura de SJDC_SIHO).
CARPETA_OPS = "Consultas_Detalladas/Reporte_Contratacion_Externa_desde_2020"

# clave -> (subcarpeta dentro de Formularios_Anuales/<año>/, columna con el valor)
FORMULARIOS: dict[str, tuple[str, str]] = {
    "capacidad": ("Capacidad_Instalada", "vigencia_actual"),
    "produccion": ("Produccion", "total"),
}

# Nómina: se suman los cargos ocupados por tipo de cargo (APOYO / OPERATIVO).
RECURSOS_HUMANOS = {
    "carpeta": "Recursos_Humanos",
    "col_tipo": "cargTipo",
    "col_cantidad": "numero_cargos",
}

# OPS: cada fila es un contrato. El área dice si es operativo o de apoyo y
# numero_meses los meses realmente contratados.
OPS = {
    "col_area": "nombre_area",
    "col_meses": "numero_meses",
    "col_fecha_inicio": "fecha_inicio_contrato",
    "texto_operativo": "Operativo",
    "texto_apoyo": "Apoyo",
    # Solo se usa el reporte de este trimestre: trae todos los contratos del año.
    "trimestre_anual": "octubre-dic",
}
