"""Ámbito departamental y datos por quinquenios.

Los gráficos 1 a 7 del inventario son del **departamento**. TerriData entrega un
archivo por entidad, así que el departamento solo está disponible si se descargó
su propia extracción. Este módulo resuelve las dos situaciones:

* si entre los `.txt` hay una entidad que es el departamento, se usa tal cual;
* si no, se arma un **agregado del área de influencia**: se suman los conteos y
  se promedian las tasas ponderando por población.

Un agregado no es el departamento y no se disfraza de él: `Ambito.nombre` y
`Ambito.calificador` van al título y al pie de cada gráfica.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from ..lectura import Fila

log = logging.getLogger("terridata.pss.ambito")

# Los 17 grupos quinquenales que publica TerriData, en orden de la pirámide.
GRUPOS_QUINQUENALES = [
    "00-04", "05-09", "10-14", "15-19", "20-24", "25-29", "30-34", "35-39",
    "40-44", "45-49", "50-54", "55-59", "60-64", "65-69", "70-74", "75-79",
    "80 o más",
]

DIMENSIONES_QUINQUENIOS = ["Demografía y población", "Censo 2005 y proyecciones DANE"]


@dataclass
class Ambito:
    """El territorio del que hablan los gráficos 1 a 7."""

    nombre: str
    calificador: str
    es_departamento: bool
    entidades: list[str] = field(default_factory=list)

    @property
    def titulo(self) -> str:
        return f"{self.nombre} ({self.calificador})" if self.calificador else self.nombre


def detectar_ambito(entidades: list[str], departamento: str) -> Ambito:
    """¿Hay una extracción del departamento entre los archivos cargados?"""
    departamento = (departamento or "").strip()
    for entidad in entidades:
        if departamento and entidad.strip().lower() == departamento.lower():
            municipios = [e for e in entidades if e != entidad]
            log.info("ámbito departamental: se usará la entidad '%s'", entidad)
            return Ambito(
                nombre=entidad,
                calificador="departamento",
                es_departamento=True,
                entidades=[entidad] + municipios,
            )
    log.info("no hay extracción del departamento: los gráficos departamentales "
             "se arman con el agregado de %d municipios", len(entidades))
    return Ambito(
        nombre="Área de influencia",
        calificador=f"agregado de {len(entidades)} municipios",
        es_departamento=False,
        entidades=list(entidades),
    )


def municipios_de(ambito: Ambito) -> list[str]:
    """Las entidades municipales, sin el departamento si estaba cargado."""
    if ambito.es_departamento:
        return [e for e in ambito.entidades if e != ambito.nombre]
    return list(ambito.entidades)


# --------------------------------------------------------------------------- agregación


def suma(valores: list[float | None]) -> float | None:
    """Suma de lo que haya. None solo si no hay ningún dato."""
    presentes = [v for v in valores if v is not None]
    return sum(presentes) if presentes else None


def promedio_ponderado(
    valores: list[float | None], pesos: list[float | None]
) -> tuple[float | None, int]:
    """Promedio de una tasa ponderado por población.

    Las tasas no se suman: la fecundidad de ocho municipios sumada no significa
    nada. Devuelve también cuántas entidades aportaron, para poder decirlo.
    """
    numerador = 0.0
    denominador = 0.0
    aportan = 0
    for valor, peso in zip(valores, pesos):
        if valor is None:
            continue
        p = peso if peso and peso > 0 else 1.0
        numerador += valor * p
        denominador += p
        aportan += 1
    if not aportan:
        return None, 0
    return numerador / denominador, aportan


# --------------------------------------------------------------------------- quinquenios


@dataclass
class Piramide:
    grupos: list[str]
    hombres: list[float | None]
    mujeres: list[float | None]
    anio: int | None
    dimension: str
    entidades: int
    completa: bool


def _indice_quinquenios(filas: list[Fila], entidades: set[str]):
    """(dimensión, sexo, grupo, año) -> suma sobre las entidades pedidas."""
    acumulado: dict[tuple[str, str, str, int], float] = {}
    for f in filas:
        if f.entidad not in entidades or f.valor is None:
            continue
        if f.dimension not in DIMENSIONES_QUINQUENIOS:
            continue
        for sexo, prefijo in (("H", "Población de hombres de "),
                              ("M", "Población de mujeres de ")):
            if f.indicador.startswith(prefijo):
                grupo = f.indicador[len(prefijo):].strip()
                clave = (f.dimension, sexo, grupo, f.anio)
                acumulado[clave] = acumulado.get(clave, 0.0) + f.valor
                break
    return acumulado


def datos_piramide(
    filas: list[Fila], entidades: list[str], anio_objetivo: int
) -> Piramide:
    """Pirámide del año más cercano al objetivo con **los dos sexos completos**.

    TerriData publica las dos series (proyecciones y censo) y no siempre tienen
    la misma cobertura: en las extracciones municipales del Huila la serie
    masculina por quinquenios solo trae 2041-2042, mientras la femenina va de
    2018 a 2042. Mezclar sexos de años distintos daría una pirámide falsa, así
    que se busca el año más reciente que no pase del objetivo y tenga los 17
    grupos de **ambos** sexos en la **misma** dimensión.
    """
    acumulado = _indice_quinquenios(filas, set(entidades))
    if not acumulado:
        return Piramide(GRUPOS_QUINQUENALES, [None] * 17, [None] * 17, None, "", 0, False)

    candidatos: list[tuple[int, str]] = []
    for dimension in DIMENSIONES_QUINQUENIOS:
        anios = {a for (d, _s, _g, a) in acumulado if d == dimension}
        for anio in anios:
            completos = all(
                (dimension, sexo, grupo, anio) in acumulado
                for sexo in ("H", "M")
                for grupo in GRUPOS_QUINQUENALES
            )
            if completos:
                candidatos.append((anio, dimension))

    if not candidatos:
        log.warning("no hay ningún año con los 17 quinquenios de ambos sexos completos")
        return Piramide(GRUPOS_QUINQUENALES, [None] * 17, [None] * 17, None, "", 0, False)

    # El año más cercano al objetivo sin pasarse; si todos se pasan, el menor.
    hasta_objetivo = [c for c in candidatos if c[0] <= anio_objetivo]
    anio, dimension = max(hasta_objetivo) if hasta_objetivo else min(candidatos)

    return Piramide(
        grupos=list(GRUPOS_QUINQUENALES),
        hombres=[acumulado[(dimension, "H", g, anio)] for g in GRUPOS_QUINQUENALES],
        mujeres=[acumulado[(dimension, "M", g, anio)] for g in GRUPOS_QUINQUENALES],
        anio=anio,
        dimension=dimension,
        entidades=len(entidades),
        completa=True,
    )


def anios_disponibles_quinquenios(filas: list[Fila], entidades: list[str]) -> dict[str, list[int]]:
    """Diagnóstico: qué años tiene cada sexo, para explicar por qué la pirámide
    puede quedar en un año anterior al pedido."""
    acumulado = _indice_quinquenios(filas, set(entidades))
    resultado: dict[str, set[int]] = {"H": set(), "M": set()}
    for (dimension, sexo, grupo, anio) in acumulado:
        if grupo in GRUPOS_QUINQUENALES:
            resultado[sexo].add(anio)
    return {sexo: sorted(anios) for sexo, anios in resultado.items()}
