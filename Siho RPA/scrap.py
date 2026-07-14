"""
RPA de descarga SIHO (prestadores.minsalud.gov.co/siho).

Mejoras respecto a la version original:
  * UN login por BLOQUE de periodo en lugar de un login por cada item.
    El sitio guarda el "periodo actual" (anio + periodicidad + sub-periodo)
    en la sesion: el PRIMER formulario abierto tras el login pide el anio
    (#ddano); los siguientes del mismo periodo abren directo en Excel.
      - Anuales:      1 login por anio            -> descarga todos los items.
      - Semestrales:  1 login por (anio, semestre)-> descarga todos los items.
      - Trimestrales: 1 login por (anio, trimestre)-> descarga todos los items.
      - Consultas:    1 login para todo el bloque.
    Esto reduce ~90% los logins/recargas respecto al original (que re-logueaba
    en CADA item) manteniendo la robustez.
  * Sincronizacion por eventos (wait_for_selector / expect_download) en vez de
    esperas ciegas grandes; pausas aleatorias pequenas para no alertar al WAF.
  * Reanudable: si el archivo destino ya existe, se omite la descarga.
  * Manejo de errores por item: un fallo no aborta el bloque.

IMPORTANTE: el sitio esta detras de un WAF que BLOQUEA navegadores headless
("Web Page Blocked!"). Debe ejecutarse con headless=False (ventana visible).
"""

from __future__ import annotations

import argparse
import os
import random
import re
import time
import unicodedata

from playwright.sync_api import sync_playwright, Error as PlaywrightError

# --------------------------------------------------------------------------- #
# Configuracion
# --------------------------------------------------------------------------- #
INIT_URL = "https://prestadores.minsalud.gov.co/siho/"
# Credenciales: se toman de --user/--password, o de las variables de entorno
# SIHO_USER / SIHO_PASSWORD (es lo que usa la app web app.py).
USER = os.environ.get("SIHO_USER", "")
PASSWORD = os.environ.get("SIHO_PASSWORD", "")

# Nombre de la entidad (detectado tras el login en #lblIngresar). Todas las
# descargas se guardan bajo descargas/<ENTIDAD>/... para separar las
# consultas de cada entidad.
ENTITY_NAME = None
ENTITY_SLUG = None
# Por defecto: desde 2020 hasta el anio actual (se actualiza solo cada anio).
YEARS = list(range(2020, time.localtime().tm_year + 1))
DOWNLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "descargas")

# (etiqueta, slug_carpeta, value_del_#ddmes)
QUARTERS = [
    ("ENE-MAR", "enero-mar", "3"),
    ("ABR-JUN", "abril-jun", "6"),
    ("JUL-SEP", "julio-sep", "9"),
    ("OCT-DIC", "octubre-dic", "12"),
]
SEMESTERS = [
    ("ENE-JUN", "enero-jun", "18"),
    ("JUL-DIC", "julio-dic", "24"),
]

# Selectores comunes de los formularios de captura
SEL_DDANO = "#ddano"
SEL_DDMES = "#ddmes"
SEL_ACEPTAR = "#ibAceptar"
SEL_EXCEL = "#_ctl0_ContentPlaceHolder1_ibExcel"
SEL_GRID = "#_ctl0_ContentPlaceHolder1_dgList"

# Items cuya exportacion a Excel esta rota en el servidor (el boton hace un
# postback que devuelve la misma pagina, sin adjunto). Para estos se extrae
# directamente la grilla HTML y se guarda como .xls (tabla HTML), el mismo
# formato que usan los demas exports del sitio, por lo que
# convert_xls_to_csv.py los procesa sin cambios (fallback pd.read_html).
HTML_GRID_ITEMS = {"Infraestructura"}

