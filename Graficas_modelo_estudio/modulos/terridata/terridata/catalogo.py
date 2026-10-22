"""Catálogo de indicadores de TerriData (Apéndice A del PLAN).

Los nombres están verificados contra extracciones reales: una tilde o un espacio
de más rompe la búsqueda. El orden de los alias dentro de cada entrada es
deliberado — se usa el primero que exista en los datos cargados (§4.2), y para
población la serie "Censo 2005 y proyecciones DANE" va primero (§4.4).
"""

from __future__ import annotations

from dataclasses import dataclass

@dataclass(frozen=True)
class Ind:
    id: str
    etiqueta: str
    unidad: str
    tipo: str            # "NUM" | "TXT"
    decimales: int
    alias: list          # [(dimensión, indicador), ...] en orden de preferencia

CATALOGO = [
    # --- Descripción general
    Ind("COD_DANE", "Código DANE", "Texto", "TXT", 0, [("Descripción general", "Código DANE")]),
    Ind("REGION", "Región", "Texto", "TXT", 0, [("Descripción general", "Región")]),
    Ind("SUBREGION", "Subregión (SGR)", "Texto", "TXT", 0, [("Descripción general", "Subregión (SGR)")]),
    Ind("CAT617", "Categoría Ley 617 de 2000", "Texto", "TXT", 0, [("Descripción general", "Categoría ley 617 de 2000")]),
    Ind("CAT_RURAL", "Categoría de ruralidad", "Texto", "TXT", 0, [("Descripción general", "Categoría de ruralidad")]),
    Ind("EXTENSION", "Extensión territorial", "Km²", "NUM", 2, [("Descripción general", "Extensión")]),
    Ind("DENSIDAD", "Densidad poblacional", "Hab/Km²", "NUM", 2, [("Descripción general", "Densidad poblacional"), ("Censo 2005 y proyecciones DANE", "Densidad poblacional")]),
    # --- Demografía  (ver §4.4: la serie "Censo 2005 y proyecciones DANE" va primero)
    Ind("POB_TOTAL", "Población total", "Personas", "NUM", 0, [("Censo 2005 y proyecciones DANE", "Población total"), ("Demografía y población", "Población total"), ("Descripción general", "Población total")]),
    Ind("POB_URB", "Población cabecera (urbana)", "Personas", "NUM", 0, [("Censo 2005 y proyecciones DANE", "Población urbana"), ("Demografía y población", "Población urbana")]),
    Ind("POB_RUR", "Población resto (rural)", "Personas", "NUM", 0, [("Censo 2005 y proyecciones DANE", "Población rural"), ("Demografía y población", "Población rural")]),
    Ind("POB_H", "Población hombres", "Personas", "NUM", 0, [("Censo 2005 y proyecciones DANE", "Población total de hombres"), ("Demografía y población", "Población total de hombres")]),
    Ind("POB_M", "Población mujeres", "Personas", "NUM", 0, [("Censo 2005 y proyecciones DANE", "Población total de mujeres"), ("Demografía y población", "Población total de mujeres")]),
    Ind("PCT_H", "Porcentaje población de hombres", "%", "NUM", 2, [("Censo 2005 y proyecciones DANE", "Porcentaje población de hombres"), ("Demografía y población", "Porcentaje población de hombres")]),
    Ind("PCT_M", "Porcentaje población de mujeres", "%", "NUM", 2, [("Censo 2005 y proyecciones DANE", "Porcentaje población de mujeres"), ("Demografía y población", "Porcentaje población de mujeres")]),
    Ind("SISBEN_T", "Puntaje SISBEN promedio — Total", "Puntos", "NUM", 2, [("Demografía y población", "Puntaje SISBEN: Promedio - Total")]),
    Ind("SISBEN_REG", "Registros válidos SISBEN", "Personas", "NUM", 0, [("Demografía y población", "Total registros válidos - Personas")]),
    # --- Vivienda y servicios públicos
    Ind("ACU_CENSO", "Cobertura de acueducto (Censo)", "% ×100", "NUM", 2, [("Vivienda y acceso a servicios públicos", "Cobertura de acueducto (Censo)")]),
    Ind("ACU_REC", "Cobertura de acueducto (REC)", "%", "NUM", 2, [("Vivienda y acceso a servicios públicos", "Cobertura de acueducto (REC)")]),
    Ind("ACU_URB", "Cobertura de acueducto urbana (REC)", "%", "NUM", 2, [("Vivienda y acceso a servicios públicos", "Cobertura de acueducto urbana (REC)")]),
    Ind("ACU_RUR", "Cobertura de acueducto rural (REC)", "%", "NUM", 2, [("Vivienda y acceso a servicios públicos", "Cobertura de acueducto rural (REC)")]),
    Ind("ALC_CENSO", "Cobertura de alcantarillado (Censo)", "% ×100", "NUM", 2, [("Vivienda y acceso a servicios públicos", "Cobertura de alcantarillado (Censo)")]),
    Ind("ALC_REC", "Cobertura de alcantarillado (REC)", "%", "NUM", 2, [("Vivienda y acceso a servicios públicos", "Cobertura de alcantarillado (REC)")]),
    Ind("ALC_URB", "Cobertura de alcantarillado urbana (REC)", "%", "NUM", 2, [("Vivienda y acceso a servicios públicos", "Cobertura de alcantarillado urbana (REC)")]),
    Ind("ALC_RUR", "Cobertura de alcantarillado rural (REC)", "%", "NUM", 2, [("Vivienda y acceso a servicios públicos", "Cobertura de alcantarillado rural (REC)")]),
    Ind("ASEO_REC", "Cobertura de aseo (REC)", "%", "NUM", 2, [("Vivienda y acceso a servicios públicos", "Cobertura de aseo (REC)")]),
    Ind("ASEO_URB", "Cobertura de aseo urbana (REC)", "%", "NUM", 2, [("Vivienda y acceso a servicios públicos", "Cobertura de aseo urbana (REC)")]),
    Ind("ASEO_RUR", "Cobertura de aseo rural (REC)", "%", "NUM", 2, [("Vivienda y acceso a servicios públicos", "Cobertura de aseo rural (REC)")]),
    Ind("ENER_RUR", "Cobertura de energía eléctrica rural", "% ×100", "NUM", 2, [("Vivienda y acceso a servicios públicos", "Cobertura de energía eléctrica rural")]),
    Ind("BANDA", "Penetración de internet fijo", "% ×100", "NUM", 2, [("Vivienda y acceso a servicios públicos", "Penetración de banda ancha"), ("Vivienda y acceso a servicios públicos", "Penetración de internet fijo en los hogares"), ("Vivienda y acceso a servicios públicos", "Penetración de acceso fijo a Internet")]),
    Ind("DEF_CUANT", "Déficit cuantitativo de vivienda", "% ×100", "NUM", 2, [("Vivienda y acceso a servicios públicos", "Déficit cuantitativo de vivienda"), ("Vivienda y acceso a servicios públicos", "Déficit cuantitativo de vivienda (Censo)")]),
    Ind("DEF_CUAL", "Déficit cualitativo de vivienda", "% ×100", "NUM", 2, [("Vivienda y acceso a servicios públicos", "Déficit cualitativo de vivienda"), ("Vivienda y acceso a servicios públicos", "Déficit cualitativo de vivienda (Censo)")]),
    # --- Salud  (los primeros alias recogen el bloque de corte propio si lo pegaron)
    Ind("AFIL_CONTRIB", "Afiliados al régimen contributivo", "Personas", "NUM", 0, [("Salud", "Afiliados régimen contributivo"), ("Salud", "Afiliados al régimen contributivo")]),
    Ind("AFIL_SUBS", "Afiliados al régimen subsidiado", "Personas", "NUM", 0, [("Salud", "Afiliados régimen subsidiado"), ("Salud", "Afiliados al régimen subsidado"), ("Salud", "Afiliados al régimen subsidiado")]),
    Ind("AFIL_ESP", "Afiliados a regímenes especiales", "Personas", "NUM", 0, [("Salud", "Afiliados régimen de excepción y especiales"), ("Salud", "Afiliados a regímenes especiales")]),
    Ind("AFIL_SGSSS", "Afiliados al SGSSS", "Personas", "NUM", 0, [("Salud", "Total afiliados SGSSS"), ("Salud", "Afiliados al SGSSS")]),
    Ind("PPNA", "Población pobre no atendida (PPNA)", "Personas", "NUM", 0, [("Salud", "Población pobre no atendida - PPNA")]),
    Ind("VAC_PENTA", "Cobertura vacunación pentavalente <1 año", "% ×100", "NUM", 2, [("Salud", "Cobertura vacunación pentavalente en menores de 1 año")]),
    Ind("MORT_MAT", "Razón de mortalidad materna a 42 días", "x 100.000 NV", "NUM", 2, [("Salud", "Razón de mortalidad materna a 42 días")]),
    Ind("MORT_INF", "Tasa de mortalidad infantil <1 año", "x 1.000 NV", "NUM", 2, [("Salud", "Tasa de mortalidad infantil en menores de 1 año (x cada 1.000 nacidos vivos)")]),
    Ind("MORT_GEN", "Tasa de mortalidad general", "x 1.000 hab", "NUM", 2, [("Salud", "Tasa de mortalidad (x cada 1.000 habitantes)")]),
    Ind("FECUNDIDAD", "Tasa de fecundidad (MEF)", "x 1.000 MEF", "NUM", 2, [("Salud", "Tasa de fecundidad (x cada 1.000 mujeres en edad fértil)")]),
    # --- Convivencia
    Ind("T_VIF", "Tasa de violencia intrafamiliar", "x 100.000 hab", "NUM", 2, [("Convivencia y seguridad ciudadana", "Tasa de violencia intrafamiliar por cada 100.000 habitantes")]),
    # --- Finanzas y pobreza
    Ind("PCT_APSB", "% de inversión en agua potable y saneamiento", "%", "NUM", 2, [("Finanzas públicas", "Porcentaje de inversión - Agua potable y saneamiento básico (sin incluir proyectos de vis)")]),
    Ind("SGP_APSB", "Inversión en agua potable y saneamiento", "Mill $", "NUM", 2, [("Finanzas públicas", "Agua potable"), ("Finanzas públicas", "Inversión - Agua potable y saneamiento básico (sin incluir proyectos de vis)")]),
    Ind("IPM", "Índice de Pobreza Multidimensional", "% ×100", "NUM", 2, [("Pobreza", "Índice de pobreza multidimensional - IPM"), ("Pobreza", "indice de pobreza multidimensional - IPM (Censo)")]),
    # --- Cultivos: el tonelaje va en Dato Numérico y el nombre del cultivo en Dato Cualitativo
    Ind("CULT_T1", "1er cultivo transitorio", "Toneladas", "NUM", 2, [("Economía", "Primer cultivo transitorio en términos de toneladas producidas")]),
    Ind("CULT_T2", "2º cultivo transitorio", "Toneladas", "NUM", 2, [("Economía", "Segundo cultivo transitorio en términos de toneladas producidas")]),
    Ind("CULT_T3", "3er cultivo transitorio", "Toneladas", "NUM", 2, [("Economía", "Tercer cultivo transitorio en términos de toneladas producidas")]),
    Ind("CULT_TO", "Otros cultivos transitorios", "Toneladas", "NUM", 2, [("Economía", "Toneladas producidas por otros cultivos transitorios")]),
    Ind("CULT_P1", "1er cultivo permanente", "Toneladas", "NUM", 2, [("Economía", "Primer cultivo permanente en términos de toneladas producidas")]),
    Ind("CULT_P2", "2º cultivo permanente", "Toneladas", "NUM", 2, [("Economía", "Segundo cultivo permanente en términos de toneladas producidas")]),
    Ind("CULT_P3", "3er cultivo permanente", "Toneladas", "NUM", 2, [("Economía", "Tercer cultivo permanente en términos de toneladas producidas")]),
    Ind("CULT_PO", "Otros cultivos permanentes", "Toneladas", "NUM", 2, [("Economía", "Toneladas producidas por otros cultivos permanentes")]),
    Ind("NOM_T1", "Nombre 1er cultivo transitorio", "Texto", "TXT", 0, [("Economía", "Primer cultivo transitorio en términos de toneladas producidas")]),
    Ind("NOM_T2", "Nombre 2º cultivo transitorio", "Texto", "TXT", 0, [("Economía", "Segundo cultivo transitorio en términos de toneladas producidas")]),
    Ind("NOM_T3", "Nombre 3er cultivo transitorio", "Texto", "TXT", 0, [("Economía", "Tercer cultivo transitorio en términos de toneladas producidas")]),
    Ind("NOM_P1", "Nombre 1er cultivo permanente", "Texto", "TXT", 0, [("Economía", "Primer cultivo permanente en términos de toneladas producidas")]),
    Ind("NOM_P2", "Nombre 2º cultivo permanente", "Texto", "TXT", 0, [("Economía", "Segundo cultivo permanente en términos de toneladas producidas")]),
    Ind("NOM_P3", "Nombre 3er cultivo permanente", "Texto", "TXT", 0, [("Economía", "Tercer cultivo permanente en términos de toneladas producidas")]),
]

CATALOGO_POR_ID: dict[str, Ind] = {i.id: i for i in CATALOGO}


def por_id(id_indicador: str) -> Ind:
    """La entrada del catálogo con ese id. KeyError si no existe (es un bug del código, no de los datos)."""
    return CATALOGO_POR_ID[id_indicador]


def existe(id_indicador: str) -> bool:
    return id_indicador in CATALOGO_POR_ID
