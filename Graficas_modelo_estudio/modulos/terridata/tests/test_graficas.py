"""Pruebas de las reglas duras de diseño y del armado de las 52 gráficas (§7.6 y §10)."""

from pathlib import Path

import pytest

from terridata import graficas as g
from terridata.catalogo import CATALOGO
from terridata.catalogo_graficas import GRAFICAS, SECCIONES, construir, generar
from terridata.derivados import agregar_derivados
from terridata.estilo import CLARO, OSCURO, formato_es
from terridata.lectura import leer_carpeta
from terridata.resolucion import resolver

FIXTURES = Path(__file__).parent / "fixtures"
ENTIDADES = ["CÁCOTA", "CHITAGÁ", "CUCUTILLA"]
VALORES = [3620.0, 9830.0, 8120.0]


@pytest.fixture(scope="module")
def res():
    lectura = leer_carpeta(FIXTURES)
    r = resolver(lectura.filas, CATALOGO, anio_corte=2026,
                 entidades=lectura.entidades, departamento=lectura.departamento)
    return agregar_derivados(r)


def _cerrar(fig):
    g.cerrar(fig)


# --- catálogo de gráficas


def test_son_exactamente_52():
    assert len(GRAFICAS) == 52


def test_los_numeros_van_del_1_al_52_sin_repetir():
    assert sorted(s.numero for s in GRAFICAS) == list(range(1, 53))


def test_los_ids_no_se_repiten():
    ids = [s.id for s in GRAFICAS]
    assert len(ids) == len(set(ids))


def test_el_conteo_por_seccion_es_el_del_apendice_b():
    esperado = {"poblacion": 15, "ods1": 12, "ods2": 5, "ods3": 5, "ods6": 10,
                "salud_publica": 5}
    real = {}
    for spec in GRAFICAS:
        real[spec.seccion] = real.get(spec.seccion, 0) + 1
    assert real == esperado


def test_todas_las_secciones_estan_declaradas():
    declaradas = {s for s, _ in SECCIONES}
    assert {spec.seccion for spec in GRAFICAS} <= declaradas


def test_ninguna_grafica_pasa_de_ocho_series():
    """La paleta tiene ocho slots y no se recicla (§7.1)."""
    for spec in GRAFICAS:
        assert len(spec.series) <= 8, spec.id


def test_las_series_existen_en_el_catalogo_o_son_derivados():
    from terridata.derivados import IDS as DERIVADOS
    from terridata.catalogo import CATALOGO_POR_ID

    for spec in GRAFICAS:
        for serie in spec.series:
            assert serie in CATALOGO_POR_ID or serie in DERIVADOS, f"{spec.id}: {serie}"


# --- reglas duras de diseño


def test_una_sola_serie_no_lleva_leyenda():
    fig = g.columnas(ENTIDADES, VALORES, CLARO, "Población total", "Personas", "Fuente")
    assert all(ax.get_legend() is None for ax in fig.axes)
    _cerrar(fig)


def test_dos_series_llevan_leyenda():
    fig = g.columnas_agrupadas(
        ENTIDADES,
        [("Hombres", [1.0, 2.0, 3.0]), ("Mujeres", [2.0, 3.0, 4.0])],
        CLARO, "Título", "Subtítulo", "Fuente",
    )
    assert any(ax.get_legend() is not None for ax in fig.axes)
    _cerrar(fig)


def test_la_leyenda_se_lee_en_el_orden_de_las_series():
    """matplotlib llena la leyenda por columnas; lo que importa es el orden visto."""
    series = [(f"S{i}", [float(i)] * 3) for i in range(1, 7)]
    fig = g.columnas_agrupadas(ENTIDADES, series, CLARO, "Título", "", "")
    leyenda = next(ax.get_legend() for ax in fig.axes if ax.get_legend())
    fig.canvas.draw()
    posiciones = []
    for texto in leyenda.get_texts():
        caja = texto.get_window_extent()
        posiciones.append((round(caja.y0), caja.x0, texto.get_text()))
    posiciones.sort(key=lambda p: (-p[0], p[1]))     # de arriba abajo, de izquierda a derecha
    assert [p[2] for p in posiciones] == [n for n, _ in series]
    _cerrar(fig)