# Items por seccion. Cada item define como localizar su enlace dentro del
# div hijo del menu. Se usa "title" cuando es unico y "text" cuando el titulo
# esta duplicado dentro del mismo submenu (caso Contratacion Externa).
ANUAL_ITEMS = [
    ("Recursos Humanos", "Recursos Humanos"),
    ("Ingresos", "Ingresos"),
    ("Gastos", "Gastos"),
    ("Facturacion", "Facturación"),
    ("Cartera por Deudor", "Cartera por Deudor"),
    ("Pasivos", "Información de Pasivos"),
    ("Mecanismos de Pago", "Mecanismos de pago aplicables a la compra de S.S"),
    ("Balance General", "Balance General"),
    ("Estado de Actividad", "Estado de Actividad Económica Financiera y Social"),
    ("Produccion", "Producción"),
    ("Capacidad Instalada", "Capacidad Instalada"),
    ("Pasivo Prestacional", "Pasivo Prestacional"),
    ("Infraestructura", "Formularios de infraestructura"),
    ("Procesos Judiciales", "Procesos Judiciales de la IPS"),
    # "Datos Generales" excluido: es un formulario de captura sin reporte.
]

SEMESTRAL_ITEMS = [
    ("Calidad", "Calidad"),
]

# Trimestrales: se identifican por TITULO salvo las dos "Contratacion Externa"
# que comparten titulo -> se distinguen por texto. ("kind", valor).
TRIMESTRAL_ITEMS = [
    # "Datos Generales" excluido: es un formulario de captura sin reporte.
    ("Facturacion", "title", "Facturación Trimestral"),
    ("Cartera por Deudor", "title", "Cartera por Deudor"),
    ("Pasivos", "title", "Cuentas por pagar"),
    ("Balance General", "title", "Balance General"),
    ("Estados Actividades", "title", "Estados Actividades"),
    ("Produccion", "title", "Producción"),
    ("Ejecucion Presupuestal", "title", "Ejecución Presupuestal de Ingresos y Gastos"),
    ("Contratacion Externa desde 2020", "text", "Contratación desde 2020"),
    ("Contratacion Externa hasta 2019", "text", "Contratación hasta 2019"),
    ("Calidad", "title", "Indicadares de calidad"),
    ("Procesos Judiciales", "title", "Procesos Judiciales del Trimestre"),
    ("Recursos Humanos", "title", "Recursos humanos"),
    ("Infraestructura", "title", "Formularios Infraestructura"),
]

# Menu: carpeta (a[name]) y div hijo por seccion.
MENU = {
    "anual": {"folder": "item0", "child": "#item0Child"},
    "semestral": {"folder": "item15", "child": "#item15Child"},
    "trimestral": {"folder": "item16", "child": "#item16Child"},
    "consulta": {"folder": "item42", "child": "#item42Child"},
}


# --------------------------------------------------------------------------- #
# Utilidades
# --------------------------------------------------------------------------- #
def safe_name(value) -> str:
    normalized = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode("ascii")
    normalized = re.sub(r"[^A-Za-z0-9_-]+", "_", normalized).strip("_")
    return normalized or "sin_nombre"


def entity_folder() -> str:
    """Carpeta raiz de la entidad actual dentro de descargas/."""
    return ENTITY_SLUG or f"Entidad_{safe_name(USER)}"


def build_download_folder(category, item_name, year, period=None) -> str:
    parts = [DOWNLOAD_FOLDER, entity_folder(), safe_name(category), str(year)]
    if period:
        parts.append(safe_name(period))
    parts.append(safe_name(item_name))
    folder = os.path.join(*parts)
    os.makedirs(folder, exist_ok=True)
    return folder


def human_pause(page, a=0.3, b=0.8):
    """Pausa aleatoria corta para no parecer un bot demasiado regular."""
    page.wait_for_timeout(int(random.uniform(a, b) * 1000))


def item_locator(frame, child, kind, value):
    """Devuelve el Locator del enlace del item dentro del submenu."""
    if kind == "title":
        return frame.locator(f'{child} a[title="{value}"]')
    # kind == "text": coincidencia exacta del texto del enlace
    return frame.locator(f"{child} a").filter(has_text=re.compile(rf"^\s*{re.escape(value)}\s*$"))


# --------------------------------------------------------------------------- #
# Navegacion / sesion
# --------------------------------------------------------------------------- #
def get_frame(page):
    return page.frame(name="areawork")


