# -*- coding: utf-8 -*-
"""Estación de difusión masiva (reconstrucción de la UI de Streamlit).

Flujo por campaña (cada campaña es una carpeta en ./campanas/<nombre>):
  1. Datos      -> carga Excel/CSV/JSON, sanea emails y crea manifest.csv
                   (opcional: genera un Word por destinatario desde una plantilla)
  2. Excluir    -> saca registros del manifest (los mueve a excluidos/, no borra)
  3. PDF        -> convierte los Word generados a PDF (requiere MS Word)
  4. Enviar     -> correo HTML personalizado + adjuntos, con estación SMTP,
                   registro de enviados (reanudable) y modo prueba

Ejecutar:  streamlit run streamlit_app.py
"""
from __future__ import annotations

import csv
import html
import json
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from diplomas.data_loader import DataLoadError, list_excel_sheets, load_records  # noqa: E402
from diplomas.docx_placeholders import extract_placeholders, guess_placeholder_column  # noqa: E402
from diplomas.email_sanitizer import sanitize_table  # noqa: E402
from diplomas.email_service import EmailService, SMTPConfig  # noqa: E402
from diplomas.generic_generator import (  # noqa: E402
    SOURCE_COLUMN,
    SOURCE_FIXED,
    run_generic_generation,
    validate_rows,
    write_manifest_only,
)
from diplomas.record_exclusion import exclude_records, find_matches, parse_exclusion_pairs  # noqa: E402
from diplomas.smtp_pool import (  # noqa: E402
    PoolExhaustedError,
    SMTPAccount,
    SMTPPool,
    get_today_usage,
    load_accounts,
    save_accounts,
    test_account_connection,
)
from diplomas.utils.naming import slugify  # noqa: E402

CAMPAIGNS_DIR = ROOT / "campanas"
DATA_DIR = ROOT / "data"
TEMPLATES_DIR = ROOT / "src" / "diplomas" / "templates"
ACCOUNTS_FILE = ROOT / "smtp_accounts.json"
USAGE_FILE = ROOT / "smtp_usage.json"

MANIFEST = "manifest.csv"
SENT_LOG = "enviados.csv"
MAIL_CONTENT = "correo.json"
SENT_HEADERS = ["timestamp", "email", "subject", "filename", "adjuntos", "cuenta"]
INTERNAL_COLS = ("_filename", "_email")
PLACEHOLDER_RE = re.compile(r"\{\{\s*([^{}]+?)\s*\}\}")

SMTP_PRESETS = {
    "Google Workspace – SMTP Relay": {"server": "smtp-relay.gmail.com", "port": 587, "use_tls": True, "use_ssl": False,
                                      "daily_limit": 2000, "require_auth": False, "local_hostname": ""},
    "Google Workspace / Gmail (usuario)": {"server": "smtp.gmail.com", "port": 587, "use_tls": True, "use_ssl": False,
                                           "daily_limit": 2000, "require_auth": True, "local_hostname": ""},
    "Hostinger": {"server": "smtp.hostinger.com", "port": 587, "use_tls": True, "use_ssl": False, "daily_limit": 100,
                  "require_auth": True, "local_hostname": ""},
    "Personalizado": {"server": "", "port": 587, "use_tls": True, "use_ssl": False, "daily_limit": 0,
                      "require_auth": True, "local_hostname": ""},
}
AUTH_OPTS = ["Usuario y contraseña", "Sin login (relay autorizado por IP)"]

st.set_page_config(page_title="Difusión masiva", page_icon="📨", layout="wide")


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------

def list_campaigns() -> List[str]:
    CAMPAIGNS_DIR.mkdir(exist_ok=True)
    return sorted(p.name for p in CAMPAIGNS_DIR.iterdir() if p.is_dir())


def save_upload(uploaded, dest_dir: Path) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / Path(uploaded.name).name
    dest.write_bytes(uploaded.getbuffer())
    return dest


def read_manifest(folder: Path) -> Tuple[List[Dict[str, str]], List[str]]:
    path = folder / MANIFEST
    if not path.exists():
        return [], []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        return list(reader), list(reader.fieldnames or [])


def load_sent(folder: Path) -> set:
    path = folder / SENT_LOG
    sent = set()
    if path.exists():
        with path.open("r", encoding="utf-8-sig", newline="") as f:
            for r in csv.DictReader(f):
                sent.add(((r.get("email") or "").strip().lower(), (r.get("filename") or "").strip()))
    return sent


