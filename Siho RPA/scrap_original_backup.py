from playwright.sync_api import sync_playwright
import pandas as pd
import json
from datetime import datetime
import numpy as np
import os
import sys
import shutil
import re
import unicodedata

YEARS = [2020,2021,2022,2023,2024,2025]
INIT_URL = "https://prestadores.minsalud.gov.co/siho/"
USER = "5451800372"
PASSWORD = "890501019"
TRI = ["ENE-MAR", "ABR-JUN", "JUL-SEP", "OCT-DIC"]
DOWNLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "descargas")

SIHO_MENU = {
    "Formularios Anuales": {
        "folder_selector": 'a[name="item0"]',
        "child_div": '#item0Child',
        "items": {
            "Ingresos":             'a[title="Ingresos"]',
            "Gastos":               'a[title="Gastos"]',
            "Cartera por Deudor":   'a[title="Cartera por Deudor"]',
            "Facturación":          'a[title="Facturación"]',
            "Mecanismos de Pago":   'a[title="Mecanismos de pago aplicables a la compra de S.S"]',
            "Demandas Judiciales":  'a[title="Procesos Judiciales de la IPS"]',
            "Estado de Actividad":  'a[title="Estado de Actividad Económica Financiera y Social"]',
            "Pasivos":              'a[title="Información de Pasivos"]',
            "Recursos Humanos":     'a[title="Recursos Humanos"]',
            "Capacidad Instalada":  'a[title="Capacidad Instalada"]',
            "Infraestructura":       'a[title="Formularios de infraestructura"]',
            "Estado de Actividad":  'a[title="Estado de Actividad Económica Financiera y Social"]',
            "Producción":           'a[title="Producción"]',


            "Pasivo Prestacional":  'a[title="Pasivo Prestacional"]',
        }
    },
    "Formularios Trimestrales": {
        "folder_selector": 'a[name="item16"]',
        "child_div": '#item16Child',
        "items": {
            "Ejecución Presupuestal":   'a[title="Ejecución Presupuestal de Ingresos y Gastos"]',
            "Calidad":                  'a[title="Indicadares de calidad"]',
        }
    },
    "Consultas Detalladas": {
        "folder_selector": 'a[name="item42"]',
        "child_div": '#item42Child',
        "items": {
            "Reporte Contratación Externa desde 2020":              'a[title="Contratación Externa"]',
        }
    },
    "Login": {
        "usuario":      '#tbid_usuario',
        "contraseña":   '#tbcontrasena',
        "btn_ingresar": '#btnIngresar',
    }
}


def safe_name(value):
    normalized = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode("ascii")
    normalized = re.sub(r"[^A-Za-z0-9_-]+", "_", normalized).strip("_")
    return normalized or "sin_nombre"


def build_download_folder(category, item_name, year, period=None):
    parts = [DOWNLOAD_FOLDER, safe_name(category), str(year)]
    if period:
        parts.append(safe_name(period))
    parts.append(safe_name(item_name))
    folder = os.path.join(*parts)
    os.makedirs(folder, exist_ok=True)
    return folder

def tri_label(tri):
    labels = {
        "ENE-MAR": "enero-mar",
        "ABR-JUN": "abril-jun",
        "JUL-SEP": "julio-sep",
        "OCT-DIC": "octubre-dic",
    }
    return labels.get(tri, safe_name(tri).lower())

def scrap_web():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        page.set_default_timeout(60000)  # Set a default timeout of 60 seconds
        page.set_default_navigation_timeout(60000)  # Set a default navigation timeout of 60 seconds
        page.goto(INIT_URL)
        page.wait_for_timeout(np.random.uniform(1000, 2000))
        frame = page.frame(name='areawork')
        if not frame:
            print("No se pudo encontrar el frame 'areawork'.")
            exit(1)
        else:
            try:
                anual(page, frame)
                #consultas_detalladas(page, frame)
                #trimestral(page, frame)
            except Exception as e:
                print(f"Error al hacer clic en el botón: {e}")
                exit(1)

