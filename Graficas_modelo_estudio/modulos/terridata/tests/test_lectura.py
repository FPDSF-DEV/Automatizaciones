"""Pruebas del parseo y la consolidación (§10 del PLAN)."""

from pathlib import Path

import pytest

from terridata.lectura import (
    a_numero,
    descubrir,
    leer_archivo,
    leer_carpeta,
    parsear_linea,
)

FIXTURES = Path(__file__).parent / "fixtures"
MINI = FIXTURES / "mini_terridata.txt"


@pytest.mark.parametrize(
    "texto,esperado",
    [
        ("22.395,00", 22395.0),
        ("-1.698,39", -1698.39),
        ("503,35", 503.35),
        ("", None),
        ("0,00", 0.0),
        ("1.344.384,50", 1344384.5),
        ("   ", None),
        ("no es un numero", None),
    ],
)
def test_a_numero(texto, esperado):
    assert a_numero(texto) == esperado


def test_a_numero_no_usa_float_directo():
    """`float("22.395,00")` explota; `float("22.395")` daría 22.395 en vez de 22395."""
    assert a_numero("22.395") == 22395.0


def test_parsear_linea_completa():
    linea = (
        "41|Huila|41306|Gigante|Descripción general|Descripción general|"
        "Población total|22.395,00||2000|12|DANE|Personas"
    )
    f = parsear_linea(linea)
    assert f is not None
    assert f.departamento == "Huila"
    assert f.entidad == "Gigante"
    assert f.dimension == "Descripción general"
    assert f.indicador == "Población total"
    assert f.valor == 22395.0
    assert f.texto is None
    assert f.anio == 2000
    assert f.mes == 12
    assert f.unidad == "Personas"


def test_parsear_linea_con_numero_y_texto():
    """Los cultivos traen tonelaje en Dato Numérico y el nombre en Dato Cualitativo."""
    linea = (
        "41|Huila|41306|Gigante|Economía|Principales cultivos transitorios según producción|"
        "Primer cultivo transitorio en términos de toneladas producidas|3.606,00|Maíz|2016|12|"
        "Evaluación Agropecuaria Municipal, MinAgricultura|Número"
    )
    f = parsear_linea(linea)
    assert f is not None
    assert f.valor == 3606.0
    assert f.texto == "Maíz"


def test_parsear_linea_con_menos_campos_devuelve_none():
    assert parsear_linea("41|Huila|41306|Gigante|Salud") is None


def test_mes_puede_ser_cero():
    linea = "41|Huila|41306|Gigante|Salud|x|Indicador x|1,00||2020|0|Fuente|Unidad"
    f = parsear_linea(linea)
    assert f is not None and f.mes == 0


def test_leer_archivo_salta_encabezado():
    filas, vistas, descartadas = leer_archivo(MINI)
    assert descartadas == 0
    assert vistas == len(filas)
    assert all(f.indicador != "Indicador" for f in filas)


def test_leer_carpeta_entidades_en_orden_de_aparicion():
    r = leer_carpeta(FIXTURES)
    assert r.entidades == ["Gigante", "Garzón"]
    assert r.departamento == "Huila"


def test_orden_entidades_por_nombre():
    r = leer_carpeta(FIXTURES, orden_entidades="nombre")
    assert r.entidades == ["Garzón", "Gigante"]


def test_archivo_corrupto_avisa_y_sigue(caplog):
    r = leer_carpeta(FIXTURES / "corrupto")
    assert len(r.filas) == 2
    assert r.lineas_descartadas == 2


def test_carpeta_vacia(tmp_path):
    r = leer_carpeta(tmp_path)
    assert r.filas == [] and r.entidades == [] and r.archivos == []


def test_carpeta_inexistente():
    assert descubrir("no/existe/por/aqui") == []


def test_deduplica_el_mismo_archivo_dos_veces(tmp_path):
    """Dos archivos con la misma entidad no duplican filas idénticas."""
    (tmp_path / "a.txt").write_text(MINI.read_text(encoding="utf-8"), encoding="utf-8")
    (tmp_path / "b.txt").write_text(MINI.read_text(encoding="utf-8"), encoding="utf-8")
    r = leer_carpeta(tmp_path)
    solo_uno = leer_carpeta(FIXTURES)
    assert len(r.filas) == len(solo_uno.filas)
    assert r.duplicados == len(solo_uno.filas)


def test_bom_no_rompe_el_encabezado(tmp_path):
    destino = tmp_path / "con_bom.txt"
    destino.write_text(MINI.read_text(encoding="utf-8"), encoding="utf-8-sig")
    filas, _, descartadas = leer_archivo(destino)
    assert descartadas == 0
    assert filas[0].cod_departamento == "41"
