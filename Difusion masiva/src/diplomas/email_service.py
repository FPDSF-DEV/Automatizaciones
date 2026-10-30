from __future__ import annotations

import smtplib
import socket
import time
import random
import logging
from pathlib import Path
from typing import Sequence, Optional, Dict
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email.mime.application import MIMEApplication
from email import encoders

log = logging.getLogger("diplomas")


def _ipv4_socket(host: str, port: int, timeout: float) -> socket.socket:
    """Conecta solo por IPv4 probando cada dirección del servidor."""
    last_error: OSError | None = None
    for family, kind, proto, _, addr in socket.getaddrinfo(host, port, socket.AF_INET, socket.SOCK_STREAM):
        sock = socket.socket(family, kind, proto)
        try:
            sock.settimeout(timeout)
            sock.connect(addr)
            return sock
        except OSError as e:
            last_error = e
            sock.close()
    raise last_error or OSError(f"Sin direcciones IPv4 para {host}")


class _SMTPv4(smtplib.SMTP):
    def _get_socket(self, host, port, timeout):
        return _ipv4_socket(host, port, timeout)


class _SMTPv4SSL(smtplib.SMTP_SSL):
    def _get_socket(self, host, port, timeout):
        return self.context.wrap_socket(_ipv4_socket(host, port, timeout), server_hostname=self._host)


class SMTPConfig:
    def __init__(
        self,
        server: str,
        port: int,
        user: str,
        password: str,
        use_tls: bool = True,
        email_from: str | None = None,
        use_ssl: bool = False,
        debug: bool = False,
        per_send_delay: float = 0.0,
        per_send_jitter: float = 0.0,
        rate_limit_cooldown: float = 0.0,
        require_auth: bool = True,
        local_hostname: str | None = None,
        reply_to: str | None = None,
        force_ipv4: bool = False,
    ):
        self.server = server
        self.port = port
        self.user = user
        self.password = password
        self.use_tls = use_tls
        self.use_ssl = use_ssl
        self.debug = debug
        self.email_from = email_from or user
        # Ritmo de envío (throttling)
        self.per_send_delay = max(0.0, float(per_send_delay or 0.0))
        self.per_send_jitter = max(0.0, float(per_send_jitter or 0.0))
        # Pausa adicional cuando el servidor responde con 4xx/rate-limit
        self.rate_limit_cooldown = max(0.0, float(rate_limit_cooldown or 0.0))
        # Relay SMTP (ej. smtp-relay.gmail.com) autorizado por IP: no hace login
        self.require_auth = require_auth
        # Nombre presentado en EHLO; los relays suelen rechazar el nombre del PC
        self.local_hostname = local_hostname or None
        self.reply_to = reply_to or None
        # Un relay autorizado por IP solo reconoce la IPv4 registrada; la IPv6 del equipo cambia
        self.force_ipv4 = force_ipv4


def open_smtp(config: SMTPConfig, timeout: int = 30) -> smtplib.SMTP:
    """Abre la conexión (SSL directo o STARTTLS) y autentica si la cuenta lo requiere."""
    if config.use_ssl:
        smtp_class = _SMTPv4SSL if config.force_ipv4 else smtplib.SMTP_SSL
    else:
        smtp_class = _SMTPv4 if config.force_ipv4 else smtplib.SMTP
    server = smtp_class(config.server, config.port, local_hostname=config.local_hostname, timeout=timeout)
    try:
        if config.debug:
            server.set_debuglevel(1)
        # EHLO antes de TLS
        server.ehlo()
        if config.use_tls and not config.use_ssl:
            server.starttls()
            # EHLO después de TLS
            server.ehlo()
        if config.require_auth:
            server.login(config.user, config.password)
    except Exception:
        try:
            server.quit()
        except Exception:
            pass
        raise
    return server


