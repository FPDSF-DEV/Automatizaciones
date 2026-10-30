from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


def _env(key: str, default: Optional[str] = None) -> Optional[str]:
    import os
    return os.getenv(key, default)


@dataclass(slots=True)
class Settings:
    template: Path
    excel: Path
    placeholder: str = "{{NOMBRE}}"  # mantiene compatibilidad, pero ahora se usan varios
    column: Optional[str] = None  # Deprecated: usar name_col o first/last
    start_row: int = 1
    limit: int = 0  # 0 => no limit
    outdir: Path = Path("output")
    dedupe: bool = True
    preserve_accents: bool = True
    concurrency: int = 1
    dry_run: bool = False
    verbose: int = 0
    fail_on_missing_placeholder: bool = False
    filename_pattern: str = "{index:03d}-{slug}.docx"
    # Nuevos parámetros
    name_col: Optional[str] = None
    id_col: Optional[str] = None
    intensity_hours: int = 120
    location: str = "Ciudad"
    start_date: Optional[str] = None  # formato YYYY-MM-DD (inicio del diplomado)
    # Si start_date no se pasa, se omitirá fecha inicial en el rango.
    first_name_col: Optional[str] = None  # Columna Nombres
    last_name_col: Optional[str] = None   # Columna Apellidos
    email_col: Optional[str] = None  # Columna Email

    def validate(self) -> None:
        if not self.template.exists():
            raise FileNotFoundError(f"Plantilla no encontrada: {self.template}")
        if not self.excel.exists():
            raise FileNotFoundError(f"Archivo Excel no encontrado: {self.excel}")
        if self.start_row < 1:
            raise ValueError("start_row debe ser >= 1")
        if self.concurrency < 1:
            raise ValueError("concurrency debe ser >= 1")
        if "{slug}" not in self.filename_pattern:
            raise ValueError("filename_pattern debe contener {slug}")
        # Validación de fecha
        if self.start_date:
            from datetime import datetime
            try:
                datetime.strptime(self.start_date, "%Y-%m-%d")
            except ValueError as e:
                raise ValueError("start_date debe tener formato YYYY-MM-DD") from e


