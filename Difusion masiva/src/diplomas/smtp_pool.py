from __future__ import annotations

from dataclasses import dataclass, asdict, field
from datetime import date
from pathlib import Path
from typing import Dict, List, Optional, Sequence
import json
import logging
import smtplib

from email.utils import parseaddr

from .email_service import SMTPConfig, EmailService, open_smtp

log = logging.getLogger("diplomas")

DEFAULT_ACCOUNTS_FILE = Path("smtp_accounts.json")
DEFAULT_USAGE_FILE = Path("smtp_usage.json")


@dataclass
class SMTPAccount:
    """Una cuenta de la estación de envío. `daily_limit=0` significa sin límite."""

    name: str
    server: str
    port: int
    user: str
    password: str
    use_tls: bool = True
    use_ssl: bool = False
    email_from: str = ""
    daily_limit: int = 0
    enabled: bool = True
    # Relay SMTP: False = autorizado por IP, sin login (user/password se ignoran)
    require_auth: bool = True
    # Nombre para EHLO (ej. el dominio); vacío = nombre del equipo
    local_hostname: str = ""
    # Dirección a la que llegan las respuestas (útil con remitentes noreply@)
    reply_to: str = ""

    def to_config(
        self,
        per_send_delay: float = 0.0,
        per_send_jitter: float = 0.0,
        rate_limit_cooldown: float = 0.0,
    ) -> SMTPConfig:
        return SMTPConfig(
            self.server,
            int(self.port),
            self.user,
            self.password,
            use_tls=self.use_tls,
            email_from=self.email_from or self.user,
            use_ssl=self.use_ssl,
            per_send_delay=per_send_delay,
            per_send_jitter=per_send_jitter,
            rate_limit_cooldown=rate_limit_cooldown,
            require_auth=self.require_auth,
            local_hostname=self.local_hostname or None,
            reply_to=self.reply_to or None,
            force_ipv4=not self.require_auth,
        )


# ---------------------------------------------------------------------------
# Persistencia de cuentas y de uso diario
# ---------------------------------------------------------------------------

def load_accounts(path: Path = DEFAULT_ACCOUNTS_FILE) -> List[SMTPAccount]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        log.error("No se pudo leer %s: %s", path, e)
        return []
    accounts: List[SMTPAccount] = []
    for item in data if isinstance(data, list) else []:
        try:
            known = {f for f in SMTPAccount.__dataclass_fields__}
            accounts.append(SMTPAccount(**{k: v for k, v in item.items() if k in known}))
        except Exception as e:  # noqa: BLE001
            log.error("Cuenta inválida en %s: %s", path, e)
    return accounts


