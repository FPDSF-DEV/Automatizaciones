"""Pruebas de alias, año de corte y agregación de duplicados (§10 del PLAN)."""

from pathlib import Path

import pytest

from terridata.catalogo import Ind
from terridata.lectura import Fila, leer_carpeta
from terridata.resolucion import resolver, tabla_texto

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def lectura():
    return leer_carpeta(FIXTURES)


@pytest.fixture
def res(lectura):
    return resolver(
        lectura.filas,
        anio_corte=2026,
        entidades=lectura.entidades,
        departamento=lectura.departamento,
    )


def fila(dimension, indicador, valor=None, texto=None, anio=2021, entidad="Gigante",
         subcategoria="x"):
    return Fila(
        cod_departamento="41", departamento="Huila", cod_entidad="41306", entidad=entidad,
        dimension=dimension, subcategoria=subcategoria, indicador=indicador,
        valor=valor, texto=texto, anio=anio, mes=12, fuente="Fuente", unidad="Unidad",
    )


# --- alias


def test_usa_el_tercer_alias_si_es_el_unico_presente():
    ind = Ind("X", "Indicador X", "%", "NUM", 2, [
        ("Dim", "Nombre viejo"),
        ("Dim", "Nombre intermedio"),
        ("Dim", "Nombre nuevo"),
    ])
    filas = [fila("Dim", "Nombre nuevo", valor=12.5)]
    r = resolver(filas, [ind], anio_corte=2026)
    assert r.valores["X"]["Gigante"] == 12.5
    assert r.alias_usado["X"] == ("Dim", "Nombre nuevo")
    assert r.faltantes == []


def test_prefiere_el_primer_alias_cuando_estan_los_dos():
    ind = Ind("X", "Indicador X", "%", "NUM", 2, [
        ("Dim", "Preferido"),
        ("Dim", "Respaldo"),
    ])
    filas = [fila("Dim", "Respaldo", valor=1.0), fila("Dim", "Preferido", valor=2.0)]
    r = resolver(filas, [ind], anio_corte=2026)
    assert r.valores["X"]["Gigante"] == 2.0


def test_sin_ningun_alias_queda_no_disponible_sin_excepcion():
    ind = Ind("X", "Indicador X", "%", "NUM", 2, [("Dim", "No está")])
    r = resolver([fila("Dim", "Otra cosa", valor=1.0)], [ind], anio_corte=2026)
    assert r.valores["X"]["Gigante"] is None
    assert "X" in r.faltantes
    assert r.disponible("X") is False


def test_banda_ancha_resuelve_por_el_nombre_nuevo(res):
    """El fixture solo trae 'Penetración de acceso fijo a Internet' (alias 3)."""
    assert res.alias_usado["BANDA"][1] == "Penetración de acceso fijo a Internet"
    assert res.valores["BANDA"]["Gigante"] == 8.40


def test_ipm_resuelve_el_nombre_sin_tilde(res):
    assert res.alias_usado["IPM"][1] == "indice de pobreza multidimensional - IPM (Censo)"
    assert res.valores["IPM"]["Garzón"] == 24.50


# --- año de corte


def test_anio_de_corte_ignora_proyecciones():
    """Datos 2019, 2021 y 2042 con corte 2026 devuelven 2021."""
    ind = Ind("X", "Indicador X", "Personas", "NUM", 0, [("Dim", "Ind")])
    filas = [
        fila("Dim", "Ind", valor=100.0, anio=2019),
        fila("Dim", "Ind", valor=200.0, anio=2021),
        fila("Dim", "Ind", valor=900.0, anio=2042),
    ]
    r = resolver(filas, [ind], anio_corte=2026)
    assert r.anios["X"] == 2021
    assert r.valores["X"]["Gigante"] == 200.0


def test_corte_mas_bajo_cambia_el_anio_usado():
    ind = Ind("X", "Indicador X", "Personas", "NUM", 0, [("Dim", "Ind")])
    filas = [
        fila("Dim", "Ind", valor=100.0, anio=2019),
        fila("Dim", "Ind", valor=200.0, anio=2021),
    ]
    r = resolver(filas, [ind], anio_corte=2020)
    assert r.anios["X"] == 2019 and r.valores["X"]["Gigante"] == 100.0


def test_sin_datos_dentro_del_corte_queda_faltante():
    ind = Ind("X", "Indicador X", "Personas", "NUM", 0, [("Dim", "Ind")])
    r = resolver([fila("Dim", "Ind", valor=1.0, anio=2042)], [ind], anio_corte=2026)
    assert "X" in r.faltantes and r.valores["X"]["Gigante"] is None