def build_settings_from_cli() -> Settings:
    import typer

    def _version_callback(value: bool):
        if value:
            typer.echo("diplomas 0.1.0")
            raise typer.Exit()

    app = typer.Typer(add_completion=False, help="Generador masivo de diplomas")

    @app.callback()
    def main():
        """CLI principal"""
        ...

    @app.command()
    def generar(
        template: Path = typer.Option(..., exists=True, readable=True, help="Ruta a la plantilla DOCX"),
        excel: Path = typer.Option(..., exists=True, readable=True, help="Ruta al Excel"),
        placeholder: str = typer.Option("{{NOMBRE}}", help="(Obsoleto) Placeholder simple principal"),
        column: Optional[str] = typer.Option(None, help="(Obsoleto) Columna única de nombre"),
        name_col: Optional[str] = typer.Option(None, help="Columna de nombre completo (si no se usan first/last)"),
        first_name_col: Optional[str] = typer.Option(None, help="Columna de Nombres (para combinar)"),
        last_name_col: Optional[str] = typer.Option(None, help="Columna de Apellidos (para combinar)"),
        id_col: Optional[str] = typer.Option(None, help="Columna de Cédula / CC (exacto 'C.C:' en tu caso)"),
        start_row: int = typer.Option(1, min=1, help="Fila inicial (1-index)"),
        limit: int = typer.Option(0, help="Límite de filas (0 = sin límite)"),
        outdir: Path = typer.Option(Path("output"), help="Directorio de salida"),
        dedupe: bool = typer.Option(True, help="Eliminar duplicados exactos de nombre"),
        preserve_accents: bool = typer.Option(True, help="Preservar acentos en slug"),
        concurrency: int = typer.Option(1, min=1, help="Nivel de concurrencia (IO-bound)"),
        dry_run: bool = typer.Option(False, help="Simular sin escribir archivos"),
        verbose: int = typer.Option(0, "-v", count=True, help="Aumentar verbosidad (-v, -vv)"),
        fail_on_missing_placeholder: bool = typer.Option(False, help="Fallar si algún placeholder requerido no aparece"),
        filename_pattern: str = typer.Option("{index:03d}-{slug}.docx", help="Patrón de nombre de archivo"),
        intensity_hours: int = typer.Option(120, help="Horas de intensidad ({{INTENSIDAD}})"),
        location: str = typer.Option("Ciudad", help="Lugar ({{LUGAR}})"),
        start_date: Optional[str] = typer.Option(None, help="Fecha inicio (YYYY-MM-DD) para rango ({{FECHA_RANGO}})"),
        email_col: Optional[str] = typer.Option(None, help="Columna de Email"),
    ):
        settings = Settings(
            template=template,
            excel=excel,
            placeholder=placeholder,
            column=column,
            name_col=name_col,
            first_name_col=first_name_col,
            last_name_col=last_name_col,
            id_col=id_col,
            email_col=email_col,
            start_row=start_row,
            limit=limit,
            outdir=outdir,
            dedupe=dedupe,
            preserve_accents=preserve_accents,
            concurrency=concurrency,
            dry_run=dry_run,
            verbose=verbose,
            fail_on_missing_placeholder=fail_on_missing_placeholder,
            filename_pattern=filename_pattern,
            intensity_hours=intensity_hours,
            location=location,
            start_date=start_date,
        )
        settings.validate()
        from .generator import run_generation
        run_generation(settings)

    @app.command()
    def exportar_pdf(
        carpeta: Path = typer.Option(Path("output"), exists=True, help="Carpeta con DOCX generados"),
        manifest: Path = typer.Option(Path("output/manifest.csv"), exists=False, help="Manifest CSV (index, filename, nombre, cc)"),
        destino: Path = typer.Option(None, help="Carpeta destino PDFs (por defecto output/pdf)"),
    ):
        """Convierte DOCX a PDF y cifra usando la cédula (si disponible en manifest)."""
        from .pdf_exporter import convert_and_encrypt
        convert_and_encrypt(carpeta, destino, manifest)

    @app.command()
    def enviar_correos(
        manifest: Path = typer.Option(Path("output/manifest.csv"), exists=True, help="Manifest con emails (index, filename, nombre, cc, email)"),
        pdf_dir: Path = typer.Option(Path("output/pdf"), exists=True, help="Carpeta de PDFs cifrados"),
        template: Path = typer.Option(Path("src/diplomas/templates/email_diploma.html"), exists=True, help="Plantilla HTML correo"),
        subject: str = typer.Option("Tu Diploma", help="Asunto del correo"),
        smtp_server: str = typer.Option(..., envvar="SMTP_SERVER"),
        smtp_port: int = typer.Option(587, envvar="SMTP_PORT"),
        smtp_user: str = typer.Option(..., envvar="SMTP_USER"),
        smtp_password: str = typer.Option(..., envvar="SMTP_PASSWORD"),
        email_from: str = typer.Option(None, envvar="EMAIL_FROM", help="Remitente (por defecto SMTP_USER)"),
        use_tls: bool = typer.Option(True, envvar="SMTP_TLS"),
        dry_run: bool = typer.Option(False, help="Simular sin enviar"),
        limit: int = typer.Option(0, help="Limitar envíos (0 = todos)"),
    ):
        """Envía correos con el PDF adjunto a cada email del manifest."""
        import csv
        import logging
        from .email_service import SMTPConfig, EmailService, render_template

        log = logging.getLogger("diplomas")
        if not manifest.exists():
            raise typer.BadParameter(f"Manifest no encontrado: {manifest}")

        rows = []
        with manifest.open("r", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            missing_cols = {"filename", "nombre", "cc", "email"} - set(reader.fieldnames or [])
            if missing_cols:
                raise typer.BadParameter(f"Manifest carece columnas: {', '.join(missing_cols)}")
            for r in reader:
                if not r.get("email"):
                    continue
                rows.append(r)
        if limit > 0:
            rows = rows[:limit]
        log.info("Total correos a enviar: %d", len(rows))
        if not rows:
            raise typer.Exit()

        config = SMTPConfig(smtp_server, smtp_port, smtp_user, smtp_password, use_tls, email_from)
        service = EmailService(config)
        tpl = template
        sent = 0
        failed = 0
        for r in rows:
            context = {
                "NOMBRE": r.get("nombre", ""),
                "CC": r.get("cc", ""),
                "INTENSIDAD": "",  # opcional no está en manifest; se podría enriquecer
                "FECHA_RANGO": "",
            }
            html = render_template(tpl, context)
            pdf_path = pdf_dir / Path(r["filename"]).with_suffix(".pdf")
            attachments = [pdf_path] if pdf_path.exists() else []
            if not attachments:
                log.warning("No se encontró PDF para %s (%s)", r.get("nombre"), pdf_path)
            if dry_run:
                log.info("[DRY] Enviaría a %s adjuntos=%d", r.get("email"), len(attachments))
                sent += 1
                continue
            ok = service.send(r.get("email"), subject, html, attachments=attachments)
            if ok:
                sent += 1
            else:
                failed += 1
        log.info("Resumen envío -> OK: %d | Fallidos: %d", sent, failed)

    @app.command()
    def generar_oficios(
        template: Path = typer.Option(..., exists=True, help="Plantilla DOCX de oficio"),
        excel: Path = typer.Option(..., exists=True, help="Excel con hoja de oficios"),
        sheet_name: str = typer.Option(..., help="Nombre exacto de la hoja"),
        outdir: Path = typer.Option(Path("output_oficios"), help="Carpeta de salida"),
        start_row: int = typer.Option(1, min=1, help="Fila inicial (1-index)"),
        limit: int = typer.Option(0, help="Límite de filas (0=sin límite)"),
        verbose: int = typer.Option(0, "-v", count=True),
    ):
        """Genera cartas de invitación/oficios a partir de hoja y columnas A-G estándar."""
        from .oficios_generator import run_oficios_generation
        run_oficios_generation(template, excel, sheet_name, outdir, start_row, limit, verbose)

    @app.command()
    def enviar_oficios(
        correos_csv: Path = typer.Option(Path("output_oficios/correos_gerentes.csv"), help="CSV de correos válidos generado por oficios"),
        pdf_dir: Path = typer.Option(Path("output_oficios/pdf"), help="Carpeta con PDFs de oficios"),
        template: Path = typer.Option(Path("src/diplomas/templates/email_oficio.html"), help="Plantilla HTML del correo de oficio"),
        subject: str = typer.Option("Oficio", help="Asunto del correo"),
        smtp_server: str = typer.Option(..., envvar="SMTP_SERVER"),
        smtp_port: int = typer.Option(587, envvar="SMTP_PORT"),
        smtp_user: str = typer.Option(..., envvar="SMTP_USER"),
        smtp_password: str = typer.Option(..., envvar="SMTP_PASSWORD"),
        email_from: str = typer.Option(None, envvar="EMAIL_FROM", help="Remitente (por defecto SMTP_USER)"),
        use_tls: bool = typer.Option(True, envvar="SMTP_TLS", help="Usar STARTTLS (587)"),
        use_ssl: bool = typer.Option(False, envvar="SMTP_SSL", help="Usar SSL directo (465)"),
        smtp_debug: bool = typer.Option(False, envvar="SMTP_DEBUG", help="Activar trazas SMTP"),
        dry_run: bool = typer.Option(False, help="Simular sin enviar"),
        limit: int = typer.Option(0, help="Limitar envíos (0 = todos)"),
        verbose: int = typer.Option(0, "-v", count=True, help="Aumentar verbosidad (-v, -vv)"),
        override_to: Optional[str] = typer.Option(None, help="Enviar todos los correos a esta dirección (modo prueba)"),
    ):
        """Envía los oficios en PDF a los correos de gerentes usando la cuenta oficial (SMTP)."""
        import csv
        import logging
        import io
        from .email_service import SMTPConfig, EmailService, render_template
        from .utils.logging import setup_logging

        setup_logging(verbose)
        log = logging.getLogger("diplomas")
        if not correos_csv.exists():
            raise typer.BadParameter(f"CSV de correos no encontrado: {correos_csv}")
        if not pdf_dir.exists():
            raise typer.BadParameter(f"Carpeta de PDFs no encontrada: {pdf_dir}")
        if not template.exists():
            raise typer.BadParameter(f"Plantilla HTML no encontrada: {template}")

        registros = []
        # Lectura robusta: detectar codificación y delimitador (coma, punto y coma, tab, pipe)
        raw_bytes = correos_csv.read_bytes()
        decoded_text = None
        for enc in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
            try:
                decoded_text = raw_bytes.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        if decoded_text is None:
            raise typer.BadParameter("No se pudo decodificar el CSV (intente guardar como UTF-8)")
        sample = decoded_text[:4096]
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
        except Exception:
            # Heurística simple por presencia de separador
            if "\t" in sample:
                dialect = csv.excel_tab
            elif ";" in sample:
                dialect = csv.excel
                dialect.delimiter = ";"  # type: ignore[attr-defined]
            else:
                dialect = csv.excel
        reader = csv.DictReader(io.StringIO(decoded_text), dialect=dialect)
        fieldnames_lc = [fn.strip().lower() for fn in (reader.fieldnames or [])]
        required = {"email", "gerente", "hospital", "departamento", "municipio", "direccion", "telefono", "idx_primero", "filename_primero"}
        missing = required - set(fieldnames_lc)
        if missing:
            raise typer.BadParameter(f"CSV carece columnas: {', '.join(sorted(missing))}")
        for r in reader:
            # Normaliza claves a minúsculas/trim
            r_lc = { (k.strip().lower() if k else k): v for k, v in r.items() }
            if not r_lc.get("email"):
                continue
            registros.append(r_lc)
        if limit > 0:
            registros = registros[:limit]
        import typer as _ty
        _ty.echo(f"Total correos de gerentes a procesar: {len(registros)}")
        if override_to:
            _ty.echo(f"[PRUEBA] Override de destinatario activo: todos se enviarán a {override_to}")
        if dry_run:
            _ty.echo("[DRY-RUN] Simulación activada: no se enviará ningún correo.")
        log.info("Total correos de gerentes a enviar: %d", len(registros))
        if not registros:
            raise typer.Exit()

        # Si se selecciona SSL, típicamente el puerto es 465; si es TLS, 587.
        config = SMTPConfig(
            smtp_server,
            smtp_port,
            smtp_user,
            smtp_password,
            use_tls,
            email_from,
            use_ssl=use_ssl,
            debug=smtp_debug,
        )
        service = EmailService(config)

        enviados = 0
        fallidos = 0
        for r in registros:
            context = {
                "GERENTE": r.get("gerente", ""),
                "HOSPITAL": r.get("hospital", ""),
                "DEPARTAMENTO": r.get("departamento", ""),
                "MUNICIPIO": r.get("municipio", ""),
                "DIRECCION": r.get("direccion", ""),
                "TELEFONO": r.get("telefono", ""),
                # Composición por si la plantilla usa LUGAR_LINEA
                "LUGAR_LINEA": f"{r.get('departamento','')}, {r.get('municipio','')}.",
            }
            html = render_template(template, context)
            # Resolver PDF por idx_primero o por filename estandarizado
            # Usamos filename_primero, cambiando sufijo a .pdf
            pdf_name = Path(r.get("filename_primero", "")).with_suffix(".pdf").name
            pdf_path = pdf_dir / pdf_name
            attachments = [pdf_path] if pdf_path.exists() else []
            if not attachments:
                log.warning("No se encontró PDF para %s (%s)", r.get("email"), pdf_path)
            to_email = override_to or r.get("email")
            if dry_run:
                log.info("[DRY] Enviar a %s adjuntos=%d asunto=\"%s\"", to_email, len(attachments), subject)
                enviados += 1
                continue
            ok = service.send(to_email, subject, html, attachments=attachments)
            if ok:
                enviados += 1
            else:
                fallidos += 1
        resumen = f"Resumen envío oficios -> OK: {enviados} | Fallidos: {fallidos}"
        _ty.echo(resumen)
        log.info(resumen)

    app()
    raise typer.Exit()


def main_cli():  # Entry point console_script
    """Punto de entrada simplificado para pyproject."""
    build_settings_from_cli()


__all__ = ["Settings", "build_settings_from_cli", "main_cli"]
