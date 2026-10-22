"""Los 32 gráficos del Inventario del Modelo PSS (ESE Hospital San Antonio, Gigante).

Cada entrada dice de qué fuente sale y con qué año. Hay tres fuentes:

* **TerriData (DNP)** — los `.txt` de los municipios.
* **ADRES** — el Excel de afiliación al SGSSS, para todo lo de aseguramiento,
  que TerriData no publica a nivel de corte.
* **Agregado** — los gráficos departamentales cuando no se cargó la extracción
  del departamento (ver `ambito.py`).

Los indicadores ODS llevan **año fijo**, el que cita el documento, para que la
comparación entre municipios sea del mismo corte. Si a un municipio le falta ese
año, se toma el más reciente anterior y el subtítulo muestra el rango.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Callable

from .. import graficas as g
from ..catalogo import Ind
from ..estilo import TAMANO_BASE, TAMANO_TORTA, Tema, formato_es
from ..lectura import Lectura
from ..resolucion import Resultado
from .afiliacion import Afiliacion, Cobertura
from .ambito import Ambito, datos_piramide, promedio_ponderado, suma

log = logging.getLogger("terridata.pss")

VIVIENDA = "Vivienda y acceso a servicios públicos"
ICM = "Índice de Ciudades Modernas (ICM)"
CONVIVENCIA = "Convivencia y seguridad ciudadana"

META_ODS_VACUNACION = 95.0

SECCIONES_PSS: list[tuple[str, str]] = [
    ("departamento", "Contexto territorial y de salud"),
    ("aseguramiento", "Aseguramiento en salud — área de influencia"),
    ("municipios", "Comparativo de los 8 municipios"),
    ("ods", "Agenda 2030 — ODS 1 a 17"),
]


# --------------------------------------------------------------------------- catálogo

CATALOGO_PSS: list[Ind] = [
    # --- demografía
    Ind("POB_H", "Población de hombres", "Personas", "NUM", 0, [
        ("Demografía y población", "Población total de hombres"),
        ("Censo 2005 y proyecciones DANE", "Población total de hombres")]),
    Ind("POB_M", "Población de mujeres", "Personas", "NUM", 0, [
        ("Demografía y población", "Población total de mujeres"),
        ("Censo 2005 y proyecciones DANE", "Población total de mujeres")]),
    Ind("POB_URB", "Población en cabecera municipal", "Personas", "NUM", 0, [
        ("Demografía y población", "Población urbana"),
        ("Censo 2005 y proyecciones DANE", "Población urbana")]),
    Ind("POB_RUR", "Población en centros poblados y rural disperso", "Personas", "NUM", 0, [
        ("Demografía y población", "Población rural"),
        ("Censo 2005 y proyecciones DANE", "Población rural")]),
    # --- salud
    Ind("FECUNDIDAD", "Tasa de fecundidad", "x 1.000 MEF", "NUM", 2, [
        ("Salud", "Tasa de fecundidad (x cada 1.000 mujeres en edad fértil)")]),
    Ind("MORT_MAT", "Razón de mortalidad materna", "x 100.000 NV", "NUM", 2, [
        ("Salud", "Razón de mortalidad materna a 42 días")]),
    Ind("MORT_INF", "Tasa de mortalidad infantil", "x 1.000 NV", "NUM", 2, [
        ("Salud", "Tasa de mortalidad infantil en menores de 1 año (x cada 1.000 nacidos vivos)")]),
    Ind("MORT_GEN", "Tasa de mortalidad general", "x 1.000 hab", "NUM", 2, [
        ("Salud", "Tasa de mortalidad (x cada 1.000 habitantes)")]),
    Ind("VAC_PENTA", "Cobertura de vacunación pentavalente", "%", "NUM", 2, [
        ("Salud", "Cobertura vacunación pentavalente en menores de 1 año")]),
    # --- convivencia
    Ind("T_VIF", "Tasa de violencia intrafamiliar", "x 100.000 hab", "NUM", 2, [
        (CONVIVENCIA, "Tasa de violencia intrafamiliar por cada 100.000 habitantes")]),
    Ind("T_INTER", "Tasa de violencia interpersonal", "x 100.000 hab", "NUM", 2, [
        (CONVIVENCIA, "Tasa de violencia interpersonal por cada 100.000 habitantes")]),
    Ind("T_HOMIC", "Tasa de homicidio intencional", "x 100.000 hab", "NUM", 2, [
        (CONVIVENCIA, "Tasa de homicidio intencional por cada 100.000 habitantes")]),
    # --- ODS
    Ind("IPM", "Índice de Pobreza Multidimensional", "%", "NUM", 2, [
        ("Pobreza", "indice de pobreza multidimensional - IPM (Censo)"),
        ("Pobreza", "Índice de pobreza multidimensional - IPM")]),
    Ind("PAE", "Preescolares con requerimiento nutricional (PAE)", "%", "NUM", 2, [
        ("Educación", "Porcentaje de niños y niñas de preescolar que reciben requerimiento nutricional a través del PAE")]),
    Ind("COB_NETA_EDU", "Cobertura neta en educación", "%", "NUM", 2, [
        ("Educación", "Cobertura neta en educación - Total")]),
    Ind("COTIZ_MUJERES", "Mujeres entre los trabajadores cotizantes", "%", "NUM", 2, [
        ("Mercado laboral", "Participación de los trabajadores cotizantes - Mujeres")]),
    Ind("ACU_CENSO", "Cobertura de acueducto (Censo)", "%", "NUM", 2, [
        (VIVIENDA, "Cobertura de acueducto (Censo)")]),
    Ind("ENER_RUR", "Cobertura de energía eléctrica rural", "%", "NUM", 2, [
        (VIVIENDA, "Cobertura de energía eléctrica rural")]),
    Ind("VA_PER_CAPITA", "Valor agregado per cápita", "$ corrientes", "NUM", 0, [
        ("Economía", "Valor agregado per cápita")]),
    Ind("INTERNET", "Penetración de acceso fijo a Internet", "%", "NUM", 2, [
        (VIVIENDA, "Penetración de acceso fijo a Internet"),
        (VIVIENDA, "Penetración de internet fijo en los hogares"),
        (VIVIENDA, "Penetración de banda ancha")]),
    Ind("NBI", "Necesidades Básicas Insatisfechas (NBI)", "%", "NUM", 2, [
        ("Pobreza", "indice de Necesidades Basicas Insatisfechas - NBI")]),
    Ind("ICM_SOSTENIBILIDAD", "Índice de Sostenibilidad (ICM)", "0-100", "NUM", 2, [
        (ICM, "Índice de Sostenibilidad")]),
    Ind("ICM_AMBIENTAL", "Índice de Cuidado ambiental (ICM)", "0-100", "NUM", 2, [
        (ICM, "Índice de Cuidado ambiental")]),
    Ind("VULNERABILIDAD", "Vulnerabilidad y riesgo por cambio climático", "0-100", "NUM", 2, [
        ("Ambiente", "índice de vulnerabilidad y riesgo por cambio climático"),
        ("Ambiente", "Vulnerabilidad y riesgo por cambio climático - Vulnerabilidad")]),
    Ind("ALC_REC", "Cobertura de alcantarillado (REC)", "%", "NUM", 2, [
        (VIVIENDA, "Cobertura de alcantarillado (REC)")]),
    Ind("SINAP", "Área municipal en el SINAP", "%", "NUM", 2, [
        ("Ambiente", "Porcentaje del área de la entidad territorial que hace parte del SINAP")]),
    Ind("ICM_INSTITUCIONAL", "Índice de Fortaleza Institucional (ICM)", "0-100", "NUM", 2, [
        (ICM, "Índice de Fortaleza Institucional")]),
]


# --------------------------------------------------------------------------- datos


@dataclass
class Datos:
    """Todo lo que necesitan los constructores, ya resuelto."""

    lectura: Lectura
    res: Resultado
    cobertura: Cobertura | None
    ambito: Ambito
    municipios: list[str]
    anio: int
    codigos: dict[str, str] = field(default_factory=dict)     # entidad -> código DANE
    cod_departamento: str = ""

    # --- consulta por año

    def valor(self, id_ind: str, entidad: str, anio: int | None = None):
        """(valor, año usado). Toma el año pedido o el más reciente anterior."""
        objetivo = self.anio if anio is None else anio
        serie = self.res.serie_temporal(id_ind, entidad)
        if not serie:
            return None, None
        if objetivo in serie:
            return serie[objetivo], objetivo
        anteriores = [a for a in serie if a <= objetivo]
        if not anteriores:
            return None, None
        usado = max(anteriores)
        return serie[usado], usado

    def valores(self, id_ind: str, anio: int | None = None):
        """Por municipio: (lista de valores, lista de años)."""
        pares = [self.valor(id_ind, e, anio) for e in self.municipios]
        return [p[0] for p in pares], [p[1] for p in pares]

    # --- población (TerriData no publica el total proyectado: se arma con H + M)

    def poblacion(self, entidad: str) -> float | None:
        h, _ = self.valor("POB_H", entidad)
        m, _ = self.valor("POB_M", entidad)
        if h is None and m is None:
            return None
        return (h or 0) + (m or 0)

    def urbana(self, entidad: str) -> float | None:
        return self.valor("POB_URB", entidad)[0]

    def rural(self, entidad: str) -> float | None:
        """Población fuera de la cabecera, del **mismo año** que la de cabecera.

        TerriData publica 'Población rural' solo en la serie del censo (2019),
        mientras 'Población urbana' llega hasta 2042: tomar la directa sin mirar
        el año daría una cabecera de 2026 con un resto de 2019, y la suma no
        sería la población del municipio. Cuando los años no coinciden, el resto
        se calcula como total menos cabecera.
        """
        urbana, anio_urbana = self.valor("POB_URB", entidad)
        directa, anio_directa = self.valor("POB_RUR", entidad)
        if directa is not None and anio_directa == anio_urbana:
            return directa
        total = self.poblacion(entidad)
        if total is None or urbana is None:
            return None
        return max(total - urbana, 0.0)

    @property
    def pesos(self) -> list[float | None]:
        return [self.poblacion(e) for e in self.municipios]

    # --- ámbito departamental

    def dep_suma(self, valores: list[float | None]) -> float | None:
        return suma(valores)

    def dep_tasa(self, id_ind: str, anio: int | None = None):
        """Tasa del ámbito: la del departamento si está, si no el promedio ponderado."""
        if self.ambito.es_departamento:
            valor, usado = self.valor(id_ind, self.ambito.nombre, anio)
            return valor, usado, 1
        vals, anios = self.valores(id_ind, anio)
        promedio, aportan = promedio_ponderado(vals, self.pesos)
        usados = [a for a in anios if a is not None]
        return promedio, (max(usados) if usados else None), aportan

    def dep_conteo(self, id_ind: str, anio: int | None = None):
        if self.ambito.es_departamento:
            return self.valor(id_ind, self.ambito.nombre, anio)
        vals, anios = self.valores(id_ind, anio)
        usados = [a for a in anios if a is not None]
        return suma(vals), (max(usados) if usados else None)

    def dep_poblacion(self) -> float | None:
        if self.ambito.es_departamento:
            return self.poblacion(self.ambito.nombre)
        return suma([self.poblacion(e) for e in self.municipios])

    # --- afiliación (Excel de ADRES)

    def afiliacion_municipio(self, entidad: str) -> Afiliacion | None:
        if not self.cobertura:
            return None
        return self.cobertura.municipio(self.codigos.get(entidad, ""))

    def afiliacion_departamento(self) -> Afiliacion | None:
        if not self.cobertura:
            return None
        return self.cobertura.departamento(self.cod_departamento)


# --------------------------------------------------------------------------- render


@dataclass(frozen=True)
class Spec:
    numero: int
    id: str
    seccion: str
    titulo: str
    constructor: Callable
    fuente: str = "TerriData (DNP)"


@dataclass
class Render:
    spec: Spec
    fig: object
    titulo: str
    subtitulo: str
    pie: str
    encabezados: list[str] = field(default_factory=list)
    filas: list[list[str]] = field(default_factory=list)
    svg: str = ""

    @property
    def archivo(self) -> str:
        """Numerado como en el inventario, para que el orden del disco sea el del documento."""
        return f"g{self.spec.numero:02d}_{self.spec.id}"


def _rango_anios(anios: list[int | None]) -> str:
    presentes = sorted({a for a in anios if a})
    if not presentes:
        return "sin año"
    if len(presentes) == 1:
        return str(presentes[0])
    return f"{presentes[0]}–{presentes[-1]}"


def _tabla(encabezados: list[str], filas: list[list[str]]):
    return encabezados, filas


def _pie(fuente: str, anios) -> str:
    etiqueta = anios if isinstance(anios, str) else _rango_anios(anios)
    return f"Fuente: {fuente} · Dato {etiqueta}"