def append_sent(folder: Path, record: Dict[str, str]) -> None:
    path = folder / SENT_LOG
    new = not path.exists()
    with path.open("a", encoding="utf-8-sig" if new else "utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=SENT_HEADERS)
        if new:
            writer.writeheader()
        writer.writerow({h: record.get(h, "") for h in SENT_HEADERS})


def render_text(text: str, row: Dict[str, str], escape_html: bool) -> str:
    """Reemplaza {{columna}} por el valor de la fila. Deja intactos los que no existan."""
    def repl(m: re.Match) -> str:
        key = m.group(1)
        if key not in row:
            return m.group(0)
        val = row.get(key) or ""
        return html.escape(val) if escape_html else val
    return PLACEHOLDER_RE.sub(repl, text)


def unresolved(text: str) -> List[str]:
    return sorted(set(PLACEHOLDER_RE.findall(text)))


def guess_email_column(columns: List[str]) -> int:
    for i, c in enumerate(columns):
        if c.strip().lower() in ("email", "correo", "e-mail", "correo electrónico", "correo electronico"):
            return i
    for i, c in enumerate(columns):
        low = c.lower()
        if "mail" in low or "correo" in low:
            return i
    return 0


def show_df(rows: List[Dict[str, str]], **kwargs) -> None:
    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True, **kwargs)


# ---------------------------------------------------------------------------
# Página: envío masivo
# ---------------------------------------------------------------------------

def campaign_selector() -> Path | None:
    st.subheader("Campaña")
    campaigns = list_campaigns()
    c1, c2 = st.columns([2, 2])
    with c1:
        options = ["➕ Nueva campaña"] + campaigns
        current = st.session_state.get("campana")
        idx = options.index(current) if current in options else 0
        choice = st.selectbox("Selecciona o crea una campaña", options, index=idx)
    if choice == "➕ Nueva campaña":
        with c2:
            name = st.text_input("Nombre de la nueva campaña", placeholder="ej. invitacion-evento-2026")
            if st.button("Crear campaña", type="primary", disabled=not name.strip()):
                slug = slugify(name.strip())
                (CAMPAIGNS_DIR / slug).mkdir(parents=True, exist_ok=True)
                st.session_state["campana"] = slug
                st.rerun()
        return None
    st.session_state["campana"] = choice
    folder = CAMPAIGNS_DIR / choice
    rows, _ = read_manifest(folder)
    sent = load_sent(folder)
    with c2:
        st.caption(f"Carpeta: `{folder}`")
        m1, m2, m3 = st.columns(3)
        m1.metric("En manifest", len(rows))
        m2.metric("Ya enviados", len(sent))
        m3.metric("Excluidos", len(list((folder / "excluidos").glob("*.docx"))) if (folder / "excluidos").exists() else 0)
    return folder