def test_poblacion_prefiere_la_serie_del_censo(res):
    """§4.4: las dos series no coinciden y manda 'Censo 2005 y proyecciones DANE'."""
    assert res.alias_usado["POB_TOTAL"][0] == "Censo 2005 y proyecciones DANE"
    assert res.valores["POB_TOTAL"]["Gigante"] == 35498.0
    assert res.anios["POB_TOTAL"] == 2019


def test_poblacion_coherente_dentro_de_la_serie_elegida(res):
    """17.993 + 17.505 = 35.498 y 19.369 + 16.129 = 35.498."""
    g = "Gigante"
    assert res.numero("POB_URB", g) + res.numero("POB_RUR", g) == res.numero("POB_TOTAL", g)
    assert res.numero("POB_H", g) + res.numero("POB_M", g) == res.numero("POB_TOTAL", g)


# --- duplicados y agregación


def test_filas_duplicadas_promedian_no_suman():
    """Déficit cualitativo aparece dos veces con 46,17 en subcategorías distintas."""
    ind = Ind("X", "Indicador X", "%", "NUM", 2, [("Dim", "Ind")])
    filas = [
        fila("Dim", "Ind", valor=46.17, subcategoria="Déficit"),
        fila("Dim", "Ind", valor=46.17, subcategoria="Déficit de vivienda"),
    ]
    r = resolver(filas, [ind], anio_corte=2026)
    assert r.valores["X"]["Gigante"] == pytest.approx(46.17)


def test_deficit_cualitativo_del_fixture_no_se_duplica(res):
    assert res.valores["DEF_CUAL"]["Gigante"] == pytest.approx(46.17)


def test_subcategoria_no_hace_parte_de_la_clave(res):
    """Las dos filas de DEF_CUAL difieren solo en Subcategoría y son el mismo dato."""
    assert res.alias_usado["DEF_CUAL"][1] == "Déficit cualitativo de vivienda (Censo)"


# --- indicadores de texto


def test_indicadores_de_texto_salen_de_dato_cualitativo(res):
    assert res.valores["REGION"]["Gigante"] == "Central"
    assert res.valores["COD_DANE"]["Garzón"] == "41298"
    assert res.anios["REGION"] is None


def test_cultivo_conserva_numero_y_nombre(res):
    assert res.valores["CULT_T1"]["Gigante"] == 3606.0
    assert res.valores["NOM_T1"]["Gigante"] == "Maíz"
    assert res.valores["NOM_P1"]["Garzón"] == "Café"


# --- robustez


def test_una_entidad_sin_datos_no_rompe_el_resto(res):
    """Garzón no tiene vacunación pentavalente en el fixture."""
    assert res.valores["VAC_PENTA"]["Gigante"] == 92.30
    assert res.valores["VAC_PENTA"]["Garzón"] is None
    assert res.disponible("VAC_PENTA") is True
    assert "VAC_PENTA" not in res.faltantes


def test_todas_las_entidades_aparecen_en_todos_los_indicadores(res):
    for id_indicador, por_entidad in res.valores.items():
        assert list(por_entidad) == res.entidades, id_indicador


def test_serie_temporal_ordenada(res):
    serie = res.serie_temporal("PCT_APSB", "Gigante")
    assert list(serie) == [2013, 2014, 2015, 2016, 2017]
    assert serie[2017] == 12.90
    assert res.ultimo_anio_con_dato("PCT_APSB") == 2017


def test_serie_temporal_de_indicador_inexistente_es_vacia(res):
    assert res.serie_temporal("NO_EXISTE", "Gigante") == {}


def test_tabla_texto_incluye_entidades_y_guion_para_faltantes(res):
    salida = tabla_texto(res, ["POB_TOTAL", "VAC_PENTA"])
    assert "Gigante" in salida and "Garzón" in salida
    assert "35.498" in salida
    assert "—" in salida


# --- verificación numérica contra la fuente (criterio 8)


@pytest.mark.parametrize(
    "id_indicador,entidad,esperado",
    [
        ("POB_TOTAL", "Gigante", 35498.0),
        ("DEF_CUAL", "Gigante", 46.17),
        ("AFIL_SUBS", "Garzón", 58920.0),
    ],
)
def test_valores_conocidos_del_fixture(res, id_indicador, entidad, esperado):
    assert res.numero(id_indicador, entidad) == pytest.approx(esperado)