def login(page):
    """Carga la pagina inicial y realiza el login. Devuelve el frame areawork."""
    page.goto(INIT_URL)
    human_pause(page, 1.0, 1.8)
    frame = get_frame(page)
    if not frame:
        raise RuntimeError("No se encontro el frame 'areawork' (posible bloqueo del WAF).")
    frame.fill("#tbid_usuario", USER)
    frame.fill("#tbcontrasena", PASSWORD)
    frame.click("#btningresar")
    page.wait_for_load_state("domcontentloaded", timeout=60000)
    human_pause(page, 1.2, 2.0)
    frame = get_frame(page)
    if not frame:
        raise RuntimeError("No se encontro el frame 'areawork' despues del login.")
    _detect_entity(frame)
    return frame


def _detect_entity(frame):
    """Lee el nombre de la entidad (#lblIngresar) tras el login y fija la
    carpeta de descargas de esta entidad. Solo se detecta una vez."""
    global ENTITY_NAME, ENTITY_SLUG
    if ENTITY_SLUG:
        return
    name = ""
    try:
        loc = frame.locator("#lblIngresar")
        if loc.count():
            name = loc.first.inner_text(timeout=10000).strip()
    except PlaywrightError:
        pass
    ENTITY_NAME = name or f"Entidad {USER}"
    ENTITY_SLUG = safe_name(ENTITY_NAME)
    print(f"Entidad: {ENTITY_NAME} -> carpeta descargas/{ENTITY_SLUG}")


def ensure_expanded(frame, folder, child):
    """Expande el submenu de la seccion solo si aun no esta visible (evita el
    toggle que lo volveria a cerrar)."""
    if not frame.locator(child).is_visible():
        loc = frame.locator(f'a[name="{folder}"]')
        loc.scroll_into_view_if_needed(timeout=15000)
        loc.click()
        frame.wait_for_selector(child, state="visible", timeout=15000)


def open_item_popup(page, frame, folder, child, locator):
    """Expande el submenu, hace clic en el item y devuelve la pestana popup."""
    ensure_expanded(frame, folder, child)
    with page.expect_popup() as popup_info:
        locator.click()
    reg = popup_info.value
    reg.wait_for_load_state("networkidle", timeout=60000)
    return reg


def configure_period(reg, year, mes_value=None):
    """Si el popup muestra la pantalla de configuracion (#ddano), fija el anio
    (y el sub-periodo) y acepta. Solo ocurre en el PRIMER formulario del bloque."""
    if reg.locator(SEL_DDANO).count() == 0:
        return  # el periodo ya estaba fijado; el form abrio directo en los datos
    reg.select_option(SEL_DDANO, str(year))
    if mes_value is not None:
        reg.select_option(SEL_DDMES, str(mes_value))
    reg.click(SEL_ACEPTAR)
    reg.wait_for_load_state("networkidle", timeout=60000)


def download_excel(reg, filepath, timeout=30000):
    """Espera el boton de Excel, dispara la descarga y guarda el archivo."""
    reg.wait_for_selector(SEL_EXCEL, timeout=timeout)
    with reg.expect_download(timeout=60000) as download_info:
        reg.click(SEL_EXCEL)
    download_info.value.save_as(filepath)


def save_grid_html(reg, filepath, timeout=30000):
    """Extrae la grilla de datos (#dgList) del popup y la guarda como .xls
    (tabla HTML). Se usa para items cuyo boton Excel no descarga nada."""
    reg.wait_for_selector(SEL_GRID, timeout=timeout)
    table_html = reg.locator(SEL_GRID).evaluate("el => el.outerHTML")
    html = (
        "<html><head><meta charset=\"utf-8\"></head><body>"
        + table_html
        + "</body></html>"
    )
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(html)


def export_item(reg, item_name, filepath):
    """Descarga via boton Excel o, si el export del item esta roto en el
    servidor (HTML_GRID_ITEMS), extrae la grilla HTML de la pagina."""
    if item_name in HTML_GRID_ITEMS:
        save_grid_html(reg, filepath)
    else:
        download_excel(reg, filepath)