@pytest.mark.parametrize("constructor", [
    lambda: g.columnas(ENTIDADES, VALORES, CLARO, "T", "S", "F"),
    lambda: g.barras_ranking(ENTIDADES, VALORES, CLARO, "T", "S", "F"),
    lambda: g.columnas_agrupadas(ENTIDADES, [("A", VALORES), ("B", VALORES)], CLARO, "T", "S", "F"),
    lambda: g.columnas_apiladas(ENTIDADES, [("A", VALORES), ("B", VALORES)], CLARO, "T", "S", "F"),
    lambda: g.torta(ENTIDADES, VALORES, CLARO, "T", "S", "F"),
])
def test_ninguna_grafica_tiene_dos_ejes_y(constructor):
    """§7.6: nunca dos ejes Y. Dos magnitudes de escala distinta son dos gráficas."""
    fig = constructor()
    con_datos = [ax for ax in fig.axes if ax.get_visible() and ax.has_data()]
    assert len(con_datos) <= 1
    _cerrar(fig)


def test_sin_marco_superior_ni_derecho():
    fig = g.columnas(ENTIDADES, VALORES, CLARO, "T", "S", "F")
    ax = fig.axes[0]
    assert not ax.spines["top"].get_visible()
    assert not ax.spines["right"].get_visible()
    _cerrar(fig)


def test_la_rejilla_es_solida_y_solo_horizontal_en_columnas():
    fig = g.columnas(ENTIDADES, VALORES, CLARO, "T", "S", "F")
    ax = fig.axes[0]
    assert any(linea.get_visible() for linea in ax.yaxis.get_gridlines())
    assert not any(linea.get_visible() for linea in ax.xaxis.get_gridlines())
    for linea in ax.yaxis.get_gridlines():
        assert linea.get_linestyle() == "-"
    _cerrar(fig)


def test_el_ranking_ordena_de_menor_a_mayor_hacia_abajo():
    fig = g.barras_ranking(ENTIDADES, VALORES, CLARO, "T", "S", "F")
    ax = fig.axes[0]
    etiquetas = [t.get_text() for t in ax.get_yticklabels()]
    assert etiquetas == ["CÁCOTA", "CUCUTILLA", "CHITAGÁ"]   # 3.620 < 8.120 < 9.830
    assert ax.get_ylim()[0] > ax.get_ylim()[1]               # eje invertido: el menor arriba
    _cerrar(fig)


def test_las_barras_no_pasan_del_grosor_maximo():
    """§7.4: máximo 24 px de diseño; con dos categorías sobra espacio y no se llena."""
    fig = g.columnas(["A", "B"], [10.0, 20.0], CLARO, "T", "S", "F")
    ax = fig.axes[0]
    lienzo = g.Lienzo(fig=fig, ax=ax, tema=CLARO,
                      ancho_ejes=g.TAMANO_BASE[0] - g.MARGEN_IZQ - g.MARGEN_DER,
                      alto_ejes=1.0)
    anchos_pulgadas = [
        (p.get_extents().width / fig.dpi) for p in ax.patches
    ]
    for ancho in anchos_pulgadas:
        assert ancho <= CLARO.grosor_barra_max + 1e-6
    _cerrar(fig)


def test_la_torta_agrupa_en_otros_con_mas_de_siete_entidades():
    nombres = [f"E{i}" for i in range(12)]
    valores = [100.0] * 6 + [1.0] * 6      # seis porciones por debajo del 2 %
    fig = g.torta(nombres, valores, CLARO, "T", "S", "F")
    leyenda = fig.legends[0]
    etiquetas = [t.get_text() for t in leyenda.get_texts()]
    assert len(etiquetas) <= 7
    assert any(e.startswith("Otros") for e in etiquetas)
    _cerrar(fig)


