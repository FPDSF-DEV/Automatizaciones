"""Definición y cálculo de los indicadores.

Cada indicador se declara una sola vez, aquí. Agregar un indicador nuevo es
agregar una entrada a la lista INDICADORES: el cálculo, la tabla, las gráficas
y el informe salen solos, sin tocar ningún otro archivo.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

import pandas as pd

from .carga import normalizar
from .config import PARAMETROS

Origen = Callable[[dict[str, pd.DataFrame], pd.DataFrame, dict[str, float]], pd.Series]


class ConceptoNoEncontrado(Exception):
    """El CSV no trae una fila que algún indicador necesita."""


# --------------------------------------------------------------------------
# Constructores de origen: de dónde sale cada columna de la tabla
# --------------------------------------------------------------------------
def de(fuente: str, concepto: str) -> Origen:
    """Trae tal cual una fila de un CSV."""

    def _origen(datos, tabla, params):
        df = datos[fuente]
        buscado = normalizar(concepto)
        filas = [c for c in df.index if normalizar(c) == buscado]
        if not filas:
            raise ConceptoNoEncontrado(
                f"'{concepto}' no está en los reportes de {fuente}. "
                f"Revise que el texto del concepto coincida."
            )
        return df.loc[filas].sum(axis=0)

    return _origen


def suma(fuente: str, *conceptos: str) -> Origen:
    """Suma varias filas de un mismo CSV."""

    def _origen(datos, tabla, params):
        partes = [de(fuente, c)(datos, tabla, params) for c in conceptos]
        return sum(partes[1:], partes[0])

    return _origen


def total(fuente: str) -> Origen:
    """Suma todas las filas del CSV (producción total del año)."""

    def _origen(datos, tabla, params):
        return datos[fuente].sum(axis=0)

    return _origen


def calculo(fn: Callable[[pd.DataFrame, dict[str, float]], pd.Series]) -> Origen:
    """Se calcula con las columnas ya resueltas de la misma tabla."""

    def _origen(datos, tabla, params):
        return fn(tabla, params)

    return _origen


def razon(numerador: str, denominador: str) -> Origen:
    """División protegida contra el denominador en cero."""

    def _origen(datos, tabla, params):
        num, den = tabla[numerador], tabla[denominador]
        return num.divide(den).where(den != 0)

    return _origen


# --------------------------------------------------------------------------
@dataclass(frozen=True)
class Columna:
    nombre: str
    origen: Origen
    formato: str = "{:,.0f}"


@dataclass(frozen=True)
class Indicador:
    clave: str
    grupo: str
    titulo: str
    descripcion: str
    fuentes: tuple[str, ...]
    columnas: tuple[Columna, ...]
    indicador: str
    eje_y: str
    volumen: tuple[str, ...] = ()
    eje_y_volumen: str = ""
    grafica_volumen: str = "barras"
    porcentaje: bool = False

    def anios(self, datos: dict[str, pd.DataFrame]) -> list[int]:
        """Años presentes en todas las fuentes que usa el indicador."""
        conjuntos = [set(datos[f].columns) for f in self.fuentes]
        comunes = set.intersection(*conjuntos) if conjuntos else set()
        return sorted(comunes)

    def calcular(self, datos: dict[str, pd.DataFrame]) -> pd.DataFrame:
        anios = self.anios(datos)
        tabla = pd.DataFrame(index=pd.Index(anios, name="Año"))
        for col in self.columnas:
            serie = col.origen(datos, tabla, PARAMETROS)
            tabla[col.nombre] = pd.Series(serie).reindex(anios).astype(float)
        return tabla

    def formatos(self) -> dict[str, str]:
        return {c.nombre: c.formato for c in self.columnas}


# --------------------------------------------------------------------------
# Los indicadores
# --------------------------------------------------------------------------
CAPACIDAD = "Capacidad instalada"
TALENTO = "Talento humano"

INDICADORES: list[Indicador] = [
    Indicador(
        clave="camas_hospitalizacion",
        grupo=CAPACIDAD,
        titulo="Camas de hospitalización",
        descripcion="Ocupación de las camas frente a los días cama disponibles.",
        fuentes=("capacidad", "produccion"),
        columnas=(
            Columna("Número de camas", de("capacidad", "Camas de hospitalización")),
            Columna(
                "Días cama disponibles",
                de("produccion", "Total de días cama disponibles"),
            ),
            Columna(
                "Días cama ocupados",
                de("produccion", "Total de días cama ocupados"),
            ),
            Columna(
                "Tasa de ocupación",
                razon("Días cama ocupados", "Días cama disponibles"),
                "{:.1%}",
            ),
        ),
        indicador="Tasa de ocupación",
        eje_y="Tasa de ocupación",
        volumen=("Días cama disponibles", "Días cama ocupados"),
        eje_y_volumen="Días cama",
        porcentaje=True,
    ),
    Indicador(
        clave="observacion",
        grupo=CAPACIDAD,
        titulo="Camas de observación",
        descripcion="Pacientes atendidos por cada cama de observación en una semana.",
        fuentes=("capacidad", "produccion"),
        columnas=(
            Columna("Camas de observación", de("capacidad", "Camas de observación")),
            Columna(
                "Cupos disponibles por semana",
                calculo(lambda t, p: t["Camas de observación"] * p["SEMANAS_ANIO"]),
            ),
            Columna(
                "Pacientes en observación",
                de("produccion", "Pacientes en Observación"),
            ),
            Columna(
                "Pacientes por cama por semana",
                razon("Pacientes en observación", "Cupos disponibles por semana"),
                "{:,.2f}",
            ),
        ),
        indicador="Pacientes por cama por semana",
        eje_y="Pacientes / cama / semana",
        volumen=("Pacientes en observación",),
        eje_y_volumen="Pacientes",
    ),
    Indicador(
        clave="consulta_externa",
        grupo=CAPACIDAD,
        titulo="Consulta externa",
        descripcion="Consultas electivas atendidas por consultorio en un día hábil.",
        fuentes=("capacidad", "produccion"),
        columnas=(
            Columna(
                "Consultorios de consulta externa",
                de("capacidad", "Consultorios de consulta externa"),
            ),
            Columna(
                "Cupos día-consultorio al año",
                calculo(
                    lambda t, p: t["Consultorios de consulta externa"] * p["DIAS_HABILES"]
                ),
            ),
            Columna(
                "Consultas de medicina general",
                de("produccion", "Consultas de medicina general electivas realizadas"),
            ),
            Columna(
                "Consultas de medicina especializada",
                de(
                    "produccion",
                    "Consultas de medicina especializada electivas realizadas",
                ),
            ),
            Columna(
                "Total consultas electivas",
                calculo(
                    lambda t, p: t["Consultas de medicina general"]
                    + t["Consultas de medicina especializada"]
                ),
            ),
            Columna(
                "Consultas por consultorio por día",
                razon("Total consultas electivas", "Cupos día-consultorio al año"),
                "{:,.2f}",
            ),
        ),
        indicador="Consultas por consultorio por día",
        eje_y="Consultas / consultorio / día",
        volumen=("Consultas de medicina general", "Consultas de medicina especializada"),
        eje_y_volumen="Consultas",
    ),
    Indicador(
        clave="urgencias",
        grupo=CAPACIDAD,
        titulo="Urgencias",
        descripcion="Consultas urgentes atendidas por consultorio en un día.",
        fuentes=("capacidad", "produccion"),
        columnas=(
            Columna(
                "Consultorios de urgencias",
                de("capacidad", "Consultorios en el servicio de urgencias"),
            ),
            Columna(
                "Cupos día-consultorio al año",
                calculo(lambda t, p: t["Consultorios de urgencias"] * p["DIAS_ANIO"]),
            ),
            Columna(
                "Consultas de medicina general",
                de("produccion", "Consultas de medicina general urgentes realizadas"),
            ),
            Columna(
                "Consultas de medicina especializada",
                de(
                    "produccion",
                    "Consultas de medicina especializada urgentes realizadas",
                ),
            ),
            Columna(
                "Total consultas urgentes",
                calculo(
                    lambda t, p: t["Consultas de medicina general"]
                    + t["Consultas de medicina especializada"]
                ),
            ),
            Columna(
                "Consultas por consultorio por día",
                razon("Total consultas urgentes", "Cupos día-consultorio al año"),
                "{:,.2f}",
            ),
        ),
        indicador="Consultas por consultorio por día",
        eje_y="Consultas / consultorio / día",
        volumen=("Consultas de medicina general", "Consultas de medicina especializada"),
        eje_y_volumen="Consultas",
    ),
    Indicador(
        clave="quirofanos",
        grupo=CAPACIDAD,
        titulo="Quirófanos",
        descripcion="Cirugías realizadas por día calendario, incluidas las cesáreas.",
        fuentes=("capacidad", "produccion"),
        columnas=(
            Columna("Salas de quirófanos", de("capacidad", "Salas de quirófanos")),
            Columna(
                "Cirugías sin partos ni cesáreas",
                de(
                    "produccion",
                    "Total de cirugías realizadas (Sin incluir partos y cesáreas)",
                ),
            ),
            Columna("Cesáreas", de("produccion", "Partos por cesárea")),
            Columna(
                "Total cirugías",
                calculo(
                    lambda t, p: t["Cirugías sin partos ni cesáreas"] + t["Cesáreas"]
                ),
            ),
            Columna(
                "Cirugías por día",
                calculo(lambda t, p: t["Total cirugías"] / p["DIAS_ANIO"]),
                "{:,.2f}",
            ),
        ),
        indicador="Cirugías por día",
        eje_y="Cirugías / día",
        volumen=("Cirugías sin partos ni cesáreas", "Cesáreas"),
        eje_y_volumen="Procedimientos",
    ),
    Indicador(
        clave="partos",
        grupo=CAPACIDAD,
        titulo="Sala de partos",
        descripcion="Partos vaginales atendidos por cada mesa de partos en el año.",
        fuentes=("capacidad", "produccion"),
        columnas=(
            Columna("Mesas de partos", de("capacidad", "Mesas de partos")),
            Columna("Partos vaginales", de("produccion", "Partos vaginales")),
            Columna(
                "Partos por mesa por año",
                razon("Partos vaginales", "Mesas de partos"),
                "{:,.2f}",
            ),
        ),
        indicador="Partos por mesa por año",
        eje_y="Partos / mesa / año",
        volumen=("Partos vaginales",),
        eje_y_volumen="Partos",
    ),
    Indicador(
        clave="odontologia",
        grupo=CAPACIDAD,
        titulo="Odontología",
        descripcion="Sesiones realizadas por unidad odontológica en un día hábil.",
        fuentes=("capacidad", "produccion"),
        columnas=(
            Columna(
                "Unidades de odontología",
                de("capacidad", "Número de unidades de odontología"),
            ),
            Columna(
                "Cupos día-unidad al año",
                calculo(lambda t, p: t["Unidades de odontología"] * p["DIAS_HABILES"]),
            ),
            Columna(
                "Sesiones de odontología",
                de("produccion", "Número de sesiones de odontología realizadas"),
            ),
            Columna(
                "Sesiones por unidad por día",
                razon("Sesiones de odontología", "Cupos día-unidad al año"),
                "{:,.2f}",
            ),
        ),
        indicador="Sesiones por unidad por día",
        eje_y="Sesiones / unidad / día",
        volumen=("Sesiones de odontología",),
        eje_y_volumen="Sesiones",
    ),
    Indicador(
        clave="talento_global",
        grupo=TALENTO,
        titulo="Productividad global del talento humano",
        descripcion=(
            "Producción institucional total frente a la oferta total de talento "
            "humano en meses-equivalentes: todo el personal de planta (apoyo y "
            "operativo) convertido a meses de disponibilidad, más los meses "
            "contratados de todas las OPS del año. Se mide de forma agregada "
            "porque el personal se redistribuye entre servicios según la demanda."
        ),
        fuentes=("nomina", "ops", "produccion"),
        columnas=(
            Columna("Personal de planta", de("nomina", "TOTAL")),
            Columna("Contratos OPS", de("ops", "CONTRATOS TOTAL")),
            Columna(
                "Meses-equivalentes planta",
                calculo(lambda t, p: t["Personal de planta"] * p["MESES_ANIO"]),
                "{:,.2f}",
            ),
            Columna("Meses contratados OPS", de("ops", "MESES CONTRATADOS TOTAL"), "{:,.2f}"),
            Columna(
                "Oferta total (meses)",
                calculo(
                    lambda t, p: t["Meses-equivalentes planta"] + t["Meses contratados OPS"]
                ),
                "{:,.2f}",
            ),
            Columna("Producción total", total("produccion")),
            Columna(
                "Producción por mes-equivalente",
                razon("Producción total", "Oferta total (meses)"),
                "{:,.2f}",
            ),
        ),
        indicador="Producción por mes-equivalente",
        eje_y="Producción / mes-equivalente",
        volumen=("Meses-equivalentes planta", "Meses contratados OPS"),
        eje_y_volumen="Meses-equivalentes",
        grafica_volumen="barras_apiladas",
    ),
    Indicador(
        clave="talento_meses",
        grupo=TALENTO,
        titulo="Productividad por mes contratado",
        descripcion=(
            "Producción total del año dividida entre los meses realmente "
            "contratados de personal operativo (nómina + OPS)."
        ),
        fuentes=("nomina", "ops", "produccion"),
        columnas=(
            Columna("Operativos nómina", de("nomina", "OPERATIVO")),
            Columna("Operativos OPS", de("ops", "OPERATIVO")),
            Columna(
                "Meses contratados nómina",
                calculo(lambda t, p: t["Operativos nómina"] * p["MESES_ANIO"]),
                "{:,.2f}",
            ),
            Columna(
                "Meses contratados OPS",
                de("ops", "MESES CONTRATADOS OPERATIVOS"),
                "{:,.2f}",
            ),
            Columna(
                "Total meses contratados",
                calculo(
                    lambda t, p: t["Meses contratados nómina"] + t["Meses contratados OPS"]
                ),
                "{:,.2f}",
            ),
            Columna("Producción total", total("produccion")),
            Columna(
                "Producción por mes contratado",
                razon("Producción total", "Total meses contratados"),
                "{:,.2f}",
            ),
        ),
        indicador="Producción por mes contratado",
        eje_y="Producción / mes",
        volumen=("Meses contratados nómina", "Meses contratados OPS"),
        eje_y_volumen="Meses contratados",
        grafica_volumen="barras_apiladas",
    ),
    Indicador(
        clave="talento_contratos",
        grupo=TALENTO,
        titulo="Productividad por contrato",
        descripcion=(
            "Producción total del año dividida entre el número de contratos "
            "operativos vigentes (nómina + OPS)."
        ),
        fuentes=("nomina", "ops", "produccion"),
        columnas=(
            Columna("Operativos nómina", de("nomina", "OPERATIVO")),
            Columna("Operativos OPS", de("ops", "OPERATIVO")),
            Columna(
                "Total contratos operativos",
                calculo(lambda t, p: t["Operativos nómina"] + t["Operativos OPS"]),
            ),
            Columna("Producción total", total("produccion")),
            Columna(
                "Producción por contrato",
                razon("Producción total", "Total contratos operativos"),
                "{:,.2f}",
            ),
        ),
        indicador="Producción por contrato",
        eje_y="Producción / contrato",
        volumen=("Operativos nómina", "Operativos OPS"),
        eje_y_volumen="Contratos",
        grafica_volumen="barras_apiladas",
    ),
]


def por_grupo() -> dict[str, list[Indicador]]:
    grupos: dict[str, list[Indicador]] = {}
    for ind in INDICADORES:
        grupos.setdefault(ind.grupo, []).append(ind)
    return grupos


def calcular_todo(datos: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    return {ind.clave: ind.calcular(datos) for ind in INDICADORES}


def resumen(datos: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Una fila por año, una columna por indicador."""
    columnas = {}
    for ind in INDICADORES:
        tabla = ind.calcular(datos)
        columnas[f"{ind.titulo} — {ind.indicador}"] = tabla[ind.indicador]
    return pd.DataFrame(columnas)