# --------------------------------------------------------------------------- #
# Bloques de descarga
# --------------------------------------------------------------------------- #
def run_anual(page, years, overwrite):
    seccion = MENU["anual"]
    for year in years:
        print(f"\n=== ANUALES {year} (1 login) ===")
        frame = login(page)
        for item_name, title in ANUAL_ITEMS:
            folder = build_download_folder("Formularios_Anuales", item_name, year)
            filepath = os.path.join(folder, f"{safe_name(item_name)}_{year}.xls")
            if not overwrite and os.path.exists(filepath):
                print(f"  [SKIP] {item_name} (ya existe)")
                continue
            reg = None
            try:
                loc = item_locator(frame, seccion["child"], "title", title)
                reg = open_item_popup(page, frame, seccion["folder"], seccion["child"], loc)
                configure_period(reg, year)
                export_item(reg, item_name, filepath)
                print(f"  [OK] {item_name} -> {os.path.basename(filepath)}")
            except Exception as e:
                print(f"  [WARN] {item_name}: {type(e).__name__}: {str(e)[:120]}")
            finally:
                _safe_close(reg)
                frame = get_frame(page) or frame
                human_pause(page)


def run_semestral(page, years, overwrite):
    seccion = MENU["semestral"]
    for year in years:
        for label, slug, mes in SEMESTERS:
            print(f"\n=== SEMESTRALES {year} {label} (1 login) ===")
            frame = login(page)
            for item_name, title in SEMESTRAL_ITEMS:
                folder = build_download_folder("Formularios_Semestrales", item_name, year, period=slug)
                filepath = os.path.join(folder, f"{safe_name(item_name)}_{year}_{slug}.xls")
                if not overwrite and os.path.exists(filepath):
                    print(f"  [SKIP] {item_name} {label} (ya existe)")
                    continue
                reg = None
                try:
                    loc = item_locator(frame, seccion["child"], "title", title)
                    reg = open_item_popup(page, frame, seccion["folder"], seccion["child"], loc)
                    configure_period(reg, year, mes)
                    download_excel(reg, filepath)
                    print(f"  [OK] {item_name} {label} -> {os.path.basename(filepath)}")
                except Exception as e:
                    print(f"  [WARN] {item_name} {label}: {type(e).__name__}: {str(e)[:120]}")
                finally:
                    _safe_close(reg)
                    frame = get_frame(page) or frame
                    human_pause(page)


def run_trimestral(page, years, overwrite):
    seccion = MENU["trimestral"]
    for year in years:
        for label, slug, mes in QUARTERS:
            print(f"\n=== TRIMESTRALES {year} {label} (1 login) ===")
            frame = login(page)
            for item_name, kind, value in TRIMESTRAL_ITEMS:
                folder = build_download_folder("Formularios_Trimestrales", item_name, year, period=slug)
                filepath = os.path.join(folder, f"{safe_name(item_name)}_{year}_{slug}.xls")
                if not overwrite and os.path.exists(filepath):
                    print(f"  [SKIP] {item_name} {label} (ya existe)")
                    continue
                reg = None
                try:
                    loc = item_locator(frame, seccion["child"], kind, value)
                    reg = open_item_popup(page, frame, seccion["folder"], seccion["child"], loc)
                    configure_period(reg, year, mes)
                    export_item(reg, item_name, filepath)
                    print(f"  [OK] {item_name} {label} -> {os.path.basename(filepath)}")
                except Exception as e:
                    print(f"  [WARN] {item_name} {label}: {type(e).__name__}: {str(e)[:120]}")
                finally:
                    _safe_close(reg)
                    frame = get_frame(page) or frame
                    human_pause(page)