def test_la_torta_con_pocas_entidades_no_agrupa():
    fig = g.torta(ENTIDADES, VALORES, CLARO, "T", "S", "F")
    etiquetas = [t.get_text() for t in fig.legends[0].get_texts()]
    assert len(etiquetas) == 3
    assert not any(e.startswith("Otros") for e in etiquetas)
    _cerrar(fig)


def test_la_paleta_no_se_recicla():
    with pytest.raises(ValueError):
        CLARO.color(9)


def test_los_dos_temas_tienen_los_mismos_slots():
    assert len(CLARO.paleta) == len(OSCURO.paleta) == 8


def test_formato_colombiano_en_las_etiquetas():
    assert formato_es(1234567.5, 1) == "1.234.567,5"
    assert formato_es(1000, 0) == "1.000"


# --- armado sobre datos reales


def test_se_arman_las_52_con_el_fixture(res):
    armadas = []
    for spec, render in generar(res, CLARO):
        if render is not None:
            armadas.append(render)
            g.cerrar(render.fig)
    # El fixture no trae los ocho cultivos ni todas las series de aseo.
    assert len(armadas) >= 45


def test_cada_render_trae_su_tabla(res):
    for spec, render in generar(res, CLARO, secciones=["poblacion"]):
        if render is None:
            continue
        assert render.encabezados[0] == "Entidad"
        assert len(render.filas) == len(res.entidades)
        g.cerrar(render.fig)


def test_el_subtitulo_lleva_unidad_anio_y_fuente(res):
    spec = next(s for s in GRAFICAS if s.id == "pob_total")
    render = construir(spec, res, CLARO)
    assert "Personas" in render.subtitulo
    assert "2019" in render.subtitulo
    assert "DANE" in render.subtitulo
    g.cerrar(render.fig)


def test_el_pie_cita_a_terridata_y_el_anio(res):
    spec = next(s for s in GRAFICAS if s.id == "pob_total")
    render = construir(spec, res, CLARO)
    assert render.pie.startswith("Fuente: TerriData (DNP)")
    assert "Dato 2019" in render.pie
    g.cerrar(render.fig)


def test_la_torta_de_cultivo_nombra_el_cultivo(res):
    spec = next(s for s in GRAFICAS if s.id == "ods2_t1_torta")
    render = construir(spec, res, CLARO)
    assert "Arroz" in render.titulo      # Garzón produce más que Gigante en el fixture
    g.cerrar(render.fig)


def test_la_grafica_agrupada_de_cultivos_no_nombra_uno_solo(res):
    spec = next(s for s in GRAFICAS if s.id == "ods2_cultivos")
    render = construir(spec, res, CLARO)
    assert "—" not in render.titulo
    g.cerrar(render.fig)


def test_una_grafica_sin_datos_se_omite_sin_excepcion(res):
    from terridata.catalogo_graficas import Spec

    spec = Spec(99, "inexistente", "poblacion", "columnas", "No hay", ("NO_EXISTE",))
    assert construir(spec, res, CLARO) is None


def test_el_dashboard_se_escribe_y_es_autocontenido(res, tmp_path):
    from terridata.dashboard import escribir_dashboard, svg_en_linea

    renders = []
    for spec, render in generar(res, CLARO, secciones=["ods3"]):
        if render is None:
            continue
        render.svg = svg_en_linea(render.fig, render.archivo)
        g.cerrar(render.fig)
        renders.append(render)

    destino = escribir_dashboard(
        tmp_path / "dashboard.html",
        renders=renders, omitidas=[], res=res, tema=CLARO,
        titulo="Prueba", anio_corte=2026, filas_leidas=106, archivos=1,
    )
    texto = destino.read_text(encoding="utf-8")
    assert "<svg" in texto and "<img" not in texto        # SVG en línea, sin rutas externas
    assert "cdn" not in texto.lower()
    assert "<details>" in texto                            # la vista de tabla no es opcional
    assert "Prueba" in texto


