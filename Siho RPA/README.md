# Siho RPA — Descarga y organización de datos del SIHO

Automatización (RPA) para **descargar los reportes de una entidad desde el SIHO**
(Sistema de Información Hospitalaria del Ministerio de Salud,
`prestadores.minsalud.gov.co/siho`) y **convertirlos/organizarlos** en CSV y
libros de Excel listos para analizar.

Todo se maneja desde una **aplicación web local** (se abre sola en el navegador):
se ingresan usuario y contraseña de la entidad, se eligen las secciones y los
años, y la app descarga y organiza. No se programa nada; se usa desde el navegador.

---

## 🚀 Uso rápido

1. Doble clic en **`Iniciar SIHO App.bat`** (o en una terminal: `python app.py`).
2. Se abre `http://localhost:5000` en el navegador.
3. Ingresar **usuario** y **contraseña** de la entidad en el SIHO.
4. Marcar las **secciones** (Anual / Semestral / Trimestral / Consulta) y los **años**.
5. Pulsar **Iniciar descarga**. Se abrirá **una ventana de Chromium visible**:
   **no la cierre** mientras descarga.
6. Al terminar (si se marcó la opción), convierte todo a CSV y arma los Excel
   consolidados. Desde la misma app se pueden explorar, descargar o comprimir (ZIP)
   los resultados.

> ⚠️ **La ventana del navegador debe ser visible.** El sitio está detrás de un
> WAF que **bloquea navegadores headless** ("Web Page Blocked!"), por eso el RPA
> corre con ventana a la vista.

---

## 📁 Contenido de la carpeta

```
Siho RPA/
├── Iniciar SIHO App.bat                 # Lanzador (doble clic): abre la app web
├── app.py                               # App web local (Flask) que orquesta todo
├── scrap.py                             # RPA de descarga (Playwright/Chromium)
├── convert_xls_to_csv.py                # XLS → CSV UTF-8 → Excel consolidado
├── comparar_salarios_recursos_humanos.py# Análisis: ranking de salarios de RR.HH.
├── templates/index.html                 # Interfaz web
├── scrap_original_backup.py             # Respaldo de la versión anterior del RPA
├── html2.html                           # Página de referencia (muestra del sitio)
├── descargas/                           # SALIDA 1: .xls crudos descargados
│   └── <ENTIDAD>/<categoría>/<año>/[periodo]/<item>/...
└── descargas_csv/                       # SALIDA 2: CSV + Excel consolidados
    └── <ENTIDAD>/<categoría>/...  +  <categoría>.xlsx
```

---

## 🧩 Componentes

### `app.py` — Aplicación web local (Flask)
Orquesta el proceso completo desde el navegador (`localhost:5000`). Sus funciones:

- Lanza `scrap.py` y `convert_xls_to_csv.py` como **subprocesos** y **transmite su
  salida en vivo** al navegador.
- Recibe las **credenciales por variables de entorno** (`SIHO_USER` /
  `SIHO_PASSWORD`), nunca en la línea de comandos.
- Ejecuta **un solo trabajo a la vez**; permite **detenerlo** (mata también el
  Chromium hijo con `taskkill /T`).
- **Explorador de archivos** integrado (`/api/browse`) y descarga de archivos o
  carpetas en **ZIP** (`/api/zip`), acotado de forma segura a `descargas/` y
  `descargas_csv/`.
- Los **años consultables** van desde **2020 hasta el año actual** y se recalculan
  solos (no hay que tocar el código cada año).

### `scrap.py` — RPA de descarga (Playwright)
Automatiza el navegador para descargar los reportes. Puntos clave:

- **Un login por bloque de periodo** (no uno por ítem): el sitio recuerda el
  periodo activo en la sesión, así que tras el primer formulario los demás del
  mismo periodo abren directo en Excel. Reduce ~90 % los logins/recargas.
  - Anuales: 1 login por año · Semestrales: 1 por (año, semestre) ·
    Trimestrales: 1 por (año, trimestre) · Consultas: 1 para todo el bloque.