def tab_datos(folder: Path) -> None:
    st.markdown("Carga la base de destinatarios. Se sanean los correos y se crea el **manifest.csv** de la campaña.")

    origen = st.radio("Origen de los datos", ["Archivo de la carpeta data/", "Subir archivo"], horizontal=True)
    path: Path | None = None
    if origen == "Subir archivo":
        up = st.file_uploader("Excel, CSV o JSON", type=["xlsx", "xls", "xlsm", "csv", "json"])
        if up is not None:
            path = save_upload(up, folder / "_fuente")
    else:
        files = sorted(p for p in DATA_DIR.glob("*") if p.suffix.lower() in (".xlsx", ".xls", ".xlsm", ".csv", ".json"))
        if not files:
            st.info("No hay archivos en data/.")
        else:
            path = st.selectbox("Archivo", files, format_func=lambda p: p.name)
    if path is None:
        return

    sheet = None
    if path.suffix.lower() in (".xlsx", ".xls", ".xlsm"):
        try:
            sheet = st.selectbox("Hoja", list_excel_sheets(path))
        except DataLoadError as e:
            st.error(str(e))
            return
    try:
        rows, columns = load_records(path, sheet)
    except DataLoadError as e:
        st.error(str(e))
        return
    # Si la fuente es un manifest de otra campaña, sus columnas internas no se heredan
    columns = [c for c in columns if c not in INTERNAL_COLS]
    rows = [{k: v for k, v in r.items() if k not in INTERNAL_COLS} for r in rows]
    st.success(f"{len(rows)} registros · {len(columns)} columnas")

    email_col = st.selectbox("Columna con el correo del destinatario", columns, index=guess_email_column(columns))

    if st.checkbox("🧹 Sanear correos automáticamente", value=True,
                   help="Corrige errores de digitación: varios correos en un campo, '.gov.c', '.con', espacios, tildes…"):
        rows, report = sanitize_table(rows, email_col)
        if "emails_alternos" not in columns:
            columns.append("emails_alternos")
        if report:
            counts = pd.Series([r["estado"] for r in report]).value_counts().to_dict()
            st.info("Saneamiento: " + " · ".join(f"{k}: {v}" for k, v in counts.items()))
            with st.expander("Detalle del saneamiento"):
                show_df(report)
        else:
            st.caption("Todos los correos ya eran válidos.")

    invalid, duplicates = validate_rows(rows, email_col)
    c1, c2 = st.columns(2)
    with c1:
        with st.expander(f"⚠️ Sin correo o inválidos: {len(invalid)}"):
            show_df(invalid) if invalid else st.write("Ninguno")
    with c2:
        with st.expander(f"ℹ️ Correos repetidos: {len(duplicates)}"):
            st.caption("Entidades distintas que comparten correo. En el envío, ese correo recibe un solo mensaje "
                       "(salvo que cada fila tenga su propio documento).")
            show_df(duplicates) if duplicates else st.write("Ninguno")

    with st.expander("Vista previa de los datos"):
        show_df(rows[:50])

    st.divider()
    modo = st.radio(
        "¿Qué se adjunta?",
        ["Un mismo archivo para todos (ej. oficio PDF único)", "Un documento Word personalizado por destinatario"],
    )

    manifest_exists = (folder / MANIFEST).exists()
    if manifest_exists:
        st.warning("Esta campaña ya tiene manifest.csv: se sobrescribirá. El registro de enviados se conserva, "
                   "así que los ya enviados se seguirán saltando.")

    if modo.startswith("Un mismo"):
        st.caption("El adjunto fijo se sube en el paso **4. Enviar**.")
        if st.button("Preparar lista de destinatarios", type="primary"):
            res = write_manifest_only(rows, folder, email_col)
            st.success(f"Manifest creado: {res['ok']} destinatarios · {res['saltados']} sin correo válido omitidos.")
        return

    tpl_up = st.file_uploader("Plantilla Word (.docx) con {{PLACEHOLDERS}}", type=["docx"])
    if tpl_up is None:
        return
    template = save_upload(tpl_up, folder / "_plantilla")
    placeholders = extract_placeholders(template)
    if not placeholders:
        st.warning("La plantilla no contiene placeholders {{...}} (o están partidos por formato en Word).")
    mapping: Dict[str, Tuple[str, str]] = {}
    FIXED = "✏️ (texto fijo)"
    for ph in placeholders:
        c1, c2 = st.columns([1, 2])
        guess = guess_placeholder_column(ph, columns)
        opts = columns + [FIXED]
        sel = c1.selectbox(ph, opts, index=opts.index(guess) if guess else len(opts) - 1, key=f"map_{ph}")
        if sel == FIXED:
            mapping[ph] = (SOURCE_FIXED, c2.text_input(f"Texto para {ph}", key=f"fix_{ph}"))
        else:
            mapping[ph] = (SOURCE_COLUMN, sel)
            c2.caption(f"Ejemplo: {rows[0].get(sel, '') if rows else ''}")
    base_name = st.text_input("Nombre base de los archivos", value="OFICIO")
    fn_col = st.selectbox("Columna para identificar cada archivo (opcional)", ["(ninguna)"] + columns)
    skip = st.checkbox("No generar documento para filas sin correo válido", value=True)
    if st.button("Generar documentos", type="primary"):
        with st.spinner("Generando documentos…"):
            res = run_generic_generation(
                template, rows, folder, mapping, base_name=base_name, email_column=email_col,
                filename_column=None if fn_col == "(ninguna)" else fn_col, skip_rows_without_email=skip,
            )
        st.success(f"Generados: {res['ok']} · Fallidos: {res['fail']} · Saltados: {res['saltados']}")
        if res["errores"]:
            st.error("\n".join(res["errores"][:50]))


def tab_excluir(folder: Path) -> None:
    rows, fields = read_manifest(folder)
    if not rows:
        st.info("Primero prepara el manifest en el paso 1.")
        return
    st.markdown("Saca registros que **no** deben recibir el envío. No se borra nada: se mueven a `excluidos/` "
                "y quedan documentados en `excluidos/manifest_excluidos.csv`.")
    cols = [c for c in fields if c not in INTERNAL_COLS]
    c1, c2 = st.columns(2)
    primary = c1.selectbox("Columna principal", cols, index=cols.index("municipio") if "municipio" in cols else 0)
    sec_opts = ["(ninguna)"] + cols
    secondary = c2.selectbox("Columna secundaria (para desambiguar)", sec_opts,
                             index=sec_opts.index("departamento") if "departamento" in sec_opts else 0)
    columns = [primary] + ([] if secondary == "(ninguna)" else [secondary])

    text = st.text_area(f"Una línea por registro: {', '.join(columns)}", key="excl_text", height=180,
                        placeholder="Municipio Uno, Departamento\nMunicipio Dos, Departamento")
    filters = parse_exclusion_pairs(text, columns)
    if not filters:
        return
    matches = find_matches(rows, filters)
    st.write(f"**{len(matches)}** registros coinciden con {len(filters)} líneas:")
    show_df([{c: m.get(c, "") for c in cols[:8]} for m in matches])
    if st.button(f"Excluir {len(matches)} registros", type="primary", disabled=not matches):
        res = exclude_records(folder, filters)
        st.success(f"Excluidos: {res['excluidos']} · Quedan: {res['restantes']} de {res['total']}")