class EmailService:
    def __init__(self, config: SMTPConfig):
        self.config = config
        # Última excepción del envío más reciente (para que un pool pueda
        # distinguir fallos de cuenta, ej. autenticación, de fallos de destinatario)
        self.last_error: Exception | None = None

    def send(
        self,
        to: str,
        subject: str,
        html: str,
        attachments: Optional[Sequence[Path]] = None,
        retries: int = 3,
        retry_backoff: float = 1.5,
    ) -> bool:
        self.last_error = None
        if not to:
            log.warning("Email destino vacío; se omite")
            return False
        msg = MIMEMultipart()
        msg["From"] = self.config.email_from
        msg["To"] = to
        msg["Subject"] = subject
        if self.config.reply_to:
            msg["Reply-To"] = self.config.reply_to
        msg.attach(MIMEText(html, "html", "utf-8"))

        for att in attachments or []:
            if not att.exists():
                log.warning("Adjunto no existe: %s", att)
                continue
            
            # Leer el contenido del archivo
            with att.open("rb") as fh:
                file_data = fh.read()
            
            # Determinar el tipo MIME según la extensión
            suffix = att.suffix.lower()
            if suffix == ".pdf":
                part = MIMEApplication(file_data, Name=att.name)
                part['Content-Disposition'] = f'attachment; filename="{att.name}"'
            elif suffix in (".doc", ".docx"):
                part = MIMEApplication(file_data, Name=att.name)
                part['Content-Disposition'] = f'attachment; filename="{att.name}"'
            else:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(file_data)
                encoders.encode_base64(part)
                part.add_header("Content-Disposition", f'attachment; filename="{att.name}"')
            
            msg.attach(part)

        attempt = 0
        while attempt < retries:
            try:
                server = open_smtp(self.config)
                try:
                    server.send_message(msg)
                finally:
                    try:
                        server.quit()
                    except Exception:
                        pass
                log.info("Enviado a %s", to)
                # Throttle entre envíos exitosos (si está configurado)
                if self.config.per_send_delay > 0:
                    if self.config.per_send_jitter > 0:
                        jitter = random.uniform(-self.config.per_send_jitter, self.config.per_send_jitter)
                    else:
                        jitter = 0.0
                    time.sleep(max(0.0, self.config.per_send_delay + jitter))
                return True
            except Exception as e:  # noqa: BLE001
                self.last_error = e
                attempt += 1
                log.error("Fallo enviando a %s (intento %d/%d): %s", to, attempt, retries, e)
                # Un fallo de autenticación no se resuelve reintentando la misma cuenta
                if isinstance(e, smtplib.SMTPAuthenticationError):
                    break
                # Detección básica de rate-limit/errores 4xx temporales
                cooldown = 0.0
                try:
                    # SMTPResponseException tiene atributos smtp_code/smtp_error
                    code = getattr(e, "smtp_code", None)
                    err = getattr(e, "smtp_error", b"") or b""
                    err_l = (err.decode(errors="ignore") if isinstance(err, (bytes, bytearray)) else str(err)).lower()
                except Exception:
                    code = None
                    err_l = str(e).lower()

                is_temp_4xx = False
                if isinstance(code, int) and 400 <= code < 500:
                    is_temp_4xx = True
                if ("4.7.1" in err_l) or ("rate" in err_l and "limit" in err_l) or ("ratelimit" in err_l):
                    is_temp_4xx = True

                if is_temp_4xx and self.config.rate_limit_cooldown > 0:
                    cooldown = self.config.rate_limit_cooldown
                    log.warning("Respuesta temporal/Rate limit detectada (code=%s). Pausando %.1fs antes de reintentar...", code, cooldown)
                else:
                    cooldown = retry_backoff * attempt

                if attempt >= retries:
                    break
                time.sleep(max(0.0, cooldown))
        return False


def render_template(template_path: Path, context: Dict[str, str]) -> str:
    html = template_path.read_text(encoding="utf-8")
    for k, v in context.items():
        html = html.replace(f"{{{{{k}}}}}", v)
    return html


__all__ = ["SMTPConfig", "EmailService", "open_smtp", "render_template"]