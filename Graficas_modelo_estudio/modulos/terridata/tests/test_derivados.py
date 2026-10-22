"""Pruebas de los cálculos derivados (§6 y §10 del PLAN)."""

from pathlib import Path

import pytest

from terridata.derivados import agregar_derivados, division, resta, suma
from terridata.lectura import leer_carpeta
from terridata.resolucion import resolver

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def res():
    lectura = leer_carpeta(FIXTURES)
    r = resolver(
        lectura.filas,
        anio_corte=2026,
        entidades=lectura.entidades,
        departamento=lectura.departamento,
    )
    return agregar_derivados(r)


# --- primitivas


def test_division_normal():
    assert division(25.0, 100.0) == 25.0


@pytest.mark.parametrize("a,b", [(None, 100.0), (25.0, None), (None, None)])
def test_division_con_none(a, b):
    assert division(a, b) is None


def test_division_por_cero_no_explota():
    assert division(25.0, 0.0) is None


def test_resta_con_none():
    assert resta(None, 5.0) is None and resta(5.0, None) is None
    assert resta(10.0, 4.0) == 6.0


def test_suma_con_un_none_es_none():
    """§6: cualquier operando None produce None, nunca cero."""
    assert suma([1.0, None, 3.0]) is None
    assert suma([1.0, 2.0, 3.0]) == 6.0
    assert suma([]) is None


# --- derivados sobre el fixture


def test_pct_del_total_suma_cien(res):
    total = sum(res.numero("PCT_DEL_TOTAL", e) for e in res.entidades)
    assert total == pytest.approx(100.0)


def test_pct_del_total_valor_conocido(res):
    # 35.498 / (35.498 + 98.550) = 26,48 %
    assert res.numero("PCT_DEL_TOTAL", "Gigante") == pytest.approx(26.4814, abs=1e-3)


def test_pct_rural_y_urbana_suman_cien(res):
    for e in res.entidades:
        assert res.numero("PCT_RURAL", e) + res.numero("PCT_URBANA", e) == pytest.approx(100.0)


def test_pct_rural_valor_conocido(res):
    # 17.505 / 35.498 = 49,31 %
    assert res.numero("PCT_RURAL", "Gigante") == pytest.approx(49.3126, abs=1e-3)


def test_total_afiliados_suma_los_tres_regimenes(res):
    # 25.110 + 5.288 + 402 = 30.800
    assert res.numero("TOTAL_AFILIADOS", "Gigante") == pytest.approx(30800.0)


def test_total_afiliados_prefiere_el_total_reportado():
    """Si AFIL_SGSSS existe, manda sobre la suma de regímenes."""
    from terridata.catalogo import Ind
    from terridata.lectura import Fila

    def f(indicador, valor):
        return Fila("41", "Huila", "1", "E", "Salud", "x", indicador, valor, None,
                    2021, 12, "F", "Personas")

    catalogo = [
        Ind("AFIL_SGSSS", "Afiliados al SGSSS", "Personas", "NUM", 0, [("Salud", "Total afiliados SGSSS")]),
        Ind("AFIL_SUBS", "Subsidiado", "Personas", "NUM", 0, [("Salud", "Afiliados régimen subsidiado")]),
        Ind("AFIL_CONTRIB", "Contributivo", "Personas", "NUM", 0, [("Salud", "Afiliados régimen contributivo")]),
        Ind("AFIL_ESP", "Especiales", "Personas", "NUM", 0, [("Salud", "Afiliados régimen de excepción y especiales")]),
        Ind("POB_TOTAL", "Población", "Personas", "NUM", 0, [("Salud", "Población")]),
    ]
    filas = [
        f("Total afiliados SGSSS", 1000.0),
        f("Afiliados régimen subsidiado", 100.0),
        f("Afiliados régimen contributivo", 100.0),
        f("Afiliados régimen de excepción y especiales", 100.0),
        f("Población", 2000.0),
    ]
    r = agregar_derivados(resolver(filas, catalogo, anio_corte=2026))
    assert r.numero("TOTAL_AFILIADOS", "E") == 1000.0
    assert r.numero("COBERTURA_SGSSS", "E") == pytest.approx(50.0)


def test_cobertura_sgsss_topada_en_cien():
    from terridata.catalogo import Ind
    from terridata.lectura import Fila

    catalogo = [
        Ind("AFIL_SGSSS", "SGSSS", "Personas", "NUM", 0, [("Salud", "Total afiliados SGSSS")]),
        Ind("POB_TOTAL", "Población", "Personas", "NUM", 0, [("Salud", "Población")]),
    ]
    filas = [
        Fila("41", "H", "1", "E", "Salud", "x", "Total afiliados SGSSS", 3000.0, None, 2021, 12, "F", "Personas"),
        Fila("41", "H", "1", "E", "Salud", "x", "Población", 2000.0, None, 2021, 12, "F", "Personas"),
    ]
    r = agregar_derivados(resolver(filas, catalogo, anio_corte=2026))
    assert r.numero("COBERTURA_SGSSS", "E") == 100.0
    assert r.numero("SIN_AFILIAR_PCT", "E") == 0.0


def test_sin_afiliar_es_el_complemento(res):
    for e in res.entidades:
        c = res.numero("COBERTURA_SGSSS", e)
        s = res.numero("SIN_AFILIAR_PCT", e)
        if c is not None:
            assert c + s == pytest.approx(100.0)


def test_variacion_censo_rec_en_puntos_porcentuales(res):
    # 78,45 − 86,90 = −8,45
    assert res.numero("VAR_ACU_CENSO_REC", "Gigante") == pytest.approx(-8.45)


def test_brecha_urbano_rural(res):
    # 97,20 − 59,10 = 38,10
    assert res.numero("BRECHA_ACU_URB_RUR", "Gigante") == pytest.approx(38.10)


def test_derivado_con_operando_faltante_es_none():
    """Sin POB_RUR no hay PCT_RURAL, y no se cae."""
    from terridata.catalogo import Ind
    from terridata.lectura import Fila

    catalogo = [
        Ind("POB_TOTAL", "Población", "Personas", "NUM", 0, [("Dim", "Población total")]),
    ]
    filas = [Fila("41", "H", "1", "E", "Dim", "x", "Población total", 100.0, None, 2021, 12, "F", "Personas")]
    r = agregar_derivados(resolver(filas, catalogo, anio_corte=2026))
    assert r.numero("PCT_RURAL", "E") is None
    assert r.numero("TOTAL_AFILIADOS", "E") is None
    assert r.numero("PCT_DEL_TOTAL", "E") == pytest.approx(100.0)


def test_produccion_agricola_es_none_si_falta_un_cultivo(res):
    """El fixture no trae los ocho cultivos, así que el total no se inventa."""
    assert res.numero("PROD_AGRICOLA_TOTAL", "Gigante") is None


def test_los_derivados_quedan_registrados_con_etiqueta_y_unidad(res):
    from terridata.derivados import IDS

    for i in IDS:
        assert res.etiqueta(i) and res.etiqueta(i) != i
        assert i in res.unidades