def anual(page, frame):
     for year in YEARS:
        for item_name, item_selector in SIHO_MENU["Formularios Anuales"]["items"].items():
            page.reload()
            page.wait_for_timeout(np.random.uniform(1000, 2000))
            print(f"\n=== Procesando año: {year} ===")
            
            # Obtener el frame actualizado después de cada recarga
            frame = page.frame(name='areawork')
            if not frame:
                print("No se pudo encontrar el frame 'areawork'.")
                continue
                
            frame.fill("#tbid_usuario", USER)
            frame.fill("#tbcontrasena", PASSWORD)
            frame.click("#btningresar")
            page.wait_for_load_state("domcontentloaded", timeout=60000)

            # Obtener el frame actualizado después del login
            frame = page.frame(name='areawork')
            frame.click(SIHO_MENU["Formularios Anuales"]["folder_selector"])
            page.wait_for_timeout(np.random.uniform(1000, 2000))
            
            try:
                with page.expect_popup() as popup_info:
                    frame.click(item_selector)

                register_page = popup_info.value
                register_page.wait_for_load_state('networkidle', timeout=60000)
                print(f"Hiciste clic en el botón: {item_name}")
                register_page.select_option('#ddano', str(year))
                register_page.click('#ibAceptar')
                register_page.wait_for_load_state('networkidle', timeout=60000)
                
                # Estructura: descargas/Formularios_Anuales/<año>/<item>/
                item_folder = build_download_folder("Formularios_Anuales", item_name, year)

                # Esperar y capturar la descarga
                with register_page.expect_download() as download_info:
                    register_page.click('#_ctl0_ContentPlaceHolder1_ibExcel')

                download = download_info.value
                # Guardar archivo con nombre descriptivo
                filename = f"{safe_name(item_name)}_{year}.xls"
                filepath = os.path.join(item_folder, filename)
                download.save_as(filepath)
                print(f"Archivo guardado: {filepath}")
                
                # Cerrar la pestaña popup
                register_page.close()
                page.wait_for_timeout(np.random.uniform(500, 1000))

            except Exception as e:
                print(f"Error al hacer clic en el botón '{item_name}': {e}")
                # Intentar cerrar la pestaña si está abierta
                try:
                    register_page.close()
                except:
                    pass
                continue  # Continuar con el siguiente item en lugar de salir
        
        # Cerrar sesión o recargar para el siguiente año
        page.goto(INIT_URL)
        page.wait_for_timeout(np.random.uniform(1000, 2000))

def trimestral(page, frame):
    for year in YEARS:
        for item_name, item_selector in SIHO_MENU["Formularios Trimestrales"]["items"].items():
            for tri in TRI:
                page.reload()
                page.wait_for_timeout(np.random.uniform(1000, 2000))
                print(f"\n=== Procesando año: {year} ===")
                
                # Obtener el frame actualizado después de cada recarga
                frame = page.frame(name='areawork')
                if not frame:
                    print("No se pudo encontrar el frame 'areawork'.")
                    continue
                    
                frame.fill("#tbid_usuario", USER)
                frame.fill("#tbcontrasena", PASSWORD)
                frame.click("#btningresar")
                page.wait_for_load_state("domcontentloaded", timeout=60000)

                # Obtener el frame actualizado después del login
                frame = page.frame(name='areawork')
                frame.click(SIHO_MENU["Formularios Trimestrales"]["folder_selector"])
                page.wait_for_timeout(np.random.uniform(1000, 2000))
                
                try:
                    with page.expect_popup() as popup_info:
                        frame.click(item_selector)

                    register_page = popup_info.value
                    register_page.wait_for_load_state('networkidle', timeout=60000)
                    print(f"Hiciste clic en el botón: {item_name}")
                    register_page.select_option('#ddano', str(year))
                    register_page.select_option('#ddmes', str(tri))
                    register_page.click('#ibAceptar')
                    register_page.wait_for_load_state('networkidle', timeout=60000)
                    
                    # Estructura: descargas/formularios_trimestrales/<año>/<item>/
                    item_folder = build_download_folder(
                        "formularios_trimestrales",
                        item_name,
                        year,
                    )

                    # Esperar y capturar la descarga
                    with register_page.expect_download() as download_info:
                        register_page.click('#_ctl0_ContentPlaceHolder1_ibExcel')

                    download = download_info.value
                    # Guardar archivo único por año+trimestre para evitar sobreescritura
                    extension = os.path.splitext(download.suggested_filename)[1] or ".xls"
                    filename = f"{safe_name(item_name).lower()}_{year}_{tri_label(tri)}{extension}"
                    filepath = os.path.join(item_folder, filename)
                    download.save_as(filepath)
                    print(f"Archivo guardado: {filepath}")
                    
                    # Cerrar la pestaña popup
                    register_page.close()
                    page.wait_for_timeout(np.random.uniform(500, 1000))

                except Exception as e:
                    print(f"Error al hacer clic en el botón '{item_name}': {e}")
                    # Intentar cerrar la pestaña si está abierta
                    try:
                        register_page.close()
                    except:
                        pass
                    continue  # Continuar con el siguiente item en lugar de salir
            
            # Cerrar sesión o recargar para el siguiente año
            page.goto(INIT_URL)
            page.wait_for_timeout(np.random.uniform(1000, 2000))