def test_los_ids_de_los_svg_no_se_repiten_entre_tarjetas(res):
    """Dos SVG con el mismo id de clip se recortarían entre sí dentro del HTML."""
    import re

    from terridata.dashboard import svg_en_linea

    vistos = set()
    for spec, render in generar(res, CLARO, secciones=["ods6"]):
        if render is None:
            continue
        marcado = svg_en_linea(render.fig, render.archivo)
        g.cerrar(render.fig)
        ids = set(re.findall(r'id="([^"]+)"', marcado))
        assert not (ids & vistos), f"ids repetidos en {render.archivo}"
        vistos |= ids


# --- etiquetas de valor en todas las marcas


def _textos_de(fig):
    return [t.get_text() for ax in fig.axes for t in ax.texts]


def test_columnas_agrupadas_etiqueta_todas_las_barras():
    categorias = ["A", "B", "C"]
    series = [("Uno", [10.0, 20.0, 30.0]), ("Dos", [11.0, 21.0, 31.0])]
    fig = g.columnas_agrupadas(categorias, series, CLARO, "T", "S", "F", decimales=0)
    textos = _textos_de(fig)
    for _, valores in series:
        for v in valores:
            assert formato_es(v, 0) in textos
    _cerrar(fig)


def test_las_etiquetas_se_giran_cuando_no_caben_acostadas():
    """Con muchas series por grupo, la cifra va vertical en vez de encimarse."""
    categorias = [f"Municipio {i}" for i in range(8)]
    series = [(f"S{s}", [123456.0 + s] * 8) for s in range(4)]
    fig = g.columnas_agrupadas(categorias, series, CLARO, "T", "S", "F", decimales=0)
    rotaciones = {t.get_rotation() for ax in fig.axes for t in ax.texts}
    assert 90 in rotaciones
    _cerrar(fig)


def test_una_sola_serie_deja_las_etiquetas_acostadas():
    fig = g.columnas(["A", "B", "C"], [1000.0, 2000.0, 3000.0], CLARO, "T", "S", "F")
    rotaciones = {t.get_rotation() for ax in fig.axes for t in ax.texts}
    assert rotaciones == {0.0}
    _cerrar(fig)


def test_la_etiqueta_cabe_dentro_del_eje():
    """El eje reserva el aire de la etiqueta: nunca queda por fuera del dibujo."""
    fig = g.columnas(["A", "B"], [100.0, 5000.0], CLARO, "T", "S", "F")
    ax = fig.axes[0]
    fig.canvas.draw()
    limite = ax.get_window_extent()
    for texto in ax.texts:
        caja = texto.get_window_extent()
        assert caja.y1 <= limite.y1 + 1
    _cerrar(fig)


def test_las_apiladas_etiquetan_el_total_de_cada_barra():
    fig = g.columnas_apiladas(
        ["A", "B"], [("Uno", [10.0, 20.0]), ("Dos", [5.0, 10.0])],
        CLARO, "T", "S", "F", decimales=0)
    textos = _textos_de(fig)
    assert "15" in textos and "30" in textos
    _cerrar(fig)


def test_el_panel_etiqueta_todas_sus_barras():
    fig = g.panel(
        [("Uno", ["A", "B"], [1.0, 2.0], 1), ("Dos", ["A", "B"], [3.0, 4.0], 1)],
        CLARO, "T", "S", "F", filas=1, columnas_grid=2)
    textos = _textos_de(fig)
    for v in ("1,0", "2,0", "3,0", "4,0"):
        assert v in textos
    _cerrar(fig)


def test_la_piramide_etiqueta_los_dos_lados():
    fig = g.piramide(["0-4", "5-9"], [10.0, 20.0], [12.0, 18.0], CLARO, "T")
    textos = _textos_de(fig)
    for v in ("10", "20", "12", "18"):
        assert v in textos
    _cerrar(fig)


def test_barras_agrupadas_h_etiqueta_todas():
    fig = g.barras_agrupadas_h(
        ["A", "B"], [("Uno", [1000.0, 2000.0]), ("Dos", [3000.0, 4000.0])],
        CLARO, "T", decimales=0)
    textos = _textos_de(fig)
    for v in ("1.000", "2.000", "3.000", "4.000"):
        assert v in textos
    _cerrar(fig)
