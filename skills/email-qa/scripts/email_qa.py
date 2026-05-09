#!/usr/bin/env python3
"""Read test emails from Mailpit, Gmail, Mailosaur, or local .eml fixtures; emit JSON for QA agents."""

from __future__ import annotations

import argparse
import base64
import imaplib
import json
import os
import platform
import re
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from email import policy
from email.message import EmailMessage
from email.parser import BytesParser
from email.utils import parseaddr, parsedate_to_datetime
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Iterator


DEFAULT_EMAIL_QA_ENV_FILE = "~/.cursor/email-qa.env"


def _strip_shell_quotes(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        return value[1:-1]
    return value


def load_email_qa_env_file() -> Path | None:
    raw_path = os.environ.get("EMAIL_QA_ENV_FILE", DEFAULT_EMAIL_QA_ENV_FILE)
    if not raw_path.strip():
        return None
    path = Path(raw_path).expanduser()
    if not path.is_file():
        return None

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
        if not key or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
            continue
        os.environ.setdefault(key, _strip_shell_quotes(value))
    return path


def _timestamp_from_unknown_date(value: str) -> float | None:
    stripped = value.strip()
    if not stripped:
        return None
    try:
        iso = stripped.replace("Z", "+00:00")
        return datetime.fromisoformat(iso).timestamp()
    except ValueError:
        pass
    try:
        legacy = parsedate_to_datetime(stripped)
        return legacy.timestamp() if legacy else None
    except (TypeError, ValueError):
        pass
    return None


# ---------------------------------------------------------------------------
# HTML to text (minimal, for OTP search on HTML bodies)
# ---------------------------------------------------------------------------


class _HTMLStripper(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._chunks: list[str] = []

    def handle_data(self, data: str) -> None:
        self._chunks.append(data)

    def get_text(self) -> str:
        return "".join(self._chunks)


def strip_html(html: str) -> str:
    if not html:
        return ""
    p = _HTMLStripper()
    try:
        p.feed(html)
        p.close()
    except Exception:
        return re.sub(r"<[^>]+>", " ", html)
    return p.get_text()


# ---------------------------------------------------------------------------
# OTP / token extraction
# ---------------------------------------------------------------------------

_CONTEXT_WORDS = (
    r"otp|one[-\s]?time|verification(?:\s+code)?|login\s+code|access\s+code|"
    r"auth(?:entication)?\s+code|security\s+code|your\s+code|code|token|pin"
)

_RE_DIGIT_BLOCK = re.compile(r"\b(\d{6,8})\b")
_RE_CONTEXT_ALNUM = re.compile(
    rf"(?:{_CONTEXT_WORDS})[\s:#\-]*([A-Za-z0-9][A-Za-z0-9\-]{{3,63}})\b",
    re.IGNORECASE,
)
# Hyphenated codes e.g. LOGIN-OTP-9FZ2
_RE_HYPHEN_TOKEN = re.compile(r"\b(?:[A-Z0-9]{2,}(?:-[A-Z0-9]{2,})+)\b")
_RE_ISOLATED_ALNUM = re.compile(r"\b([A-Z0-9]{6,10})\b")
_STOPWORDS = frozenset(
    "code otp login token thank verify continue please enter your the and for"
    .split()
)


def extract_otp_candidates(text: str, html: str | None) -> list[str]:
    blob = (text or "").strip()
    if html:
        blob = blob + "\n" + strip_html(html)
    if not blob:
        return []

    found: list[str] = []
    seen: set[str] = set()

    def add(s: str) -> None:
        s = s.strip()
        if not s or s in seen:
            return
        sl = s.lower()
        if sl in _STOPWORDS and not any(ch.isdigit() for ch in s):
            return
        if all(c.isalpha() for c in s) and len(s) < 6:
            return
        seen.add(s)
        found.append(s)

    for m in _RE_DIGIT_BLOCK.finditer(blob):
        add(m.group(1))
    for m in _RE_CONTEXT_ALNUM.finditer(blob):
        add(m.group(1))
    for m in _RE_HYPHEN_TOKEN.finditer(blob):
        add(m.group(0))
    for m in _RE_ISOLATED_ALNUM.finditer(blob):
        g = m.group(1)
        if g.islower():
            continue
        if any(c.isdigit() for c in g) or (g.isupper() and len(g) >= 6):
            add(g)
    return found


_RE_HREF_URL = re.compile(
    r"(?i)\b(https?://[^\s<>\[\]()\"'`]+|mailto:[^\s<>\[\]()\"'`]+)"
)


def extract_magic_link_candidates(
    text: str,
    html: str | None,
    extra_hrefs: list[str] | None = None,
) -> list[str]:
    """Collect http(s) and mailto URLs for QA (deduped, ordered)."""
    found: list[str] = []
    seen: set[str] = set()

    def add(u: str) -> None:
        u = u.strip().rstrip(").,;]")
        if not u or u in seen:
            return
        seen.add(u)
        found.append(u)

    blob = (text or "") + "\n" + (html or "")
    for m in _RE_HREF_URL.finditer(blob):
        add(m.group(1))
    if html:
        for m in re.finditer(r'(?i)href\s*=\s*"([^"]+)"', html):
            add(m.group(1))
        for m in re.finditer(r"(?i)href\s*=\s*'([^']+)'", html):
            add(m.group(1))
    if extra_hrefs:
        for u in extra_hrefs:
            if isinstance(u, str) and u.strip():
                add(u)
    return found


def _body_matches_blob(text: str, html: str | None, body_sub: str | None) -> bool:
    if not body_sub:
        return True
    blob = ((text or "") + "\n" + (html or "")).lower()
    return body_sub.lower() in blob


# ---------------------------------------------------------------------------
# HTTP helpers (Mailpit)
# ---------------------------------------------------------------------------


def _http_get_json(url: str, timeout_s: float) -> Any:
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        raw = resp.read()
    return json.loads(raw.decode("utf-8", errors="replace"))


def _http_get_bytes(url: str, timeout_s: float) -> tuple[bytes, str | None]:
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        data = resp.read()
        ct = resp.headers.get("Content-Type")
    return data, ct


def _mailpit_base(raw: str) -> str:
    base = raw.rstrip("/")
    if not base.startswith("http://") and not base.startswith("https://"):
        base = "http://" + base
    return base


def _iter_mailpit_messages(obj: Any) -> list[dict[str, Any]]:
    if isinstance(obj, list):
        return [x for x in obj if isinstance(x, dict)]
    if isinstance(obj, dict):
        for key in ("messages", "Messages", "data", "items"):
            v = obj.get(key)
            if isinstance(v, list):
                return [x for x in v if isinstance(x, dict)]
    return []


def _addr_match(addr_field: Any, needle: str) -> bool:
    needle_l = needle.lower()

    def one(s: str) -> bool:
        return needle_l in s.lower()

    if isinstance(addr_field, str):
        _, e = parseaddr(addr_field)
        return one(addr_field) or one(e)
    if isinstance(addr_field, dict):
        for k in ("Address", "Email", "email", "address"):
            v = addr_field.get(k)
            if isinstance(v, str) and one(v):
                return True
        n = addr_field.get("Name")
        if isinstance(n, str) and one(n):
            return True
    if isinstance(addr_field, list):
        for item in addr_field:
            if _addr_match(item, needle):
                return True
    return False


def _message_to_list(field: Any) -> list[Any]:
    if field is None:
        return []
    if isinstance(field, list):
        return field
    return [field]


def _mailpit_full_matches(
    msg: dict[str, Any],
    to_sub: str | None,
    subject_sub: str | None,
    from_sub: str | None,
    body_sub: str | None = None,
) -> bool:
    if subject_sub:
        subj = str(msg.get("Subject") or msg.get("subject") or "")
        if subject_sub.lower() not in subj.lower():
            return False
    if from_sub:
        from_f = msg.get("From") or msg.get("from")
        if not _addr_match(from_f, from_sub) and from_sub.lower() not in str(
            from_f or ""
        ).lower():
            return False
    if to_sub:
        matched = False
        for key in ("To", "to", "Cc", "cc", "Bcc", "bcc"):
            for ent in _message_to_list(msg.get(key)):
                if _addr_match(ent, to_sub):
                    matched = True
                    break
            if matched:
                break
        if not matched:
            blob = json.dumps(msg, default=str).lower()
            if to_sub.lower() not in blob:
                return False
    if body_sub:
        text = str(msg.get("Text") or msg.get("text") or "")
        html_v = msg.get("HTML") or msg.get("Html") or msg.get("html")
        html_s = str(html_v) if html_v is not None else None
        if not _body_matches_blob(text, html_s, body_sub):
            return False
    return True


def _mailpit_matches_summary(
    summary: dict[str, Any],
    to_sub: str | None,
    subject_sub: str | None,
    from_sub: str | None,
) -> bool:
    if subject_sub:
        subj = str(summary.get("Subject") or summary.get("subject") or "")
        if subject_sub.lower() not in subj.lower():
            return False
    if from_sub:
        from_f = summary.get("From") or summary.get("from")
        if not _addr_match(from_f, from_sub) and from_sub.lower() not in str(
            from_f or ""
        ).lower():
            return False
    if to_sub:
        matched = False
        for key in ("To", "to", "Cc", "cc", "Bcc", "bcc"):
            for ent in _message_to_list(summary.get(key)):
                if _addr_match(ent, to_sub):
                    matched = True
                    break
            if matched:
                break
        if not matched:
            blob = json.dumps(summary, default=str).lower()
            if to_sub.lower() not in blob:
                return False
    return True


def _get_part_id(att: dict[str, Any]) -> str | None:
    for k in ("PartID", "PartId", "partID", "partId", "ID", "Id"):
        v = att.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return None


def _get_filename(att: dict[str, Any]) -> str:
    for k in ("FileName", "Filename", "filename", "Name", "name"):
        v = att.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return "attachment"


def _get_content_type(att: dict[str, Any], fallback: str | None) -> str:
    for k in ("ContentType", "Content-Type", "contentType", "MIME", "Mime"):
        v = att.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip().split(";")[0].strip()
    return fallback or "application/octet-stream"


def _safe_attachment_filename(filename: Any) -> str:
    safe = Path(str(filename or "")).name
    if safe in ("", ".", ".."):
        return "attachment"
    return safe


# ---------------------------------------------------------------------------
# Fixture (.eml) parsing
# ---------------------------------------------------------------------------


def _walk_parts(msg: EmailMessage) -> Iterator[EmailMessage]:
    if msg.is_multipart():
        for p in msg.iter_parts():
            yield from _walk_parts(p)
    else:
        yield msg


def _decode_payload(part: EmailMessage) -> tuple[str, str | None]:
    charset = part.get_content_charset() or "utf-8"
    try:
        raw = part.get_payload(decode=True)
    except Exception:
        payload = part.get_payload()
        raw = payload.encode(charset, errors="replace") if isinstance(payload, str) else b""
    if raw is None:
        text = part.get_content() or ""
        return text, part.get_content_type()
    try:
        text = raw.decode(charset, errors="replace")
    except LookupError:
        text = raw.decode("utf-8", errors="replace")
    return text, part.get_content_type()


def parse_eml_bytes(data: bytes) -> dict[str, Any]:
    parser = BytesParser(policy=policy.default)
    root = parser.parsebytes(data)
    if not isinstance(root, EmailMessage):
        raise ValueError("Invalid message")

    text_body = ""
    html_body = ""
    raw_attachments: list[tuple[str, bytes, str]] = []

    for part in _walk_parts(root):
        ctype = (part.get_content_type() or "").lower()
        disp = (part.get_content_disposition() or "").lower()
        filename = part.get_filename()
        if ctype == "text/plain" and not disp:
            t, _ = _decode_payload(part)
            if t:
                text_body = text_body + t if text_body else t
        elif ctype == "text/html" and not disp:
            t, _ = _decode_payload(part)
            if t:
                html_body = html_body + t if html_body else t
        elif disp == "attachment" or (filename and ctype not in ("text/plain", "text/html")):
            fn = filename or "attachment"
            raw = part.get_payload(decode=True)
            if not isinstance(raw, bytes):
                raw = b""
            raw_attachments.append((fn, raw, ctype or "application/octet-stream"))

    frm = root.get("From") or ""
    to = root.get("To") or ""
    subj = root.get("Subject") or ""
    date_hdr = root.get("Date") or ""
    date_iso = ""
    if date_hdr:
        try:
            dt = parsedate_to_datetime(date_hdr)
            if dt:
                date_iso = dt.isoformat()
        except Exception:
            date_iso = str(date_hdr)

    return {
        "subject": subj,
        "from": frm,
        "to": to,
        "date": date_iso,
        "text": text_body,
        "html": html_body or None,
        "rawAttachments": raw_attachments,
    }


def _save_fixture_attachments(
    raw_pairs: list[tuple[str, bytes, str]], out_dir: Path
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    out_dir.mkdir(parents=True, exist_ok=True)
    for fn, data, ctype in raw_pairs:
        safe = _safe_attachment_filename(fn)
        dest = out_dir / safe
        if dest.exists():
            stem = dest.stem
            dest = dest.with_name(f"{stem}_{abs(hash(data)) % 10_000_000}{dest.suffix}")
        dest.write_bytes(data)
        out.append(
            {
                "filename": safe,
                "path": str(dest.resolve()),
                "contentType": ctype,
                "sizeBytes": len(data),
            }
        )
    return out


# ---------------------------------------------------------------------------
# Mailpit: fetch matching message and optional attachments
# ---------------------------------------------------------------------------

def fetch_mailpit_message(
    base: str,
    to_sub: str | None,
    subject_sub: str | None,
    from_sub: str | None,
    body_sub: str | None,
    timeout_ms: int,
    poll_ms: int,
    download_attachments: bool,
    output_dir: Path | None,
) -> dict[str, Any]:
    base_u = _mailpit_base(base)
    timeout_s = max(0.5, timeout_ms / 1000.0)
    poll_s = max(0.05, min(5.0, poll_ms / 1000.0))
    deadline = time.monotonic() + timeout_s

    last_err: str | None = None
    while time.monotonic() < deadline:
        try:
            list_url = f"{base_u}/api/v1/messages?limit=500"
            data = _http_get_json(list_url, timeout_s=min(30.0, timeout_s))
        except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as e:
            last_err = str(e)
            time.sleep(poll_s)
            continue

        summaries = _iter_mailpit_messages(data)
        # Newest first (Mailpit returns newest first; if not, sort by Created if present)
        def sort_key(s: dict[str, Any]) -> float:
            for k in ("Created", "created", "Date", "date", "Time", "time"):
                v = s.get(k)
                if isinstance(v, (int, float)):
                    return float(v)
                if isinstance(v, str):
                    ts = _timestamp_from_unknown_date(v)
                    if ts is not None:
                        return ts
            return 0.0

        try:
            summaries.sort(key=sort_key, reverse=True)
        except Exception:
            pass

        for summary in summaries:
            if not _mailpit_matches_summary(summary, to_sub, subject_sub, from_sub):
                continue
            mid = summary.get("ID") or summary.get("Id") or summary.get("id")
            if not mid:
                continue
            mid_s = str(mid)
            msg_url = f"{base_u}/api/v1/message/{urllib.parse.quote(mid_s, safe='')}"
            try:
                full = _http_get_json(msg_url, timeout_s=min(30.0, timeout_s))
            except Exception as e:
                last_err = str(e)
                continue
            if not isinstance(full, dict):
                continue

            if not _mailpit_full_matches(full, to_sub, subject_sub, from_sub, body_sub):
                continue

            text = str(full.get("Text") or full.get("text") or "")
            html_v = full.get("HTML") or full.get("Html") or full.get("html")
            html = str(html_v) if html_v is not None else None

            subj_o = full.get("Subject") or summary.get("Subject") or ""
            from_o = full.get("From") or summary.get("From") or ""
            to_o = full.get("To") or summary.get("To") or ""
            date_o = full.get("Date") or summary.get("Created") or summary.get("Date") or ""

            atts_out: list[dict[str, Any]] = []
            att_list = full.get("Attachments") or full.get("attachments") or []
            if not isinstance(att_list, list):
                att_list = []

            out_dir = output_dir
            if download_attachments:
                if out_dir is None:
                    out_dir = Path(tempfile.mkdtemp(prefix="email_qa_attach_"))
                out_dir.mkdir(parents=True, exist_ok=True)

                for att in att_list:
                    if not isinstance(att, dict):
                        continue
                    pid = _get_part_id(att)
                    fn = _get_filename(att)
                    ctype = _get_content_type(att, None)
                    if not pid:
                        raise SystemExit(
                            "Mailpit attachment missing PartID; cannot download. "
                            f"Attachment metadata: {json.dumps(att, default=str)[:500]}"
                        )
                    part_url = (
                        f"{base_u}/api/v1/message/{urllib.parse.quote(mid_s, safe='')}"
                        f"/part/{urllib.parse.quote(pid, safe='')}"
                    )
                    try:
                        raw_b, resp_ct = _http_get_bytes(part_url, timeout_s=min(60.0, timeout_s))
                    except Exception as e:
                        raise SystemExit(f"Failed to download attachment {fn!r}: {e}") from e
                    if resp_ct:
                        ctype = resp_ct.split(";")[0].strip() or ctype
                    safe_fn = _safe_attachment_filename(fn)
                    dest = out_dir / safe_fn
                    if dest.exists():
                        dest = dest.with_name(f"{dest.stem}_{abs(hash(raw_b)) % 10_000_000}{dest.suffix}")
                    dest.write_bytes(raw_b)
                    atts_out.append(
                        {
                            "filename": safe_fn,
                            "path": str(dest.resolve()),
                            "contentType": ctype,
                            "sizeBytes": len(raw_b),
                        }
                    )

            otps = extract_otp_candidates(text, html)
            links = extract_magic_link_candidates(text, html)
            return {
                "subject": str(subj_o),
                "from": str(from_o) if not isinstance(from_o, (dict, list)) else json.dumps(from_o),
                "to": str(to_o) if not isinstance(to_o, (dict, list)) else json.dumps(to_o),
                "date": str(date_o),
                "text": text,
                "html": html,
                "otpCandidates": otps,
                "magicLinkCandidates": links,
                "attachments": atts_out,
                "backend": "mailpit",
            }

        time.sleep(poll_s)

    msg = "No matching Mailpit message found within timeout."
    if last_err:
        msg += f" Last error: {last_err}"
    raise SystemExit(msg)


def load_fixture_message(
    fixture_dir: Path,
    to_sub: str | None,
    subject_sub: str | None,
    from_sub: str | None,
    body_sub: str | None,
    download_attachments: bool,
    output_dir: Path | None,
) -> dict[str, Any]:
    if not fixture_dir.is_dir():
        raise SystemExit(f"Fixture directory not found: {fixture_dir}")

    eml_files = sorted(fixture_dir.glob("*.eml"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not eml_files:
        raise SystemExit(f"No .eml files in {fixture_dir}")

    def matches(parsed: dict[str, Any]) -> bool:
        if subject_sub:
            if subject_sub.lower() not in (parsed.get("subject") or "").lower():
                return False
        if from_sub:
            f = parsed.get("from") or ""
            if from_sub.lower() not in f.lower():
                return False
        if to_sub:
            t = parsed.get("to") or ""
            if to_sub.lower() not in t.lower():
                return False
        if body_sub:
            if not _body_matches_blob(
                parsed.get("text") or "", parsed.get("html"), body_sub
            ):
                return False
        return True

    chosen: dict[str, Any] | None = None
    parse_errors = 0
    for path in eml_files:
        try:
            parsed = parse_eml_bytes(path.read_bytes())
        except Exception:
            parse_errors += 1
            continue
        if matches(parsed):
            chosen = parsed
            break

    if chosen is None:
        raise SystemExit(
            "No .eml fixture matched the filters. "
            f"Files tried: {len(eml_files)}; parse failures: {parse_errors}."
        )

    raw_atts: list[tuple[str, bytes, str]] = list(chosen.pop("rawAttachments", []))
    text = chosen["text"]
    html = chosen.get("html")
    otps = extract_otp_candidates(text, html)
    links = extract_magic_link_candidates(text, html)

    atts_out: list[dict[str, Any]] = []
    if download_attachments and raw_atts:
        out_dir = output_dir or Path(tempfile.mkdtemp(prefix="email_qa_attach_"))
        atts_out = _save_fixture_attachments(raw_atts, out_dir)

    return {
        "subject": chosen["subject"],
        "from": chosen["from"],
        "to": chosen["to"],
        "date": chosen["date"],
        "text": text,
        "html": html,
        "otpCandidates": otps,
        "magicLinkCandidates": links,
        "attachments": atts_out,
        "backend": "fixture",
    }


# ---------------------------------------------------------------------------
# Gmail IMAP (dedicated test inbox)
# ---------------------------------------------------------------------------


def _env_first(*names: str) -> str | None:
    for name in names:
        value = (os.environ.get(name) or "").strip()
        if value:
            return value
    return None


def _resolve_gmail_address(cli_value: str | None) -> str:
    value = (cli_value or "").strip() or _env_first(
        "EMAIL_QA_GMAIL_ADDRESS",
        "EMAIL_QA_GMAIL_USER",
        "GMAIL_ADDRESS",
    )
    if value:
        return value
    raise SystemExit(
        "Gmail address is missing. Set EMAIL_QA_GMAIL_ADDRESS in "
        f"{os.environ.get('EMAIL_QA_ENV_FILE', DEFAULT_EMAIL_QA_ENV_FILE)}."
    )


def _resolve_gmail_app_password(address: str) -> str:
    value = _env_first("EMAIL_QA_GMAIL_APP_PASSWORD", "GMAIL_APP_PASSWORD")
    if value:
        normalized = "".join(value.split())
        if normalized and "replace" not in normalized.lower():
            return normalized
    raise SystemExit(
        "Gmail app password is missing. Create a Google App Password for "
        f"{address}, then set EMAIL_QA_GMAIL_APP_PASSWORD in "
        f"{os.environ.get('EMAIL_QA_ENV_FILE', DEFAULT_EMAIL_QA_ENV_FILE)}. "
        "Do not use the normal Google account password."
    )


def _gmail_login(host: str, port: int, address: str, password: str) -> imaplib.IMAP4_SSL:
    try:
        client = imaplib.IMAP4_SSL(host, port)
    except OSError as e:
        raise SystemExit(f"Failed to connect to Gmail IMAP at {host}:{port}: {e}") from e
    try:
        client.login(address, password)
    except imaplib.IMAP4.error as e:
        try:
            client.logout()
        except Exception:
            pass
        detail = str(e)
        raise SystemExit(
            "Gmail IMAP login failed. Verify IMAP is enabled for the account and "
            "EMAIL_QA_GMAIL_APP_PASSWORD is a 16-character Google App Password. "
            f"Google response: {detail}"
        ) from e
    return client


def _gmail_select_mailbox(client: imaplib.IMAP4_SSL, mailbox: str) -> None:
    try:
        typ, data = client.select(mailbox, readonly=True)
    except imaplib.IMAP4.error as e:
        raise SystemExit(f"Failed to select Gmail mailbox {mailbox!r}: {e}") from e
    if typ != "OK":
        detail = data[0].decode("utf-8", errors="replace") if data else typ
        raise SystemExit(f"Failed to select Gmail mailbox {mailbox!r}: {detail}")


def _gmail_recent_uids(client: imaplib.IMAP4_SSL, limit: int) -> list[bytes]:
    typ, data = client.uid("search", None, "ALL")
    if typ != "OK":
        detail = data[0].decode("utf-8", errors="replace") if data else typ
        raise SystemExit(f"Failed to search Gmail mailbox: {detail}")
    raw = data[0] if data else b""
    uids = raw.split()
    if limit > 0:
        uids = uids[-limit:]
    return list(reversed(uids))


def _gmail_fetch_raw(client: imaplib.IMAP4_SSL, uid: bytes) -> bytes | None:
    typ, data = client.uid("fetch", uid, "(RFC822)")
    if typ != "OK":
        return None
    for item in data:
        if isinstance(item, tuple) and len(item) >= 2 and isinstance(item[1], bytes):
            return item[1]
    return None


def _gmail_message_matches(
    parsed: dict[str, Any],
    to_sub: str | None,
    subject_sub: str | None,
    from_sub: str | None,
    body_sub: str | None,
) -> bool:
    if subject_sub and subject_sub.lower() not in (parsed.get("subject") or "").lower():
        return False
    if from_sub and from_sub.lower() not in (parsed.get("from") or "").lower():
        return False
    if to_sub and to_sub.lower() not in (parsed.get("to") or "").lower():
        return False
    if body_sub:
        if not _body_matches_blob(parsed.get("text") or "", parsed.get("html"), body_sub):
            return False
    return True


def fetch_gmail_message(
    address: str | None,
    host: str,
    port: int,
    mailbox: str,
    recent_limit: int,
    to_sub: str | None,
    subject_sub: str | None,
    from_sub: str | None,
    body_sub: str | None,
    timeout_ms: int,
    poll_ms: int,
    download_attachments: bool,
    output_dir: Path | None,
) -> dict[str, Any]:
    resolved_address = _resolve_gmail_address(address)
    password = _resolve_gmail_app_password(resolved_address)
    timeout_s = max(0.5, timeout_ms / 1000.0)
    poll_s = max(0.05, min(5.0, poll_ms / 1000.0))
    deadline = time.monotonic() + timeout_s
    last_err: str | None = None

    while time.monotonic() < deadline:
        client: imaplib.IMAP4_SSL | None = None
        try:
            client = _gmail_login(host, port, resolved_address, password)
            _gmail_select_mailbox(client, mailbox)
            for uid in _gmail_recent_uids(client, recent_limit):
                raw = _gmail_fetch_raw(client, uid)
                if not raw:
                    continue
                try:
                    parsed = parse_eml_bytes(raw)
                except Exception as e:
                    last_err = f"failed to parse Gmail message UID {uid!r}: {e}"
                    continue
                if not _gmail_message_matches(
                    parsed, to_sub, subject_sub, from_sub, body_sub
                ):
                    continue

                raw_atts: list[tuple[str, bytes, str]] = list(
                    parsed.pop("rawAttachments", [])
                )
                text = parsed.get("text") or ""
                html = parsed.get("html")
                atts_out: list[dict[str, Any]] = []
                if download_attachments and raw_atts:
                    out_dir = output_dir or Path(
                        tempfile.mkdtemp(prefix="email_qa_attach_")
                    )
                    atts_out = _save_fixture_attachments(raw_atts, out_dir)

                return {
                    "subject": parsed.get("subject") or "",
                    "from": parsed.get("from") or "",
                    "to": parsed.get("to") or "",
                    "date": parsed.get("date") or "",
                    "text": text,
                    "html": html,
                    "otpCandidates": extract_otp_candidates(text, html),
                    "magicLinkCandidates": extract_magic_link_candidates(text, html),
                    "attachments": atts_out,
                    "backend": "gmail",
                }
        except SystemExit:
            raise
        except (imaplib.IMAP4.error, OSError, TimeoutError) as e:
            last_err = str(e)
        finally:
            if client is not None:
                try:
                    client.close()
                except Exception:
                    pass
                try:
                    client.logout()
                except Exception:
                    pass

        time.sleep(poll_s)

    msg = "No matching Gmail message found within timeout."
    if last_err:
        msg += f" Last error: {last_err}"
    raise SystemExit(msg)


# ---------------------------------------------------------------------------
# Mailosaur (hosted test inbox)
# ---------------------------------------------------------------------------


def _macos_keychain_read_password(
    *,
    service: str,
    account: str | None = None,
) -> str | None:
    if platform.system() != "Darwin":
        return None
    if account:
        cmd = ["security", "find-generic-password", "-a", account, "-s", service, "-w"]
    else:
        cmd = ["security", "find-generic-password", "-s", service, "-w"]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
    except (OSError, subprocess.SubprocessError):
        return None
    if p.returncode != 0:
        return None
    out = (p.stdout or "").strip()
    return out if out else None


def _resolve_mailosaur_api_key() -> str:
    k = (os.environ.get("MAILOSAUR_API_KEY") or "").strip()
    if k:
        return k
    if platform.system() == "Darwin":
        for svc in ("cursor-email-qa-mailosaur-api-key", "mailosaur-api-key"):
            got = _macos_keychain_read_password(service=svc)
            if got:
                return got.strip()
    raise SystemExit(
        "Mailosaur API key is missing. Set MAILOSAUR_API_KEY, or on macOS store the "
        "secret in Keychain (services tried: cursor-email-qa-mailosaur-api-key, "
        "mailosaur-api-key). Example:\n"
        "  security add-generic-password -s cursor-email-qa-mailosaur-api-key "
        '-a mailosaur -w "YOUR_KEY"\n'
        "Use a server-restricted key from the Mailosaur dashboard. "
        "See skills/email-qa/SKILL.md."
    )


def _resolve_mailosaur_server_id() -> str:
    for env_name in ("MAILOSAUR_SERVER_ID", "MAILOSAUR_SERVER"):
        v = (os.environ.get(env_name) or "").strip()
        if v:
            return v
    if platform.system() == "Darwin":
        for svc in ("cursor-email-qa-mailosaur-server-id", "mailosaur-server-id"):
            got = _macos_keychain_read_password(service=svc)
            if got:
                return got.strip()
    raise SystemExit(
        "Mailosaur server id is missing. Set MAILOSAUR_SERVER_ID or MAILOSAUR_SERVER "
        "(non-secret inbox id), or store it in Keychain (services tried: "
        "cursor-email-qa-mailosaur-server-id, mailosaur-server-id). "
        "Send mail to anything@<serverId>.mailosaur.net. "
        "See skills/email-qa/SKILL.md."
    )


def _mailosaur_normalize_base_url(raw: str) -> str:
    base = raw.strip().rstrip("/")
    if not base.startswith("http://") and not base.startswith("https://"):
        base = "https://" + base
    return base


def _mailosaur_api_root(base_url: str) -> str:
    return _mailosaur_normalize_base_url(base_url).rstrip("/") + "/api"


def _mailosaur_basic_auth_value(api_key: str) -> str:
    # Mailosaur SDKs authenticate with the API key as the username and an empty
    # password. Some curl examples show a literal "api" username; do not use it.
    tok = base64.b64encode(f"{api_key}:".encode("ascii")).decode("ascii")
    return f"Basic {tok}"


def _mailosaur_format_http_error(code: int, raw: bytes) -> str:
    msg = f"HTTP {code}"
    try:
        j = json.loads(raw.decode("utf-8", errors="replace"))
        if isinstance(j, dict) and j.get("message"):
            msg += f": {j['message']}"
            mtype = j.get("type")
            if mtype:
                msg += f" ({mtype})"
    except json.JSONDecodeError:
        if raw:
            msg += f": {raw[:400]!r}"
    return msg


def _mailosaur_request_json(
    method: str,
    api_root: str,
    path: str,
    api_key: str,
    *,
    body_obj: Any | None = None,
    timeout_s: float,
) -> tuple[int, dict[str, str], Any | None, bytes]:
    url = api_root.rstrip("/") + path
    headers: dict[str, str] = {
        "Accept": "application/json",
        "Authorization": _mailosaur_basic_auth_value(api_key),
    }
    body_bytes: bytes | None = None
    if body_obj is not None:
        body_bytes = json.dumps(body_obj).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=body_bytes, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            raw = resp.read()
            hdrs = {k.lower(): v for k, v in resp.headers.items()}
            try:
                parsed = json.loads(raw.decode("utf-8", errors="replace"))
            except json.JSONDecodeError:
                parsed = None
            return resp.getcode(), hdrs, parsed, raw
    except urllib.error.HTTPError as e:
        raw = e.read() if e.fp else b""
        hdrs = {k.lower(): v for k, v in e.headers.items()}
        try:
            parsed = json.loads(raw.decode("utf-8", errors="replace"))
        except json.JSONDecodeError:
            parsed = None
        return e.code, hdrs, parsed, raw
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
        raise SystemExit(f"Mailosaur request failed ({url}): {e}") from e


def _mailosaur_get_bytes(
    api_root: str,
    path: str,
    api_key: str,
    timeout_s: float,
) -> tuple[int, str | None, bytes]:
    url = api_root.rstrip("/") + path
    headers = {"Authorization": _mailosaur_basic_auth_value(api_key)}
    req = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            return resp.getcode(), resp.headers.get("Content-Type"), resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.headers.get("Content-Type"), (e.read() if e.fp else b"")
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise SystemExit(f"Mailosaur download failed ({url}): {e}") from e


def _mailosaur_iter_summaries(obj: Any) -> list[dict[str, Any]]:
    if isinstance(obj, list):
        return [x for x in obj if isinstance(x, dict)]
    if isinstance(obj, dict):
        items = obj.get("items")
        if isinstance(items, list):
            return [x for x in items if isinstance(x, dict)]
    return []


def _mailosaur_plain(msg: dict[str, Any]) -> str:
    t = msg.get("text")
    if isinstance(t, dict):
        return str(t.get("body") or "")
    if t is None:
        return ""
    return str(t)


def _mailosaur_html_body(msg: dict[str, Any]) -> str | None:
    h = msg.get("html")
    if isinstance(h, dict):
        body = h.get("body")
        return str(body) if body is not None else None
    if h is None:
        return None
    return str(h)


def _mailosaur_extra_hrefs(msg: dict[str, Any]) -> list[str]:
    out: list[str] = []
    for key in ("html", "text"):
        block = msg.get(key)
        if isinstance(block, dict):
            for link in block.get("links") or []:
                if isinstance(link, dict):
                    href = link.get("href")
                    if isinstance(href, str) and href.strip():
                        out.append(href.strip())
    return out


def _mailosaur_format_addrs(entries: Any) -> str:
    if not entries:
        return ""
    if not isinstance(entries, list):
        return str(entries)
    parts: list[str] = []
    for ent in entries:
        if isinstance(ent, dict):
            e = ent.get("email") or ""
            n = ent.get("name")
            if e and n:
                parts.append(f"{n} <{e}>")
            elif e:
                parts.append(str(e))
            elif n:
                parts.append(str(n))
        else:
            parts.append(str(ent))
    return ", ".join(parts)


def _mailosaur_message_matches(
    msg: dict[str, Any],
    to_sub: str | None,
    subject_sub: str | None,
    from_sub: str | None,
    body_sub: str | None,
) -> bool:
    if subject_sub:
        subj = str(msg.get("subject") or "")
        if subject_sub.lower() not in subj.lower():
            return False
    if from_sub:
        parts: list[str] = []
        for ent in msg.get("from") or []:
            if isinstance(ent, dict):
                if ent.get("email"):
                    parts.append(str(ent["email"]))
                if ent.get("name"):
                    parts.append(str(ent["name"]))
            else:
                parts.append(str(ent))
        blob = " ".join(parts).lower()
        if from_sub.lower() not in blob:
            return False
    if to_sub:
        parts_t: list[str] = []
        for key in ("to", "cc", "bcc"):
            for ent in msg.get(key) or []:
                if isinstance(ent, dict) and ent.get("email"):
                    parts_t.append(str(ent["email"]))
        blob_t = " ".join(parts_t).lower()
        if to_sub.lower() not in blob_t:
            return False
    if body_sub:
        plain = _mailosaur_plain(msg)
        html_b = _mailosaur_html_body(msg)
        if not _body_matches_blob(plain, html_b, body_sub):
            return False
    return True


def fetch_mailosaur_message(
    base_url: str,
    to_sub: str | None,
    subject_sub: str | None,
    from_sub: str | None,
    body_sub: str | None,
    timeout_ms: int,
    poll_ms: int,
    download_attachments: bool,
    output_dir: Path | None,
) -> dict[str, Any]:
    api_key = _resolve_mailosaur_api_key()
    server_id = _resolve_mailosaur_server_id()
    api_root = _mailosaur_api_root(base_url)

    timeout_s = max(0.5, timeout_ms / 1000.0)
    poll_s = max(0.05, min(5.0, poll_ms / 1000.0))
    deadline = time.monotonic() + timeout_s
    last_err: str | None = None

    while time.monotonic() < deadline:
        q = urllib.parse.urlencode({"server": server_id, "itemsPerPage": "200"})
        path = f"/messages?{q}"
        code, hdrs, data, raw = _mailosaur_request_json(
            "GET", api_root, path, api_key, timeout_s=min(30.0, timeout_s)
        )
        if code == 401 or code == 403:
            raise SystemExit(
                "Mailosaur authentication failed. Verify MAILOSAUR_API_KEY (or macOS "
                "Keychain item) is a valid API key for this account. "
                + _mailosaur_format_http_error(code, raw)
            )
        if code != 200:
            last_err = _mailosaur_format_http_error(code, raw)
            time.sleep(poll_s)
            continue

        delay_raw = hdrs.get("x-ms-delay")
        summaries = _mailosaur_iter_summaries(data)

        def sort_key(s: dict[str, Any]) -> float:
            for k in ("received", "created", "sent", "date", "receivedAt", "createdAt"):
                v = s.get(k)
                if isinstance(v, (int, float)):
                    return float(v)
                if isinstance(v, str):
                    ts = _timestamp_from_unknown_date(v)
                    if ts is not None:
                        return ts
            return 0.0

        try:
            summaries.sort(key=sort_key, reverse=True)
        except Exception:
            pass

        for summary in summaries:
            mid = summary.get("id")
            if not mid:
                continue
            mid_s = str(mid)
            path_m = f"/messages/{urllib.parse.quote(mid_s, safe='')}"
            code2, _, full, raw2 = _mailosaur_request_json(
                "GET", api_root, path_m, api_key, timeout_s=min(30.0, timeout_s)
            )
            if code2 != 200 or not isinstance(full, dict):
                last_err = _mailosaur_format_http_error(code2, raw2)
                continue

            mtype = full.get("type")
            if isinstance(mtype, str) and mtype.lower() not in ("email",):
                continue

            if not _mailosaur_message_matches(
                full, to_sub, subject_sub, from_sub, body_sub
            ):
                continue

            text = _mailosaur_plain(full)
            html_raw = _mailosaur_html_body(full)
            html_out = html_raw if html_raw else None
            extra_h = _mailosaur_extra_hrefs(full)
            otps = extract_otp_candidates(text, html_out)
            links = extract_magic_link_candidates(text, html_out, extra_h)

            atts_out: list[dict[str, Any]] = []
            out_dir = output_dir
            att_list = full.get("attachments") or []
            if not isinstance(att_list, list):
                att_list = []

            if download_attachments and att_list:
                if out_dir is None:
                    out_dir = Path(tempfile.mkdtemp(prefix="email_qa_attach_"))
                out_dir.mkdir(parents=True, exist_ok=True)

                for att in att_list:
                    if not isinstance(att, dict):
                        continue
                    aid = att.get("id")
                    fn = att.get("fileName") or "attachment"
                    ctype = str(att.get("contentType") or "application/octet-stream")
                    if not aid:
                        raise SystemExit(
                            "Mailosaur attachment missing id; cannot download. "
                            f"Metadata (truncated): {json.dumps(att, default=str)[:500]}"
                        )
                    path_a = f"/files/attachments/{urllib.parse.quote(str(aid), safe='')}"
                    cta, ct_hdr, raw_b = _mailosaur_get_bytes(
                        api_root, path_a, api_key, timeout_s=min(60.0, timeout_s)
                    )
                    if cta != 200:
                        raise SystemExit(
                            f"Failed to download attachment {fn!r}: "
                            f"{_mailosaur_format_http_error(cta, raw_b)}"
                        )
                    if ct_hdr:
                        ctype = ct_hdr.split(";")[0].strip() or ctype
                    assert out_dir is not None
                    safe_fn = _safe_attachment_filename(fn)
                    dest = out_dir / safe_fn
                    if dest.exists():
                        dest = dest.with_name(
                            f"{dest.stem}_{abs(hash(raw_b)) % 10_000_000}{dest.suffix}"
                        )
                    dest.write_bytes(raw_b)
                    atts_out.append(
                        {
                            "filename": safe_fn,
                            "path": str(dest.resolve()),
                            "contentType": ctype,
                            "sizeBytes": len(raw_b),
                        }
                    )

            return {
                "subject": str(full.get("subject") or ""),
                "from": _mailosaur_format_addrs(full.get("from")),
                "to": _mailosaur_format_addrs(full.get("to")),
                "date": str(full.get("received") or ""),
                "text": text,
                "html": html_out,
                "otpCandidates": otps,
                "magicLinkCandidates": links,
                "attachments": atts_out,
                "backend": "mailosaur",
            }

        if delay_raw:
            try:
                first = int(delay_raw.split(",")[0].strip())
                time.sleep(max(poll_s, min(5.0, first / 1000.0)))
            except (ValueError, IndexError):
                time.sleep(poll_s)
        else:
            time.sleep(poll_s)

    msg = "No matching Mailosaur message found within timeout."
    if last_err:
        msg += f" Last error: {last_err}"
    raise SystemExit(msg)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw.strip(), 10)
    except ValueError:
        return default


def main(argv: list[str] | None = None) -> int:
    load_email_qa_env_file()

    ap = argparse.ArgumentParser(
        description="Read test emails for QA (Mailpit, Gmail, Mailosaur, or .eml fixtures)."
    )
    ap.add_argument(
        "--backend",
        choices=("mailpit", "gmail", "mailosaur", "fixture"),
        help="Source backend (or EMAIL_QA_BACKEND).",
    )
    ap.add_argument("--to", dest="to_addr", metavar="ADDR", help="Match recipient (substring).")
    ap.add_argument("--subject-contains", dest="subject", help="Match subject substring.")
    ap.add_argument("--from-contains", dest="from_addr", help="Match From substring.")
    ap.add_argument(
        "--body-contains",
        dest="body",
        help="Match substring in plain/HTML body (all network backends and fixtures).",
    )
    ap.add_argument(
        "--timeout-ms",
        type=int,
        help="Max wait for a matching message (network backends). Default EMAIL_QA_TIMEOUT_MS or 60000.",
    )
    ap.add_argument(
        "--poll-ms",
        type=int,
        default=500,
        help="Poll interval in ms for network backends (default 500).",
    )
    ap.add_argument(
        "--mailpit-base",
        default=os.environ.get("EMAIL_QA_MAILPIT_BASE", "http://127.0.0.1:8025"),
        help="Mailpit HTTP base URL (default http://127.0.0.1:8025 or EMAIL_QA_MAILPIT_BASE).",
    )
    ap.add_argument(
        "--mailosaur-base",
        default=os.environ.get("MAILOSAUR_BASE_URL", "https://mailosaur.com"),
        help="Mailosaur API host (default https://mailosaur.com or MAILOSAUR_BASE_URL).",
    )
    ap.add_argument(
        "--gmail-address",
        default=os.environ.get("EMAIL_QA_GMAIL_ADDRESS"),
        help="Gmail test inbox address (default EMAIL_QA_GMAIL_ADDRESS).",
    )
    ap.add_argument(
        "--gmail-host",
        default=os.environ.get("EMAIL_QA_GMAIL_HOST", "imap.gmail.com"),
        help="Gmail IMAP host (default imap.gmail.com or EMAIL_QA_GMAIL_HOST).",
    )
    ap.add_argument(
        "--gmail-port",
        type=int,
        default=env_int("EMAIL_QA_GMAIL_PORT", 993),
        help="Gmail IMAP SSL port (default 993 or EMAIL_QA_GMAIL_PORT).",
    )
    ap.add_argument(
        "--gmail-mailbox",
        default=os.environ.get("EMAIL_QA_GMAIL_MAILBOX", "INBOX"),
        help="Gmail IMAP mailbox/label (default INBOX or EMAIL_QA_GMAIL_MAILBOX).",
    )
    ap.add_argument(
        "--gmail-recent-limit",
        type=int,
        default=env_int("EMAIL_QA_GMAIL_RECENT_LIMIT", 200),
        help="How many newest Gmail messages to inspect each poll (default 200).",
    )
    ap.add_argument(
        "--fixture-dir",
        type=Path,
        help="Directory of .eml files (or EMAIL_QA_FIXTURE_DIR).",
    )
    ap.add_argument(
        "--download-attachments",
        action="store_true",
        help="Save attachments to --output-dir or a temp directory.",
    )
    ap.add_argument(
        "--output-dir",
        type=Path,
        help="Directory for downloaded attachments.",
    )

    args = ap.parse_args(argv)

    backend = args.backend or os.environ.get("EMAIL_QA_BACKEND", "mailpit")
    if backend not in ("mailpit", "gmail", "mailosaur", "fixture"):
        raise SystemExit(f"Invalid backend: {backend!r}")

    timeout_ms = args.timeout_ms if args.timeout_ms is not None else env_int("EMAIL_QA_TIMEOUT_MS", 60_000)
    poll_ms = args.poll_ms if args.poll_ms is not None else 500

    output_dir = args.output_dir
    if output_dir:
        output_dir.mkdir(parents=True, exist_ok=True)

    fixture_dir = args.fixture_dir
    if fixture_dir is None:
        fd = os.environ.get("EMAIL_QA_FIXTURE_DIR")
        fixture_dir = Path(fd).expanduser() if fd else None

    if backend == "fixture":
        if fixture_dir is None:
            raise SystemExit("fixture backend requires --fixture-dir or EMAIL_QA_FIXTURE_DIR.")
        result = load_fixture_message(
            fixture_dir,
            args.to_addr,
            args.subject,
            args.from_addr,
            args.body,
            args.download_attachments,
            output_dir,
        )
    elif backend == "gmail":
        result = fetch_gmail_message(
            args.gmail_address,
            args.gmail_host,
            args.gmail_port,
            args.gmail_mailbox,
            args.gmail_recent_limit,
            args.to_addr,
            args.subject,
            args.from_addr,
            args.body,
            timeout_ms,
            poll_ms,
            args.download_attachments,
            output_dir,
        )
    elif backend == "mailosaur":
        result = fetch_mailosaur_message(
            args.mailosaur_base,
            args.to_addr,
            args.subject,
            args.from_addr,
            args.body,
            timeout_ms,
            poll_ms,
            args.download_attachments,
            output_dir,
        )
    else:
        result = fetch_mailpit_message(
            args.mailpit_base,
            args.to_addr,
            args.subject,
            args.from_addr,
            args.body,
            timeout_ms,
            poll_ms,
            args.download_attachments,
            output_dir,
        )

    sys.stdout.write(json.dumps(result, indent=2, ensure_ascii=False))
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