def save_accounts(accounts: Sequence[SMTPAccount], path: Path = DEFAULT_ACCOUNTS_FILE) -> None:
    path.write_text(
        json.dumps([asdict(a) for a in accounts], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def _load_usage(path: Path) -> Dict[str, Dict[str, int]]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:  # noqa: BLE001
        return {}


def get_today_usage(path: Path = DEFAULT_USAGE_FILE) -> Dict[str, int]:
    """Envíos realizados hoy por cada cuenta (persistente entre corridas)."""
    return _load_usage(path).get(date.today().isoformat(), {})


def _record_send(account_name: str, path: Path = DEFAULT_USAGE_FILE) -> None:
    data = _load_usage(path)
    today = date.today().isoformat()
    day = data.setdefault(today, {})
    day[account_name] = int(day.get(account_name, 0)) + 1
    # Conservar solo los últimos 30 días para que el archivo no crezca sin fin
    if len(data) > 30:
        for old_key in sorted(data.keys())[:-30]:
            del data[old_key]
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


# ---------------------------------------------------------------------------
# Pool con rotación automática
# ---------------------------------------------------------------------------

class PoolExhaustedError(Exception):
    """Todas las cuentas de la estación agotaron su cupo diario o fallaron."""


@dataclass
class PoolSendResult:
    ok: bool
    account: str = ""
    detail: str = ""


class SMTPPool:
    """Estación de cuentas SMTP con cupos diarios y rotación automática.

    Estrategia: usa las cuentas en el orden dado ("llenar y pasar a la
    siguiente"): la primera cuenta envía hasta agotar su cupo diario y se pasa
    a la siguiente. Si una cuenta falla repetidamente (auth, rate-limit
    persistente), se marca como caída para esta sesión y se rota sin detener
    el proceso. Los contadores se persisten en `usage_path`, así el cupo
    diario se respeta aunque cierres y vuelvas a abrir la app.
    """

    def __init__(
        self,
        accounts: Sequence[SMTPAccount],
        usage_path: Path = DEFAULT_USAGE_FILE,
        per_send_delay: float = 0.0,
        per_send_jitter: float = 0.0,
        rate_limit_cooldown: float = 0.0,
        retries_per_account: int = 2,
    ):
        self.accounts = [a for a in accounts if a.enabled]
        self.usage_path = usage_path
        self.per_send_delay = per_send_delay
        self.per_send_jitter = per_send_jitter
        self.rate_limit_cooldown = rate_limit_cooldown
        self.retries_per_account = max(1, retries_per_account)
        self._failed_session: set[str] = set()
        # Fallos consecutivos por cuenta: un destinatario malo no debe tumbar
        # una cuenta sana; solo fallos repetidos (o de autenticación) la marcan caída.
        self._strikes: Dict[str, int] = {}
        self.max_strikes = 2

    # Separado para poder simularlo en pruebas sin servidor real
    def _make_service(self, account: SMTPAccount) -> EmailService:
        return EmailService(
            account.to_config(
                per_send_delay=self.per_send_delay,
                per_send_jitter=self.per_send_jitter,
                rate_limit_cooldown=self.rate_limit_cooldown,
            )
        )

    def _sent_today(self, account: SMTPAccount) -> int:
        return int(get_today_usage(self.usage_path).get(account.name, 0))

    def remaining_quota(self, account: SMTPAccount) -> Optional[int]:
        """Cupo restante hoy; None si la cuenta no tiene límite."""
        if account.daily_limit <= 0:
            return None
        return max(0, account.daily_limit - self._sent_today(account))

    def status(self) -> List[Dict[str, object]]:
        """Estado de cada cuenta para mostrar en la UI."""
        rows = []
        for a in self.accounts:
            remaining = self.remaining_quota(a)
            rows.append({
                "cuenta": a.name,
                "usuario": a.user,
                "enviados_hoy": self._sent_today(a),
                "limite_diario": a.daily_limit or "sin límite",
                "restante_hoy": "sin límite" if remaining is None else remaining,
                "estado": "caída (esta sesión)" if a.name in self._failed_session else "disponible",
            })
        return rows

    def _next_account(self, exclude: Sequence[str] = ()) -> Optional[SMTPAccount]:
        for a in self.accounts:
            if a.name in self._failed_session or a.name in exclude:
                continue
            remaining = self.remaining_quota(a)
            if remaining is None or remaining > 0:
                return a
        return None

    def total_remaining(self) -> Optional[int]:
        """Cupo total restante hoy entre todas las cuentas sanas; None si alguna es ilimitada."""
        total = 0
        for a in self.accounts:
            if a.name in self._failed_session:
                continue
            remaining = self.remaining_quota(a)
            if remaining is None:
                return None
            total += remaining
        return total

    def send(
        self,
        to: str,
        subject: str,
        html: str,
        attachments: Optional[Sequence[Path]] = None,
    ) -> PoolSendResult:
        """Envía rotando entre cuentas.

        Un mismo destinatario se intenta con máximo 2 cuentas distintas: si
        falla con ambas, el problema es casi seguro del destinatario y se
        reporta como fallo de ese registro (las cuentas solo suman un strike).
        Una cuenta se marca caída con `max_strikes` fallos consecutivos o de
        inmediato ante un error de autenticación.

        Lanza PoolExhaustedError si no queda ninguna cuenta disponible.
        """
        tried: List[str] = []
        last_error = ""
        while len(tried) < 2:
            account = self._next_account(exclude=tried)
            if account is None:
                if not tried:
                    raise PoolExhaustedError(
                        "Todas las cuentas agotaron su cupo diario o fallaron. "
                        "El envío puede continuar mañana: el registro de enviados evita duplicados."
                    )
                break  # no hay segunda cuenta para reintentar este destinatario
            tried.append(account.name)
            service = self._make_service(account)
            ok = service.send(to, subject, html, attachments=attachments, retries=self.retries_per_account)
            if ok:
                self._strikes[account.name] = 0
                _record_send(account.name, self.usage_path)
                return PoolSendResult(ok=True, account=account.name)

            last_error = f"[{account.name}] {service.last_error}"
            if isinstance(service.last_error, smtplib.SMTPAuthenticationError):
                self._failed_session.add(account.name)
                log.warning("Cuenta '%s' con fallo de autenticación: marcada caída; rotando...", account.name)
                tried.pop()  # el destinatario no tuvo culpa; no le cuenta el intento
                continue

            self._strikes[account.name] = self._strikes.get(account.name, 0) + 1
            if self._strikes[account.name] >= self.max_strikes:
                self._failed_session.add(account.name)
                log.warning(
                    "Cuenta '%s' con %d fallos consecutivos: marcada caída para esta sesión; rotando...",
                    account.name, self._strikes[account.name],
                )
        return PoolSendResult(ok=False, account=tried[-1] if tried else "", detail=last_error or "fallo con las cuentas intentadas")


def test_account_connection(account: SMTPAccount, timeout: int = 15) -> tuple[bool, str]:
    """Verifica servidor + credenciales de una cuenta sin enviar ningún correo.

    Para un relay sin login (autorizado por IP) además pregunta al servidor si
    acepta al remitente (MAIL FROM + RSET), que es donde el relay rechaza una IP
    no autorizada; aun así no se envía ningún mensaje.
    """
    try:
        server = open_smtp(account.to_config(), timeout=timeout)
        try:
            if not account.require_auth:
                sender = parseaddr(account.email_from or account.user)[1]
                code, resp = server.mail(sender)
                server.rset()
                if code >= 400:
                    return False, f"El relay rechazó al remitente {sender}: {code} {resp.decode(errors='ignore')}"
        finally:
            try:
                server.quit()
            except Exception:  # noqa: BLE001
                pass
        if not account.require_auth:
            return True, "Conexión exitosa: el relay acepta este remitente desde esta IP"
        return True, "Conexión y autenticación exitosas"
    except smtplib.SMTPAuthenticationError as e:
        return False, f"Credenciales rechazadas: {e}"
    except Exception as e:  # noqa: BLE001
        return False, f"Error de conexión: {e}"


__all__ = [
    "SMTPAccount",
    "SMTPPool",
    "PoolSendResult",
    "PoolExhaustedError",
    "load_accounts",
    "save_accounts",
    "get_today_usage",
    "test_account_connection",
    "DEFAULT_ACCOUNTS_FILE",
    "DEFAULT_USAGE_FILE",
]
