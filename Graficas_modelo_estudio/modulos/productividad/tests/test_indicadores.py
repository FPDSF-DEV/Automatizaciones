"""Verificación contra valores calculados a mano desde los reportes crudos de
DATA/SIHO/ (ESE HOSPITAL SAN ANTONIO, 2020-2025).

Ejecutar con:  python -m pytest -q     (o)   python tests/test_indicadores.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd

from prodlib.carga import _anio_de_archivo, cargar, normalizar
from prodlib.indicadores import INDICADORES

ANIOS = [2020, 2021, 2022, 2023, 2024, 2025]
TOLERANCIA = 1e-9

# (indicador, año) -> valor esperado, con la cuenta hecha a mano
ESPERADO: dict[tuple[str, int], float] = {
    # Consultas medicina general electivas 16244 / (6 consultorios x 260 días)
    ("consulta_externa", 2020): 16244 / (6 * 260),
    # Consultas medicina general urgentes 11005 / (2 consultorios x 365 días)
    ("urgencias", 2025): 11005 / (2 * 365),
    # Partos vaginales 42 / 1 mesa
    ("partos", 2020): 42.0,
    # Sesiones de odontología 18731 / (5 unidades x 260 días)
    ("odontologia", 2025): 18731 / (5 * 260),
    # Producción total 277952 / (3 cargos operativos de planta + 556 contratos OPS)
    ("talento_contratos", 2025): 277952 / (3 + 556),
    # Producción total 77477 / (9 cargos x 12 meses + 418.05 meses OPS)
    ("talento_meses", 2020): 77477 / (9 * 12 + 418.05),
    # Producción total 77477 / ((13 + 9) cargos x 12 meses + 658.33 meses de las 621 OPS)
    ("talento_global", 2020): 77477 / (22 * 12 + 658.33),
}


def test_valores_calculados_a_mano():
    datos = cargar()
    por_clave = {ind.clave: ind for ind in INDICADORES}
    for (clave, anio), esperado in ESPERADO.items():
        ind = por_clave[clave]
        obtenido = ind.calcular(datos).loc[anio, ind.indicador]
        assert abs(obtenido - esperado) < TOLERANCIA, (
            f"{clave} {anio}: calculado {obtenido!r}, esperado {esperado!r}"
        )


def test_consolidacion_de_nomina_y_ops():
    datos = cargar()
    assert datos["nomina"].loc["OPERATIVO"].tolist() == [9, 9, 8, 6, 6, 3]
    assert datos["ops"].loc["OPERATIVO", 2020] == 409
    assert abs(datos["ops"].loc["MESES CONTRATADOS OPERATIVOS", 2020] - 418.05) < 1e-6
    assert datos["nomina"].loc["TOTAL"].tolist() == [22, 20, 19, 16, 16, 12]
    assert datos["ops"].loc["CONTRATOS TOTAL"].tolist() == [621, 510, 803, 961, 718, 807]
    assert abs(datos["ops"].loc["MESES CONTRATADOS TOTAL", 2025] - 1187.94) < 1e-6


def test_los_anios_se_detectan_solos():
    datos = cargar()
    for ind in INDICADORES:
        assert ind.anios(datos) == ANIOS


def test_anio_del_reporte_ops():
    vacio = pd.DataFrame()
    nombre = Path("Reporte_Contratacion_Externa_desde_2020_2025_octubre-dic.csv")
    assert _anio_de_archivo(nombre, vacio) == 2025


def test_normalizar_ignora_tildes_y_espacios():
    assert normalizar("  Número de  unidades de ODONTOLOGÍA ") == "numero de unidades de odontologia"


if __name__ == "__main__":
    test_valores_calculados_a_mano()
    test_consolidacion_de_nomina_y_ops()
    test_los_anios_se_detectan_solos()
    test_anio_del_reporte_ops()
    test_normalizar_ignora_tildes_y_espacios()
    print("Todas las verificaciones pasaron.")
