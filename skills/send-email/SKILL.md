---
name: send-email
description: >-
  Sends outbound email from Cursor using local SMTP credentials, attachments,
  reply-to headers, dry-runs, and JSON results. Use when the user asks to send
  an email, email a hiring manager, send a resume or attachment, or verify an
  SMTP sending setup from any codebase.
---

# Send Email

Use this skill when an agent needs to send a real outbound email from any
workspace.

## Safety

- Do not send unless the recipient, subject, and body are explicit in the task
  or derived from a trusted workflow step.
- Use `--dry-run` first for new workflows, new recipients, or attachment-heavy
  messages. Inspect the JSON metadata before sending.
- Never print SMTP passwords or paste full private emails into public channels.
- Use `--reply-to` when the SMTP account is not the inbox that should receive
  replies.

## Helper Script

Path after sync: `~/.cursor/skills/send-email/scripts/send_email.py`.

Run with `python3`; the script uses only the Python standard library.

It returns JSON:

- `status: "dry_run"` after validation without sending.
- `status: "sent"` after SMTP accepts the message.
- `status: "failed"` with an actionable `error`.

## Credentials

The helper loads `~/.cursor/email-qa.env` by default, so it can reuse the Gmail
app password already maintained by cursor-config. Env vars override file values.

Supported variables:

- `EMAIL_SEND_USERNAME` or `EMAIL_QA_GMAIL_ADDRESS`: SMTP login username.
- `EMAIL_SEND_PASSWORD` or `EMAIL_QA_GMAIL_APP_PASSWORD`: SMTP password. For
  Gmail, use a Google App Password.
- `EMAIL_SEND_FROM`: optional From address override.
- `EMAIL_SEND_REPLY_TO`: optional default Reply-To.
- `EMAIL_SEND_SMTP_HOST`: optional SMTP host, default `smtp.gmail.com`.
- `EMAIL_SEND_SMTP_PORT`: optional SSL SMTP port, default `465`.
- `EMAIL_SEND_ENV_FILE`: optional env file override.

## Examples

Dry-run a plain-text message:

```bash
python3 ~/.cursor/skills/send-email/scripts/send_email.py \
  --to "person@example.com" \
  --subject "Quick note" \
  --body-file /tmp/email-body.txt \
  --dry-run
```

Send a job application with a resume and replies routed to the candidate:

```bash
python3 ~/.cursor/skills/send-email/scripts/send_email.py \
  --to "careers@example.com" \
  --subject "Application - Senior Frontend Engineer" \
  --body-file /tmp/cover-note.txt \
  --attach /path/to/resume.pdf \
  --reply-to "candidate@example.com"
```

Send HTML with a generated plain-text fallback:

```bash
python3 ~/.cursor/skills/send-email/scripts/send_email.py \
  --to "person@example.com" \
  --subject "HTML test" \
  --html-file /tmp/body.html
```

## Behavior

- `--to`, `--cc`, `--bcc`, and `--attach` are repeatable.
- Address flags may also contain comma-separated lists.
- Bcc recipients are included in the SMTP envelope but not written to message
  headers.
- `--body`, `--body-file`, stdin, `--html`, and `--html-file` are supported.
- Messages larger than `--max-message-mb` fail before SMTP. The default is
  `24.5`, below Gmail's typical 25 MB limit.

## Related

- `email-qa` reads received test emails, OTPs, magic links, and attachments.
  Keep receiving/verification flows there; keep outbound SMTP sends here.