def tab_pdf(folder: Path) -> None:
    docs = sorted(folder.glob("*.docx"))
    pdf_dir = folder / "pdf"
    pdfs = list(pdf_dir.glob("*.pdf")) if pdf_dir.exists() else []
    if not docs:
        st.info("Esta campaña no tiene documentos Word generados (modo adjunto fijo): este paso no aplica.")
        return
    st.write(f"Word generados: **{len(docs)}** · PDF existentes: **{len(pdfs)}**")
    st.caption("La conversión usa Microsoft Word instalado en este PC. Cierra Word antes de empezar.")
    if st.button("Convertir a PDF", type="primary"):
        import pythoncom  # Word/COM necesita inicializarse en el hilo de Streamlit
        from diplomas.pdf_exporter import convert_and_encrypt

        pythoncom.CoInitialize()
        try:
            with st.spinner(f"Convirtiendo {len(docs)} documentos…"):
                convert_and_encrypt(folder, pdf_dir, None)
        finally:
            pythoncom.CoUninitialize()
        st.success(f"PDF en carpeta: {len(list(pdf_dir.glob('*.pdf')))}")


def _load_template_into_body(tpl_key: str, body_key: str) -> None:
    name = st.session_state.get(tpl_key)
    if name and name != "(escribir manualmente)":
        st.session_state[body_key] = (TEMPLATES_DIR / name).read_text(encoding="utf-8")


def load_mail_content(folder: Path) -> Dict[str, str]:
    path = folder / MAIL_CONTENT
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            pass
    return {}


def save_mail_content(folder: Path, subject: str, body: str) -> None:
    content = {"subject": subject, "body": body}
    if content != load_mail_content(folder):
        (folder / MAIL_CONTENT).write_text(json.dumps(content, ensure_ascii=False, indent=2), encoding="utf-8")