def consultas_detalladas(page, frame):
    for year in YEARS:
        for item_name, item_selector in SIHO_MENU["Consultas Detalladas"]["items"].items():
            for tri in TRI:
                page.reload()
                page.wait_for_timeout(np.random.uniform(1000, 2000))
                print(f"\n=== Procesando año: {year} ===")

                # Obtener el frame actualizado después de cada recarga
                frame = page.frame(name='areawork')
                if not frame:
                    print("No se pudo encontrar el frame 'areawork'.")
                    continue

                frame.fill("#tbid_usuario", USER)
                frame.fill("#tbcontrasena", PASSWORD)
                frame.click("#btningresar")
                page.wait_for_load_state("domcontentloaded", timeout=60000)

                # Obtener el frame actualizado después del login
                frame = page.frame(name='areawork')
                # item42 está en la 2ª columna del menú: forzar scroll y esperar visibilidad
                folder_locator = frame.locator(SIHO_MENU["Consultas Detalladas"]["folder_selector"])
                folder_locator.scroll_into_view_if_needed(timeout=15000)
                folder_locator.click()
                # Esperar a que el submenú hijo (#item42Child) se expanda
                frame.wait_for_selector(
                    SIHO_MENU["Consultas Detalladas"]["child_div"],
                    state="visible", timeout=10000
                )
                page.wait_for_timeout(np.random.uniform(500, 1000))

                try:
                    # Acotar el selector dentro de #item42Child para evitar
                    # coincidir con a[title="Contratación Externa"] de #item16Child
                    scoped_selector = f'{SIHO_MENU["Consultas Detalladas"]["child_div"]} {item_selector}'
                    with page.expect_popup() as popup_info:
                        frame.click(scoped_selector)

                    register_page = popup_info.value
                    register_page.wait_for_load_state('networkidle', timeout=60000)
                    print(f"Hiciste clic en el botón: {item_name}")
                    register_page.select_option('#_ctl0_ContentPlaceHolder1_ddano', str(year))
                    register_page.select_option('#_ctl0_ContentPlaceHolder1_ddmes', str(tri))
                    register_page.click('#_ctl0_ContentPlaceHolder1_chkmostrar')
                    register_page.click('#_ctl0_ibBuscarFtr')
                    register_page.wait_for_load_state('networkidle', timeout=60000)

                    # Estructura: descargas/consultas_detalladas/<item>/<año>/
                    item_folder = os.path.join(
                        DOWNLOAD_FOLDER,
                        "consultas_detalladas",
                        safe_name(item_name),
                        str(year),
                    )
                    os.makedirs(item_folder, exist_ok=True)

                    # Esperar y capturar la descarga
                    with register_page.expect_download() as download_info:
                        register_page.click('#_ctl0_ContentPlaceHolder1_ibExcel')

                    download = download_info.value
                    extension = os.path.splitext(download.suggested_filename)[1] or ".xls"
                    filename = f"{safe_name(item_name)}_{tri_label(tri)}{extension}"
                    filepath = os.path.join(item_folder, filename)
                    download.save_as(filepath)
                    print(f"Archivo guardado: {filepath}")

                    # Cerrar la pestaña popup
                    register_page.close()
                    page.wait_for_timeout(np.random.uniform(500, 1000))

                except Exception as e:
                    print(f"Error al hacer clic en el botón '{item_name}': {e}")
                    try:
                        register_page.close()
                    except:
                        pass
                    continue

        # Cerrar sesión o recargar para el siguiente año
        page.goto(INIT_URL)
        page.wait_for_timeout(np.random.uniform(1000, 2000))


# Modificar la llamada principal al final del archivo
if __name__ == "__main__":
    scrap_web()





