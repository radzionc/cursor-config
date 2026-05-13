#!/usr/bin/env python3
"""Send email via SMTP using Cursor-managed local credentials; emit JSON."""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import re
import smtplib
import ssl
import sys
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import formataddr, getaddresses, make_msgid, parseaddr
from html.parser import HTMLParser
from pathlib import Path
from typing import Any


DEFAULT_ENV_FILE = "~/.cursor/email-qa.env"
DEFAULT_SMTP_HOST = "smtp.gmail.com"
DEFAULT_SMTP_PORT = 465
DEFAULT_MAX_MESSAGE_MB = 24.5


class EmailSendError(Exception):
    def __init__(self, message: str, **extra: Any) -> None:
        super().__init__(message)
        self.extra = extra


@dataclass(frozen=True)
class Address:
    display: str
    email: str

    @property
    def header(self) -> str:
        return formataddr((self.display, self.email)) if self.display else self.email


@dataclass(frozen=True)
class SmtpConfig:
    host: str
    port: int
    username: str
    password: str
    sender: Address


def _json(status: str, **data: Any) -> None:
    out = {"status": status}
    out.update(data)
    print(json.dumps(out, ensure_ascii=False))


def _strip_shell_quotes(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        return value[1:-1]
    return value


def load_env_file(raw_path: str | None) -> dict[str, str]:
    path = Path(raw_path or DEFAULT_ENV_FILE).expanduser()
    if not path.is_file():
        return {}

    env: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
            env[key] = _strip_shell_quotes(value)
    return env


def env_first(file_env: dict[str, str], *names: str) -> str:
    for name in names:
        value = os.environ.get(name)
        if value is not None and value.strip():
            return value.strip()
    for name in names:
        value = file_env.get(name)
        if value is not None and value.strip():
            return value.strip()
    return ""


def parse_int(value: str, name: str) -> int:
    try:
        return int(value)
    except ValueError as exc:
        raise EmailSendError(f"{name} must be an integer, got {value!r}.") from exc


def reject_header_injection(value: str, label: str) -> None:
    if "\r" in value or "\n" in value:
        raise EmailSendError(f"{label} cannot contain newlines.")


def parse_address(value: str, label: str) -> Address:
    reject_header_injection(value, label)
    display, email = parseaddr(value)
    email = email.strip()
    display = display.strip()
    if not email or "@" not in email or email.startswith("@") or email.endswith("@"):
        raise EmailSendError(f"Invalid {label}: {value!r}.")
    if any(ch.isspace() for ch in email):
        raise EmailSendError(f"Invalid {label}: email address contains whitespace.")
    return Address(display=display, email=email)


def parse_address_list(values: list[str] | None, label: str) -> list[Address]:
    if not values:
        return []
    joined = ", ".join(values)
    reject_header_injection(joined, label)
    parsed = getaddresses(values)
    out: list[Address] = []
    for display, email in parsed:
        raw = formataddr((display, email)) if display else email
        out.append(parse_address(raw, label))
    if not out:
        raise EmailSendError(f"No valid {label} addresses provided.")
    seen: set[str] = set()
    deduped: list[Address] = []
    for addr in out:
        key = addr.email.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(addr)
    return deduped


class _HTMLStripper(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        if data.strip():
            self.parts.append(data.strip())

    def get_text(self) -> str:
        return "\n".join(self.parts)


def html_to_text(html: str) -> str:
    parser = _HTMLStripper()
    try:
        parser.feed(html)
        parser.close()
        text = parser.get_text()
    except Exception:
        text = re.sub(r"<[^>]+>", " ", html)
    return text.strip()


def read_text_arg(value: str | None, path_value: str | None, label: str) -> str | None:
    if value is not None and path_value is not None:
        raise EmailSendError(f"Use either --{label} or --{label}-file, not both.")
    if value is not None:
        return value
    if path_value is None:
        return None
    path = Path(path_value).expanduser()
    if not path.is_file():
        raise EmailSendError(f"{label.title()} file not found: {path}")
    return path.read_text(encoding="utf-8")


def read_body(args: argparse.Namespace) -> tuple[str, str | None]:
    text = read_text_arg(args.body, args.body_file, "body")
    html = read_text_arg(args.html, args.html_file, "html")
    if text is None and not sys.stdin.isatty():
        text = sys.stdin.read()
    if text is None and html:
        text = html_to_text(html)
    if text is None or not text.strip():
        raise EmailSendError("Body is empty. Use --body, --body-file, --html, --html-file, or stdin.")
    if html is not None and not html.strip():
        raise EmailSendError("HTML body is empty.")
    return text, html


def resolve_smtp_config(args: argparse.Namespace, file_env: dict[str, str]) -> SmtpConfig:
    host = args.smtp_host or env_first(file_env, "EMAIL_SEND_SMTP_HOST", "SMTP_HOST") or DEFAULT_SMTP_HOST
    port_raw = str(args.smtp_port or env_first(file_env, "EMAIL_SEND_SMTP_PORT", "SMTP_PORT") or DEFAULT_SMTP_PORT)
    port = parse_int(port_raw, "SMTP port")

    username = args.smtp_user or env_first(
        file_env,
        "EMAIL_SEND_USERNAME",
        "EMAIL_SEND_USER",
        "EMAIL_QA_GMAIL_ADDRESS",
        "GMAIL_ADDRESS",
    )
    if not username:
        raise EmailSendError(
            "SMTP username is missing. Set EMAIL_SEND_USERNAME or EMAIL_QA_GMAIL_ADDRESS "
            f"in {args.env_file or DEFAULT_ENV_FILE}."
        )

    password = env_first(
        file_env,
        "EMAIL_SEND_PASSWORD",
        "EMAIL_SEND_APP_PASSWORD",
        "EMAIL_QA_GMAIL_APP_PASSWORD",
        "GMAIL_APP_PASSWORD",
    )
    if not args.dry_run and not password:
        raise EmailSendError(
            "SMTP password is missing. Set EMAIL_SEND_PASSWORD or EMAIL_QA_GMAIL_APP_PASSWORD "
            f"in {args.env_file or DEFAULT_ENV_FILE}. For Gmail, use a Google App Password."
        )
    password = "".join(password.split())
    if not args.dry_run and host.endswith("gmail.com") and len(password) < 16:
        raise EmailSendError("Gmail app password looks too short; expected a 16-character app password.")

    from_value = args.from_addr or env_first(file_env, "EMAIL_SEND_FROM", "EMAIL_QA_GMAIL_ADDRESS") or username
    sender = parse_address(from_value, "from address")
    if args.from_name:
        reject_header_injection(args.from_name, "from name")
        sender = Address(display=args.from_name, email=sender.email)

    return SmtpConfig(host=host, port=port, username=username, password=password, sender=sender)


def attach_files(msg: EmailMessage, paths: list[str] | None) -> list[dict[str, Any]]:
    attachments: list[dict[str, Any]] = []
    for raw in paths or []:
        path = Path(raw).expanduser()
        if not path.is_file():
            raise EmailSendError(f"Attachment not found: {path}")
        ctype, encoding = mimetypes.guess_type(str(path))
        if ctype is None or encoding is not None:
            ctype = "application/octet-stream"
        maintype, subtype = ctype.split("/", 1)
        data = path.read_bytes()
        msg.add_attachment(data, maintype=maintype, subtype=subtype, filename=path.name)
        attachments.append(
            {
                "filename": path.name,
                "contentType": ctype,
                "sizeBytes": len(data),
            }
        )
    return attachments


def build_message(
    args: argparse.Namespace,
    file_env: dict[str, str],
    smtp_config: SmtpConfig,
    to_addrs: list[Address],
    cc_addrs: list[Address],
    bcc_addrs: list[Address],
    text_body: str,
    html_body: str | None,
) -> tuple[EmailMessage, list[dict[str, Any]]]:
    reject_header_injection(args.subject, "subject")
    if not args.subject.strip():
        raise EmailSendError("Subject is empty.")

    msg = EmailMessage()
    msg["From"] = smtp_config.sender.header
    msg["To"] = ", ".join(addr.header for addr in to_addrs)
    if cc_addrs:
        msg["Cc"] = ", ".join(addr.header for addr in cc_addrs)
    reply_to_raw = args.reply_to or env_first(file_env, "EMAIL_SEND_REPLY_TO")
    if reply_to_raw:
        reply_to = parse_address_list([reply_to_raw], "reply-to")
        msg["Reply-To"] = ", ".join(addr.header for addr in reply_to)
    msg["Subject"] = args.subject
    msg["Message-ID"] = make_msgid(domain=smtp_config.sender.email.split("@", 1)[-1])
    msg.set_content(text_body)
    if html_body:
        msg.add_alternative(html_body, subtype="html")

    attachments = attach_files(msg, args.attach)
    return msg, attachments


def enforce_message_size(raw: bytes, max_mb: float) -> None:
    max_bytes = int(max_mb * 1024 * 1024)
    if len(raw) > max_bytes:
        raise EmailSendError(
            f"Message is too large ({len(raw)} bytes). Limit is {max_mb:g} MB; "
            "remove attachments or pass a higher --max-message-mb if your SMTP server allows it.",
            bytes=len(raw),
            maxBytes=max_bytes,
        )


def make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Send email via SMTP using Cursor-managed credentials.")
    parser.add_argument("--to", action="append", required=True, help="Recipient; repeat or comma-separate.")
    parser.add_argument("--cc", action="append", default=None, help="CC recipient; repeat or comma-separate.")
    parser.add_argument("--bcc", action="append", default=None, help="BCC recipient; repeat or comma-separate.")
    parser.add_argument("--subject", required=True)
    parser.add_argument("--body", default=None)
    parser.add_argument("--body-file", default=None)
    parser.add_argument("--html", default=None)
    parser.add_argument("--html-file", default=None)
    parser.add_argument("--attach", action="append", default=None, help="Attachment path; repeatable.")
    parser.add_argument("--reply-to", default=None)
    parser.add_argument("--from-addr", default=None, help="Override From address.")
    parser.add_argument("--from-name", default=None, help="Display name for the From header.")
    parser.add_argument("--env-file", default=os.environ.get("EMAIL_SEND_ENV_FILE") or os.environ.get("EMAIL_QA_ENV_FILE"))
    parser.add_argument("--smtp-host", default=None)
    parser.add_argument("--smtp-port", default=None)
    parser.add_argument("--smtp-user", default=None)
    parser.add_argument("--max-message-mb", type=float, default=DEFAULT_MAX_MESSAGE_MB)
    parser.add_argument("--dry-run", action="store_true", help="Validate and print metadata without sending.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = make_parser()
    args = parser.parse_args(argv)

    try:
        file_env = load_env_file(args.env_file)
        to_addrs = parse_address_list(args.to, "to")
        cc_addrs = parse_address_list(args.cc, "cc")
        bcc_addrs = parse_address_list(args.bcc, "bcc")
        text_body, html_body = read_body(args)
        smtp_config = resolve_smtp_config(args, file_env)
        msg, attachments = build_message(
            args,
            file_env,
            smtp_config,
            to_addrs,
            cc_addrs,
            bcc_addrs,
            text_body,
            html_body,
        )
        raw = bytes(msg)
        enforce_message_size(raw, args.max_message_mb)

        all_recipients = to_addrs + cc_addrs + bcc_addrs
        metadata = {
            "from": smtp_config.sender.header,
            "to": [addr.header for addr in to_addrs],
            "cc": [addr.header for addr in cc_addrs],
            "bcc": [addr.header for addr in bcc_addrs],
            "subject": args.subject,
            "message_id": msg["Message-ID"],
            "bytes": len(raw),
            "attachments": attachments,
        }

        if args.dry_run:
            _json("dry_run", **metadata)
            return 0

        context = ssl.create_default_context()
        try:
            with smtplib.SMTP_SSL(
                smtp_config.host,
                smtp_config.port,
                context=context,
                timeout=30,
            ) as smtp:
                smtp.login(smtp_config.username, smtp_config.password)
                refused = smtp.send_message(
                    msg,
                    from_addr=smtp_config.sender.email,
                    to_addrs=[addr.email for addr in all_recipients],
                )
        except smtplib.SMTPAuthenticationError as exc:
            detail = exc.smtp_error.decode("utf-8", "replace") if isinstance(exc.smtp_error, bytes) else str(exc.smtp_error)
            raise EmailSendError(f"SMTP authentication failed ({exc.smtp_code} {detail}).") from exc
        except (smtplib.SMTPException, ssl.SSLError, OSError) as exc:
            raise EmailSendError(f"SMTP send failed: {type(exc).__name__}: {exc}") from exc

        _json("sent", refused=list(refused.keys()) if refused else [], **metadata)
        return 0
    except EmailSendError as exc:
        _json("failed", error=str(exc), **exc.extra)
        return 1
    except Exception as exc:
        _json("failed", error=f"Unexpected error: {type(exc).__name__}.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