def tab_enviar(folder: Path) -> None:
    rows, fields = read_manifest(folder)
    rows = [r for r in rows if (r.get("_email") or "").strip()]
    if not rows:
        st.info("Primero prepara el manifest en el paso 1.")
        return
    data_cols = [c for c in fields if c not in INTERNAL_COLS]

    # --- Adjuntos ---------------------------------------------------------
    st.markdown("#### Adjuntos")
    fixed_dir = folder / "adjuntos"
    ups = st.file_uploader("Adjunto fijo para todos (ej. oficio en PDF)", accept_multiple_files=True)
    for up in ups or []:
        save_upload(up, fixed_dir)
    fixed_files = sorted(p for p in fixed_dir.glob("*") if p.is_file()) if fixed_dir.exists() else []
    if fixed_files:
        st.write("Adjuntos fijos: " + ", ".join(f"`{p.name}` ({p.stat().st_size / 1024:.0f} KB)" for p in fixed_files))
        if st.button("Quitar adjuntos fijos"):
            shutil.rmtree(fixed_dir)
            st.rerun()
    has_docs = any((r.get("_filename") or "").strip() for r in rows)
    per_row_pdf = st.checkbox("Adjuntar además el PDF individual de cada destinatario (carpeta pdf/)",
                              value=has_docs, disabled=not has_docs)
    total_mb = sum(p.stat().st_size for p in fixed_files) / 1024 / 1024
    if total_mb > 20:
        st.error(f"Los adjuntos fijos pesan {total_mb:.1f} MB: Gmail rechaza correos de más de 25 MB.")

    # --- Contenido --------------------------------------------------------
    st.markdown("#### Contenido del correo")
    with st.expander("Placeholders disponibles (columnas del manifest, sensibles a mayúsculas)"):
        st.code("  ".join("{{" + c + "}}" for c in data_cols))
    # Asunto y cuerpo son de cada campaña: nunca se heredan de otra
    subject_key, body_key, tpl_key = f"subject::{folder.name}", f"body::{folder.name}", f"tpl::{folder.name}"
    saved_mail = load_mail_content(folder)
    st.session_state.setdefault(subject_key, saved_mail.get("subject", ""))
    st.session_state.setdefault(body_key, saved_mail.get("body", ""))
    subject = st.text_input("Asunto", key=subject_key, placeholder="Escribe el asunto de esta campaña")
    templates = ["(escribir manualmente)"] + sorted(p.name for p in TEMPLATES_DIR.glob("*.html"))
    st.selectbox("Cargar plantilla HTML", templates, key=tpl_key, on_change=_load_template_into_body,
                 args=(tpl_key, body_key))
    body = st.text_area("Cuerpo del correo (HTML)", key=body_key, height=260)
    save_mail_content(folder, subject, body)

    # --- Filtro -----------------------------------------------------------
    with st.expander("Filtrar destinatarios (opcional)"):
        fcol = st.selectbox("Columna", ["(sin filtro)"] + data_cols)
        if fcol != "(sin filtro)":
            values = sorted({r.get(fcol, "") for r in rows})
            chosen = st.multiselect("Enviar solo a", values)
            if chosen:
                rows = [r for r in rows if r.get(fcol, "") in chosen]

    # --- Pendientes -------------------------------------------------------
    sent = load_sent(folder)
    pending, seen = [], set()
    already_sent = duplicated = 0
    for r in rows:
        key = (r["_email"].strip().lower(), (r.get("_filename") or "").strip())
        if key in sent:
            already_sent += 1
            continue
        if key in seen:
            duplicated += 1
            continue
        seen.add(key)
        pending.append(r)

    # --- Vista previa -----------------------------------------------------
    st.markdown("#### Vista previa")
    if pending or rows:
        sample_rows = pending or rows
        i = st.number_input("Registro", min_value=1, max_value=len(sample_rows), value=1) - 1
        r = sample_rows[i]
        subj_r = render_text(subject, r, escape_html=False)
        body_r = render_text(body, r, escape_html=True)
        st.write(f"**Para:** {r['_email']}  \n**Asunto:** {subj_r}")
        missing = unresolved(subj_r + body_r)
        if missing:
            st.error("Estos campos no existen en esta campaña: " + ", ".join(missing) + ". Corrígelos para poder enviar.")
        st.iframe(body_r, height=520)

    # --- Configuración de envío ---------------------------------------------
    st.markdown("#### Envío")
    accounts = [a for a in load_accounts(ACCOUNTS_FILE) if a.enabled]
    modo = st.radio("Cuenta de envío", ["Estación SMTP (rotación de cuentas)", "Cuenta única manual"],
                    index=0 if accounts else 1, horizontal=True)
    manual_cfg = None
    if modo.startswith("Estación"):
        if not accounts:
            st.error("No hay cuentas activas. Regístralas en ⚙️ Cuentas SMTP.")
            return
        pool_preview = SMTPPool(accounts, usage_path=USAGE_FILE)
        show_df(pool_preview.status())
        rem = pool_preview.total_remaining()
        st.caption(f"Cupo disponible hoy: {'sin límite' if rem is None else rem}")
    else:
        c1, c2, c3 = st.columns(3)
        server = c1.text_input("Servidor", "smtp.gmail.com")
        port = c2.number_input("Puerto", value=587)
        security = c3.selectbox("Seguridad", ["STARTTLS (587)", "SSL (465)"])
        user = c1.text_input("Usuario")
        password = c2.text_input("Contraseña (de aplicación)", type="password")
        sender = c3.text_input("Remitente (opcional)")
        manual_cfg = (server, int(port), user, password, security.startswith("STARTTLS"), sender or None,
                      security.startswith("SSL"))

    c1, c2, c3 = st.columns(3)
    delay = c1.number_input("Pausa entre correos (s)", min_value=0.0, value=3.0, step=0.5)
    jitter = c2.number_input("Variación aleatoria (± s)", min_value=0.0, value=1.0, step=0.5)
    cooldown = c3.number_input("Pausa si el servidor limita (s)", min_value=0.0, value=60.0, step=10.0)
    c1, c2, c3 = st.columns(3)
    limit = c1.number_input("Máximo a enviar en esta corrida (0 = todos)", min_value=0, value=0)
    dry_run = c2.checkbox("Simulación (no envía nada)", value=True)
    override_raw = c3.text_input("Modo prueba: enviar todo a estos correos", placeholder="tu@correo.com, colega@correo.com",
                                 help="Separa varios correos con coma. Cada mensaje de prueba llega a todos ellos.")
    test_list = [e.strip() for e in re.split(r"[,;\s]+", override_raw) if e.strip()]
    bad = [e for e in test_list if not re.fullmatch(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", e)]
    if bad:
        st.error("Correos de prueba inválidos: " + ", ".join(bad))
        return
    override = ", ".join(test_list)

    batch = pending[: int(limit)] if limit else pending
    st.info(f"Registros: {len(rows)} · Ya enviados (enviados.csv): {already_sent} · "
            f"Correo repetido (recibe un solo mensaje): {duplicated} · "
            f"**Pendientes en esta corrida: {len(batch)}**")

    real = not dry_run and not override.strip()
    confirm = True
    bad_fields = sorted(set(unresolved(subject + body)) - set(fields))
    if not subject.strip() or not body.strip():
        st.error("Falta el asunto o el cuerpo de esta campaña: no se puede enviar.")
        confirm = False
    elif bad_fields:
        st.error("No se puede enviar: estos campos no existen en esta campaña: " + ", ".join(bad_fields))
        confirm = False
    elif override.strip() and not 1 <= int(limit) <= 10:
        # Evita mandar el lote completo (cientos de mensajes) a los correos de prueba
        st.error("En modo prueba el **Máximo a enviar** debe estar entre 1 y 10.")
        confirm = False
    elif dry_run:
        st.caption("🧪 SIMULACIÓN: no se enviará ningún correo.")
    elif override.strip():
        st.warning(f"🧪 MODO PRUEBA: se enviarán {len(batch)} mensajes (cada uno con los datos de una ESE distinta), "
                   f"**todos a: {override}**. Ninguna ESE recibirá nada.")
    else:
        st.error(f"📨 ENVÍO REAL: cada una de las {len(batch)} ESEs recibirá **un solo correo, con sus propios datos, "
                 f"únicamente en su propia dirección**.")
        st.write(f"**Campaña:** {folder.name}  \n**Asunto:** {subject}  \n"
                 f"**Adjuntos:** {', '.join(p.name for p in fixed_files) or 'ninguno'}")
        confirm = st.checkbox(f"Confirmo el ENVÍO REAL a {len(batch)} destinatarios")
    if not st.button("🚀 Enviar", type="primary", disabled=not batch or not confirm):
        return

    # --- Ejecución --------------------------------------------------------
    if manual_cfg:
        server, port, user, password, tls, sender, ssl = manual_cfg
        svc = EmailService(SMTPConfig(server, port, user, password, use_tls=tls, email_from=sender, use_ssl=ssl,
                                      per_send_delay=delay, per_send_jitter=jitter, rate_limit_cooldown=cooldown))
        pool = None
    else:
        pool = SMTPPool(accounts, usage_path=USAGE_FILE, per_send_delay=delay, per_send_jitter=jitter,
                        rate_limit_cooldown=cooldown)

    progress = st.progress(0.0)
    log_box = st.empty()
    log: List[str] = []
    ok = fail = 0
    failed_rows: List[Dict[str, str]] = []

    def emit(line: str) -> None:
        log.append(line)
        log_box.code("\n".join(log[-200:]))

    for n, r in enumerate(batch, start=1):
        to = override.strip() or r["_email"].strip()
        subj_r = render_text(subject, r, escape_html=False)
        body_r = render_text(body, r, escape_html=True)
        attachments = list(fixed_files)
        fname = (r.get("_filename") or "").strip()
        if per_row_pdf and fname:
            pdf = folder / "pdf" / Path(fname).with_suffix(".pdf").name
            if pdf.exists():
                attachments.append(pdf)
            else:
                emit(f"⚠️ fila {n}: no existe {pdf.name}; se omite este destinatario")
                fail += 1
                failed_rows.append({**r, "motivo": "falta PDF individual"})
                continue

        if dry_run:
            emit(f"[SIMULACIÓN] {n}/{len(batch)} → {to} | {subj_r} | adjuntos={len(attachments)}")
            ok += 1
        else:
            try:
                if pool:
                    res = pool.send(to, subj_r, body_r, attachments=attachments)
                    success, cuenta, detalle = res.ok, res.account, res.detail
                else:
                    success, cuenta = svc.send(to, subj_r, body_r, attachments=attachments), "manual"
                    detalle = str(svc.last_error or "")
            except PoolExhaustedError as e:
                emit(f"⛔ {e}")
                st.warning(f"Cupos agotados. Quedan {len(batch) - n + 1} pendientes: vuelve a pulsar Enviar "
                           "mañana o con otra cuenta y retoma desde aquí.")
                break
            if success:
                ok += 1
                emit(f"OK {n}/{len(batch)} → {to} [vía {cuenta}]")
                if not override.strip():
                    append_sent(folder, {
                        "timestamp": datetime.now().isoformat(timespec="seconds"), "email": r["_email"].strip(),
                        "subject": subj_r, "filename": fname,
                        "adjuntos": "; ".join(p.name for p in attachments), "cuenta": cuenta,
                    })
            else:
                fail += 1
                failed = {"timestamp": datetime.now().isoformat(timespec="seconds"), **r, "motivo": "fallo SMTP",
                          "detalle": detalle, "modo": "prueba" if override.strip() else "real", "enviado_a": to}
                failed_rows.append(failed)
                # Se escribe al instante: si la corrida se detiene, el motivo del fallo no se pierde
                fpath_live = folder / "fallidos.csv"
                new_file = not fpath_live.exists()
                with fpath_live.open("a", encoding="utf-8-sig" if new_file else "utf-8", newline="") as fh:
                    w = csv.DictWriter(fh, fieldnames=list(failed.keys()), extrasaction="ignore")
                    if new_file:
                        w.writeheader()
                    w.writerow(failed)
                emit(f"❌ {n}/{len(batch)} → {to} falló: {detalle}")
        progress.progress(n / len(batch))

    if failed_rows:
        st.error(f"Fallidos: {fail} (detalle en `fallidos.csv`). Siguen pendientes: puedes reintentarlos pulsando Enviar de nuevo.")
    st.success(f"Terminado · OK: {ok} · Fallidos: {fail}" + (" · (simulación)" if dry_run else ""))


def page_envio() -> None:
    st.title("📨 Envío masivo")
    folder = campaign_selector()
    if folder is None:
        return
    st.divider()
    steps = {"1. Datos": tab_datos, "2. Excluir registros": tab_excluir,
             "3. Exportar PDF": tab_pdf, "4. Enviar correos": tab_enviar}
    step = st.radio("Paso", list(steps), horizontal=True, key="paso", label_visibility="collapsed")
    steps[step](folder)


# ---------------------------------------------------------------------------
# Página: cuentas SMTP
# ---------------------------------------------------------------------------

def page_cuentas() -> None:
    st.title("⚙️ Cuentas SMTP")
    st.caption("La estación usa las cuentas activas en orden: cada una envía hasta su límite diario y sigue la "
               "siguiente. Las contraseñas se guardan en texto plano en `smtp_accounts.json`: no compartas ese archivo.")
    accounts = load_accounts(ACCOUNTS_FILE)
    usage = get_today_usage(USAGE_FILE)
    if accounts:
        show_df([{
            "cuenta": a.name, "usuario": a.user, "servidor": f"{a.server}:{a.port}",
            "seguridad": "SSL" if a.use_ssl else ("STARTTLS" if a.use_tls else "ninguna"),
            "autenticación": "usuario" if a.require_auth else "IP (relay)",
            "remitente": a.email_from or a.user,
            "límite diario": a.daily_limit or "sin límite", "enviados hoy": usage.get(a.name, 0),
            "activa": "sí" if a.enabled else "no",
        } for a in accounts])
    else:
        st.info("Aún no hay cuentas registradas.")

    names = [a.name for a in accounts]
    sel = st.selectbox("Editar cuenta", ["➕ Nueva cuenta"] + names)
    existing = next((a for a in accounts if a.name == sel), None)
    preset_name = st.selectbox("Proveedor", list(SMTP_PRESETS), disabled=existing is not None)
    p = SMTP_PRESETS[preset_name]

    if preset_name.startswith("Google Workspace – SMTP Relay") and not existing:
        st.info("**Relay de Workspace**: el remitente puede ser cualquier dirección de tu dominio (ej. noreply@) aunque "
                "no sea un usuario. Escribe tu dominio en *Nombre EHLO*. En *Sin login*, el relay debe tener autorizada la IP pública de este equipo; en "
                "*Usuario y contraseña*, usa un usuario real de Workspace con contraseña de aplicación y pon noreply@ "
                "como remitente visible.")
    elif preset_name.startswith("Google") and not existing:
        st.caption("Gmail/Workspace exige una **contraseña de aplicación** (requiere verificación en 2 pasos).")

    with st.form("cuenta"):
        c1, c2 = st.columns(2)
        name = c1.text_input("Nombre interno", value=existing.name if existing else "", disabled=existing is not None)
        server = c2.text_input("Servidor", value=existing.server if existing else p["server"])
        port = c1.number_input("Puerto", value=int(existing.port) if existing else p["port"])
        sec_opts = ["STARTTLS (587)", "SSL (465)"]
        security = c2.selectbox("Seguridad", sec_opts, index=1 if (existing.use_ssl if existing else p["use_ssl"]) else 0)
        needs_auth = existing.require_auth if existing else p["require_auth"]
        auth_mode = c1.selectbox("Autenticación", AUTH_OPTS, index=0 if needs_auth else 1)
        local_hostname = c2.text_input("Nombre EHLO (dominio)", value=existing.local_hostname if existing else p["local_hostname"],
                                       help="Con qué nombre se presenta este equipo al servidor. Para el relay de Google usa tu dominio.")
        user = c1.text_input("Usuario (correo)", value=existing.user if existing else "",
                             help="Con relay sin login, pon aquí la dirección remitente (ej. noreply@tudominio.com).")
        password = c2.text_input("Contraseña" + (" (vacío = conservar la actual)" if existing else ""), type="password",
                                 help="No se usa con relay sin login.")
        email_from = c1.text_input("Remitente visible", value=existing.email_from if existing else "",
                                   placeholder="Mi Organización <noreply@tudominio.com>")
        reply_to = c2.text_input("Responder a (Reply-To)", value=existing.reply_to if existing else "",
                                 placeholder="contacto@tudominio.com",
                                 help="Las respuestas de los destinatarios llegan aquí y no a noreply@.")
        daily = c1.number_input("Límite diario (0 = sin límite)", min_value=0,
                                value=int(existing.daily_limit) if existing else p["daily_limit"])
        enabled = c2.checkbox("Activa", value=existing.enabled if existing else True)
        saved = st.form_submit_button("Guardar", type="primary")

    if saved:
        final_name = existing.name if existing else name.strip()
        require_auth = auth_mode == AUTH_OPTS[0]
        if not final_name or not user.strip() or not server.strip():
            st.error("Nombre, usuario y servidor son obligatorios.")
        elif not existing and final_name in names:
            st.error("Ya existe una cuenta con ese nombre.")
        elif require_auth and not password and not (existing and existing.password):
            st.error("La contraseña es obligatoria cuando la cuenta usa usuario y contraseña.")
        else:
            acc = SMTPAccount(
                name=final_name, server=server.strip(), port=int(port), user=user.strip(),
                password=password or (existing.password if existing else ""),
                use_tls=security.startswith("STARTTLS"), use_ssl=security.startswith("SSL"),
                email_from=email_from.strip(), daily_limit=int(daily), enabled=enabled,
                require_auth=require_auth, local_hostname=local_hostname.strip(), reply_to=reply_to.strip(),
            )
            accounts = [a for a in accounts if a.name != final_name] + [acc]
            save_accounts(accounts, ACCOUNTS_FILE)
            st.success(f"Cuenta '{final_name}' guardada.")
            st.rerun()

    if existing:
        c1, c2, c3 = st.columns(3)
        if c1.button("🔌 Probar conexión"):
            with st.spinner("Conectando…"):
                ok, msg = test_account_connection(existing)
            (st.success if ok else st.error)(msg)
        if c2.button("⬆️ Subir prioridad") and names.index(existing.name) > 0:
            i = names.index(existing.name)
            accounts[i - 1], accounts[i] = accounts[i], accounts[i - 1]
            save_accounts(accounts, ACCOUNTS_FILE)
            st.rerun()
        if c3.button("🗑️ Eliminar cuenta"):
            save_accounts([a for a in accounts if a.name != existing.name], ACCOUNTS_FILE)
            st.rerun()


# ---------------------------------------------------------------------------
# Página: ayuda
# ---------------------------------------------------------------------------

def page_ayuda() -> None:
    st.title("ℹ️ Cómo usar")
    st.markdown("""
**Orden recomendado para una campaña**

1. **⚙️ Cuentas SMTP** → registra la(s) cuenta(s) de envío y pulsa *Probar conexión*.
2. **📨 Envío masivo** → crea una campaña (una carpeta por difusión).
3. **1. Datos** → elige la base (puedes probar con `ejemplos/destinatarios_ejemplo.csv`), revisa el saneamiento y prepara la lista.
   - *Mismo archivo para todos*: solo crea el manifest; el PDF se adjunta en el paso 4.
   - *Word por destinatario*: sube una plantilla con `{{PLACEHOLDERS}}` y mapea cada uno a una columna.
4. **2. Excluir** → pega los municipios/entidades que no deben recibir el correo.
5. **3. PDF** → solo si generaste Word por destinatario.
6. **4. Enviar** → adjunto, asunto, cuerpo y vista previa. Luego, **en este orden**:
   - Simulación (casilla marcada) para revisar el lote completo.
   - Modo prueba con tu correo y máximo 2–3 envíos.
   - Envío real: desmarca la simulación, deja vacío el modo prueba y confirma.

**Reanudar**: cada envío real queda en `enviados.csv` de la campaña. Si se corta o se agotan los cupos,
vuelve a pulsar *Enviar* y continúa con los pendientes sin duplicar.

**Placeholders del correo**: usan el nombre exacto de la columna del manifest, ej. `{{nombre}}`,
`{{entidad}}`. Los del Word son los que definiste al mapear la plantilla.
""")


PAGES = {"📨 Envío masivo": page_envio, "⚙️ Cuentas SMTP": page_cuentas, "ℹ️ Cómo usar": page_ayuda}
with st.sidebar:
    st.header("Difusión masiva")
    page = st.radio("Módulo", list(PAGES), label_visibility="collapsed")
PAGES[page]()