def run_consulta(page, years, overwrite):
    """Reporte 'Contratacion Externa desde 2020' (Consultas Detalladas).
    Es una consulta con filtros en linea: no usa el periodo de captura, por lo
    que basta UN login para todo el bloque; se reabre el popup por (anio,trim)."""
    seccion = MENU["consulta"]
    item_name = "Reporte Contratacion Externa desde 2020"
    print("\n=== CONSULTAS DETALLADAS: Contratacion Externa (1 login) ===")
    frame = login(page)
    for year in years:
        for label, slug, mes in QUARTERS:
            folder = os.path.join(DOWNLOAD_FOLDER, entity_folder(), "Consultas_Detalladas", safe_name(item_name), str(year))
            os.makedirs(folder, exist_ok=True)
            filepath = os.path.join(folder, f"{safe_name(item_name)}_{year}_{slug}.xls")
            if not overwrite and os.path.exists(filepath):
                print(f"  [SKIP] {year} {label} (ya existe)")
                continue
            reg = None
            try:
                loc = item_locator(frame, seccion["child"], "title", "Contratación Externa")
                reg = open_item_popup(page, frame, seccion["folder"], seccion["child"], loc)
                reg.select_option("#_ctl0_ContentPlaceHolder1_ddano", str(year))
                reg.select_option("#_ctl0_ContentPlaceHolder1_ddmes", str(mes))
                # "mostrar" (trae el detalle); dispara postback -> esperar
                chk = reg.locator("#_ctl0_ContentPlaceHolder1_chkmostrar")
                if chk.count() and not chk.is_checked():
                    chk.check()
                    reg.wait_for_load_state("networkidle", timeout=60000)
                reg.click("#_ctl0_ibBuscarFtr")
                reg.wait_for_load_state("networkidle", timeout=60000)
                download_excel(reg, filepath)
                print(f"  [OK] {year} {label} -> {os.path.basename(filepath)}")
            except Exception as e:
                print(f"  [WARN] {year} {label}: {type(e).__name__}: {str(e)[:120]}")
            finally:
                _safe_close(reg)
                frame = get_frame(page) or frame
                human_pause(page)


def _safe_close(reg):
    try:
        if reg is not None and not reg.is_closed():
            reg.close()
    except PlaywrightError:
        pass


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def parse_args():
    p = argparse.ArgumentParser(description="RPA de descarga SIHO (login por bloque de periodo).")
    p.add_argument("--anual", action="store_true", help="Descargar Formularios Anuales.")
    p.add_argument("--semestral", action="store_true", help="Descargar Formularios Semestrales.")
    p.add_argument("--trimestral", action="store_true", help="Descargar Formularios Trimestrales.")
    p.add_argument("--consulta", action="store_true", help="Descargar Consulta Contratacion Externa.")
    p.add_argument("--years", type=int, nargs="+", default=YEARS, help="Anios a procesar.")
    p.add_argument("--overwrite", action="store_true", help="Volver a descargar aunque el archivo exista.")
    p.add_argument("--user", default=None, help="Usuario SIHO (tambien via env SIHO_USER).")
    p.add_argument("--password", default=None, help="Contrasena SIHO (tambien via env SIHO_PASSWORD).")
    p.add_argument("--headful", dest="headless", action="store_false",
                   help="(por defecto) navegador visible; requerido por el WAF.")
    p.set_defaults(headless=False)
    return p.parse_args()


def main():
    global USER, PASSWORD
    args = parse_args()
    if args.user:
        USER = args.user
    if args.password:
        PASSWORD = args.password
    if not USER or not PASSWORD:
        raise SystemExit(
            "ERROR: faltan credenciales. Use --user/--password o las variables "
            "de entorno SIHO_USER / SIHO_PASSWORD."
        )
    # Si no se especifica ninguna seccion, se ejecutan todas.
    run_all = not (args.anual or args.semestral or args.trimestral or args.consulta)

    start = time.time()
    with sync_playwright() as p:
        # headless=False es OBLIGATORIO: el WAF bloquea navegadores headless.
        browser = p.chromium.launch(headless=args.headless)
        ctx = browser.new_context(
            viewport={"width": 1366, "height": 900},
            accept_downloads=True,
        )
        page = ctx.new_page()
        page.set_default_timeout(60000)
        page.set_default_navigation_timeout(60000)
        try:
            if run_all or args.anual:
                run_anual(page, args.years, args.overwrite)
            if run_all or args.semestral:
                run_semestral(page, args.years, args.overwrite)
            if run_all or args.trimestral:
                run_trimestral(page, args.years, args.overwrite)
            if run_all or args.consulta:
                run_consulta(page, args.years, args.overwrite)
        finally:
            browser.close()
    print(f"\nListo en {time.time() - start:.0f}s. Archivos en: {DOWNLOAD_FOLDER}")


if __name__ == "__main__":
    main()