- **Reanudable:** si el archivo destino ya existe, lo omite (usar `--overwrite`
  para volver a bajarlo).
- **Detecta el nombre de la entidad** tras el login y guarda todo bajo
  `descargas/<ENTIDAD>/…`, separando las consultas de cada entidad.
- Un fallo en un ítem **no aborta el bloque** (se registra `[WARN]` y sigue).
- Algunos ítems con exportación rota en el servidor (p. ej. *Infraestructura*)
  se guardan extrayendo la **grilla HTML** como `.xls`.

Uso directo (opcional, la app ya lo hace por usted):
```bash
python scrap.py --anual --trimestral --years 2024 2025
# credenciales por entorno: SIHO_USER / SIHO_PASSWORD  (o --user / --password)
```
Secciones: `--anual` `--semestral` `--trimestral` `--consulta`
(si no se indica ninguna, descarga **todas**).

### `convert_xls_to_csv.py` — Conversión y organización
- Convierte **recursivamente** los `.xls` de `descargas/` a **CSV UTF-8** en
  `descargas_csv/`, **manteniendo la estructura de carpetas**.
- Muchos `.xls` del SIHO son en realidad **tablas HTML**; el script las detecta y
  las procesa igual (fallback `pd.read_html`).
- **Elimina columnas de metadatos** (año, mes, códigos, IP, fechas de captura, …)
  tanto de los CSV como de los Excel.
- **Consolida** los CSV en libros de Excel: un `.xlsx` por categoría dentro de la
  carpeta de la entidad (una hoja por reporte, con año y trimestre en el nombre).

Uso directo (opcional):
```bash
python convert_xls_to_csv.py            # descargas/ -> descargas_csv/
python convert_xls_to_csv.py --include-xlsx
```

### `comparar_salarios_recursos_humanos.py` — Análisis de salarios
Toma los CSV de **Recursos Humanos** ya organizados y produce un **ranking anual
de salarios por cargo y perfil ocupacional**, con variación porcentual año a año.

```bash
python comparar_salarios_recursos_humanos.py
# lee:  descargas_csv/Formularios_Anuales/*/Recursos_Humanos/Recursos_Humanos_*.csv
# crea: descargas_csv/analisis_recursos_humanos/ranking_salarios_por_cargo_perfil_anual.{csv,xlsx}
```

---

## 📊 Secciones que descarga

| Sección | Periodicidad | Ejemplos de ítems |
|---|---|---|
| **Anual** | 1 por año | Recursos Humanos, Ingresos, Gastos, Facturación, Cartera por Deudor, Pasivos, Balance General, Estado de Actividad, Producción, Capacidad Instalada, Infraestructura, Procesos Judiciales… |
| **Semestral** | ene–jun / jul–dic | Calidad |
| **Trimestral** | ene–mar, abr–jun, jul–sep, oct–dic | Facturación, Cartera, Pasivos, Balance, Ejecución Presupuestal, Contratación Externa, Calidad, RR.HH., Infraestructura… |
| **Consulta** | trimestral | Reporte de Contratación Externa desde 2020 |

Datos disponibles **desde 2020** hasta el año actual.

---

## 🔧 Requisitos

- **Python 3.10+**
- Paquetes: `flask`, `playwright`, `pandas`, `openpyxl`, `xlrd`, `lxml` (o
  `html5lib`, para leer las tablas HTML).
- Navegador de Playwright (Chromium):
  ```bash
  pip install flask playwright pandas openpyxl xlrd lxml
  playwright install chromium
  ```

---

## 🔐 Notas de seguridad y operación

- Las **credenciales** se pasan por variables de entorno al subproceso; no se
  escriben en disco ni en la línea de comandos.
- La app corre **solo en local** (`127.0.0.1:5000`); no expone nada a la red.
- El explorador y las descargas están **acotados** a `descargas/` y
  `descargas_csv/` (no se puede salir de esas carpetas).
- Durante la descarga se abre **Chromium visible** (requisito del WAF del sitio).
  Si necesita cancelar, use el botón **Detener** de la app (no cierre la ventana
  del navegador a mano).
