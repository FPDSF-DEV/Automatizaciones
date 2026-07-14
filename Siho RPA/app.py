"""
Aplicacion web local para el RPA de descarga SIHO (scrap.py) y la
conversion/organizacion de datos (convert_xls_to_csv.py).

Uso:
    python app.py
Luego abrir http://localhost:5000 (se abre solo). Ingresar usuario y
contrasena de la entidad, elegir secciones/anios y pulsar "Iniciar descarga".
Al terminar (si la opcion esta marcada) se convierte todo a CSV y se
consolida en libros de Excel, sin las columnas de metadatos.

La app lanza los scripts como subprocesos (credenciales en variables de
entorno, nunca en la linea de comandos) y transmite su salida en vivo al
navegador. Recordar: el sitio bloquea navegadores headless, por lo que se
abrira una ventana de Chromium visible durante la descarga.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import threading
import time
import webbrowser
import zipfile
from datetime import datetime

from flask import Flask, jsonify, render_template, request, send_file

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SCRAP_SCRIPT = os.path.join(BASE_DIR, "scrap.py")
CONVERT_SCRIPT = os.path.join(BASE_DIR, "convert_xls_to_csv.py")
DOWNLOAD_FOLDER = os.path.join(BASE_DIR, "descargas")
CSV_FOLDER = os.path.join(BASE_DIR, "descargas_csv")
PORT = 5000
FIRST_YEAR = 2020

VALID_SECTIONS = {"anual", "semestral", "trimestral", "consulta"}
CONVERT_LABEL = "Conversión y organización (XLS → CSV → Excel)"

app = Flask(__name__)

# Estado del unico trabajo en curso (un proceso a la vez).
_lock = threading.Lock()
_job = {
    "proc": None,
    "lines": [],
    "running": False,
    "returncode": None,
    "started": None,
    "finished": None,
    "params": None,
    "phase": None,
    "cancel": False,
}


def valid_years() -> set[int]:
    """Anios consultables: desde 2020 hasta el anio ACTUAL. Se recalcula en
    cada peticion, asi el anio nuevo aparece solo, sin tocar el codigo."""
    return set(range(FIRST_YEAR, datetime.now().year + 1))


def _base_env() -> dict:
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    return env


def _runner_thread(steps):
    """Ejecuta los pasos en orden, transmitiendo su salida al log compartido.
    Corta la cadena si un paso falla o si el usuario detiene el proceso."""
    rc = 0
    for label, cmd, env in steps:
        with _lock:
            if _job["cancel"]:
                break
            _job["phase"] = label
            _job["lines"].append(f"--- {label} ---")
        proc = subprocess.Popen(
            cmd,
            cwd=BASE_DIR,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        with _lock:
            _job["proc"] = proc
        for line in proc.stdout:
            with _lock:
                _job["lines"].append(line.rstrip("\r\n"))
        proc.wait()
        rc = proc.returncode
        if rc != 0:
            break
    with _lock:
        _job.update(running=False, returncode=rc, finished=time.time(), proc=None, phase=None)
        if _job["cancel"]:
            _job["lines"].append("--- Detenido por el usuario ---")
        else:
            _job["lines"].append(f"--- Proceso terminado (código {rc}) ---")


def _start_job(steps, params, intro_lines) -> bool:
    with _lock:
        if _job["running"]:
            return False
        _job.update(
            proc=None,
            lines=list(intro_lines),
            running=True,
            returncode=None,
            started=time.time(),
            finished=None,
            params=params,
            phase=None,
            cancel=False,
        )
    threading.Thread(target=_runner_thread, args=(steps,), daemon=True).start()
    return True


@app.get("/")
def index():
    return render_template("index.html", years=sorted(valid_years()))


@app.post("/api/start")
def api_start():
    data = request.get_json(silent=True) or {}
    usuario = str(data.get("usuario", "")).strip()
    password = str(data.get("password", "")).strip()
    sections = [s for s in data.get("secciones", []) if s in VALID_SECTIONS]
    overwrite = bool(data.get("overwrite", False))
    convertir = bool(data.get("convertir", False))
    try:
        years = sorted({int(y) for y in data.get("years", [])})
    except (TypeError, ValueError):
        return jsonify(error="Años inválidos."), 400

    current_year = datetime.now().year
    if not usuario or not password:
        return jsonify(error="Debe ingresar usuario y contraseña."), 400
    if not sections:
        return jsonify(error="Seleccione al menos una sección a descargar."), 400
    if not years:
        return jsonify(error="Seleccione al menos un año."), 400
    if years[-1] > current_year:
        return jsonify(
            error=f"El año {years[-1]} es mayor que el año actual ({current_year})."
        ), 400
    if years[0] < FIRST_YEAR:
        return jsonify(error=f"Solo hay datos disponibles desde {FIRST_YEAR}."), 400

    cmd = [sys.executable, "-u", SCRAP_SCRIPT]
    for s in sections:
        cmd.append(f"--{s}")
    cmd += ["--years", *[str(y) for y in years]]
    if overwrite:
        cmd.append("--overwrite")

    env = _base_env()
    env["SIHO_USER"] = usuario
    env["SIHO_PASSWORD"] = password

    steps = [("Descarga SIHO", cmd, env)]
    if convertir:
        steps.append((CONVERT_LABEL, [sys.executable, "-u", CONVERT_SCRIPT], _base_env()))

    intro = [
        f"--- Descarga iniciada {datetime.now():%Y-%m-%d %H:%M:%S} ---",
        f"Secciones: {', '.join(sections)} | Años: {', '.join(map(str, years))}"
        + (" | sobrescribir" if overwrite else "")
        + (" | convertir al terminar" if convertir else ""),
        "Se abrirá una ventana de Chromium: NO la cierre mientras descarga.",
    ]
    params = {
        "secciones": sections,
        "years": years,
        "overwrite": overwrite,
        "convertir": convertir,
    }
    if not _start_job(steps, params, intro):
        return jsonify(error="Ya hay un proceso en curso."), 409
    return jsonify(ok=True)


@app.post("/api/convert")
def api_convert():
    """Convierte y organiza lo ya descargado, sin volver a descargar."""
    if not os.path.isdir(DOWNLOAD_FOLDER):
        return jsonify(error="Aún no hay archivos descargados para convertir."), 400
    steps = [(CONVERT_LABEL, [sys.executable, "-u", CONVERT_SCRIPT], _base_env())]
    intro = [f"--- Conversión iniciada {datetime.now():%Y-%m-%d %H:%M:%S} ---"]
    if not _start_job(steps, {"solo_conversion": True}, intro):
        return jsonify(error="Ya hay un proceso en curso."), 409
    return jsonify(ok=True)


@app.get("/api/status")
def api_status():
    offset = request.args.get("offset", 0, type=int)
    with _lock:
        return jsonify(
            running=_job["running"],
            returncode=_job["returncode"],
            started=_job["started"],
            finished=_job["finished"],
            params=_job["params"],
            phase=_job["phase"],
            total=len(_job["lines"]),
            lines=_job["lines"][offset:],
        )


@app.post("/api/stop")
def api_stop():
    with _lock:
        if not _job["running"]:
            return jsonify(error="No hay ningún proceso en curso."), 400
        _job["cancel"] = True
        proc = _job["proc"]
        pid = proc.pid if proc else None
    if pid:
        # taskkill /T mata tambien el navegador Chromium hijo de Playwright.
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True)
    return jsonify(ok=True)


def _resolve_safe(rel) -> str | None:
    """Convierte una ruta relativa en absoluta SOLO si queda dentro de
    descargas/ o descargas_csv/ (evita salirse de esas carpetas)."""
    rel = str(rel or "").replace("\\", "/").strip().strip("/")
    full = os.path.realpath(os.path.join(BASE_DIR, rel))
    for root in (DOWNLOAD_FOLDER, CSV_FOLDER):
        real_root = os.path.realpath(root)
        if full == real_root or full.startswith(real_root + os.sep):
            return full
    return None


def _tree_stats(folder: str) -> tuple[int, int]:
    files = 0
    size = 0
    for root, _dirs, names in os.walk(folder):
        for f in names:
            if f.startswith("~$"):
                continue
            try:
                size += os.stat(os.path.join(root, f)).st_size
                files += 1
            except OSError:
                pass
    return files, size


@app.get("/api/browse")
def api_browse():
    """Explorador: '' lista las dos carpetas raiz; cualquier otra ruta
    relativa lista sus subcarpetas (con conteo) y archivos."""
    rel = request.args.get("path", "").replace("\\", "/").strip("/")
    if not rel:
        roots = []
        for root, label in (
            (DOWNLOAD_FOLDER, "Descargas del SIHO (.xls)"),
            (CSV_FOLDER, "Datos organizados (CSV y Excel)"),
        ):
            if os.path.isdir(root):
                n, b = _tree_stats(root)
                roots.append({
                    "name": os.path.basename(root),
                    "rel": os.path.basename(root),
                    "label": label,
                    "items": n,
                    "bytes": b,
                })
        return jsonify(path="", parent=None, dirs=roots, files=[])

    full = _resolve_safe(rel)
    if not full or not os.path.isdir(full):
        return jsonify(error="Carpeta no válida."), 404

    dirs = []
    files = []
    for entry in sorted(os.scandir(full), key=lambda e: e.name.lower()):
        if entry.name.startswith("~$"):
            continue
        child_rel = f"{rel}/{entry.name}"
        if entry.is_dir():
            n, b = _tree_stats(entry.path)
            dirs.append({"name": entry.name, "rel": child_rel, "items": n, "bytes": b})
        else:
            st = entry.stat()
            files.append({
                "name": entry.name,
                "rel": child_rel,
                "bytes": st.st_size,
                "mtime": st.st_mtime,
            })
    parent = rel.rsplit("/", 1)[0] if "/" in rel else ""
    return jsonify(path=rel, parent=parent, dirs=dirs, files=files)


@app.post("/api/open-folder")
def api_open_folder():
    data = request.get_json(silent=True) or {}
    full = _resolve_safe(data.get("path") or "descargas")
    if not full:
        return jsonify(error="Carpeta no válida."), 404
    os.makedirs(full, exist_ok=True)
    os.startfile(full)  # noqa: S606 - app local de escritorio
    return jsonify(ok=True)


@app.get("/api/download")
def api_download():
    full = _resolve_safe(request.args.get("path", ""))
    if not full or not os.path.isfile(full):
        return jsonify(error="Archivo no válido."), 404
    return send_file(full, as_attachment=True)


@app.get("/api/zip")
def api_zip():
    rel = request.args.get("path", "descargas")
    full = _resolve_safe(rel)
    if not full or not os.path.isdir(full):
        return jsonify(error="Carpeta no válida."), 404
    tmp = tempfile.NamedTemporaryFile(suffix=".zip", delete=False, dir=tempfile.gettempdir())
    tmp.close()
    with zipfile.ZipFile(tmp.name, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _dirs, files in os.walk(full):
            for f in files:
                if f.startswith("~$"):
                    continue
                path = os.path.join(root, f)
                zf.write(path, os.path.relpath(path, full))
    parts = rel.replace("\\", "/").strip("/").split("/")
    base = "_".join(parts[-2:]) if len(parts) > 1 else parts[0]
    name = f"{base}_{datetime.now():%Y%m%d_%H%M}.zip"
    return send_file(tmp.name, as_attachment=True, download_name=name)


def _open_browser():
    webbrowser.open(f"http://localhost:{PORT}")


if __name__ == "__main__":
    threading.Timer(1.0, _open_browser).start()
    print(f"App SIHO en http://localhost:{PORT}  (Ctrl+C para salir)")
    app.run(host="127.0.0.1", port=PORT, debug=False, use_reloader=False)
