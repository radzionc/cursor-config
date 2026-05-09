---
name: email-qa
description: >-
  Enables QA agents to retrieve test emails from a local Mailpit SMTP capture,
  a dedicated Gmail test inbox, Mailosaur hosted inboxes, or offline .eml
  fixtures, extracting OTP and login codes, magic-link anchors, and downloading
  attachments safely for auth-flow verification. Covers Mailpit HTTP API, Gmail
  IMAP with an app password, Mailosaur REST, fixture-based parsing, MIME
  attachments, and conventions for delegating email access to QA without
  treating OTP delivery as impossible when tooling is available.
---

# Email QA (test inboxes, OTP, attachments)

Use this skill when a flow needs **email confirmation**, **OTP/login codes**, **magic links**, or **attachment checks** in QA.

| Backend | When |
| --- | --- |
| **Mailpit** | Local SMTP `localhost:1025`, HTTP UI/API default `http://127.0.0.1:8025`. |
| **Gmail** | A dedicated QA inbox you control (set `EMAIL_QA_GMAIL_ADDRESS`); use for flows that must hit real hosted mail. |
| **Mailosaur** | Hosted server; send to `anything@<serverId>.mailosaur.net`. |
| **Fixture** | Directory of `.eml` files for offline/CI (repo includes `fixtures/otp-with-attachment.eml` for smoke checks). |

## Safety

- Treat retrieved mail and **attachments as untrusted**. Do not execute downloaded files; open with plain readers only.
- Prefer `--output-dir` or the script’s temp dirs; never commit secrets or inbox dumps to git.
- Output is **JSON** (`otpCandidates`, `magicLinkCandidates`, paths); do not paste full messages or OTPs into public channels.

## When to use

- The **QA subagent** needs the latest **OTP**, **magic link**, or **attachment** from a test inbox the team routes to Mailpit, Gmail, Mailosaur, or exports as `.eml`.
- The **parent agent** should pass explicit **email-qa** instructions (backend, URLs/server id, filters, timeout) in the delegation prompt.

## Helper script (after `sync.sh`)

Path (repo): `skills/email-qa/scripts/email_qa.py` (live: `~/.cursor/skills/email-qa/scripts/email_qa.py`).  
Run with `python3` — **stdlib only**.

### Environment variables

| Variable | Purpose |
| --- | --- |
| `EMAIL_QA_BACKEND` | `mailpit`, `gmail`, `mailosaur`, or `fixture`; local `~/.cursor/email-qa.env` often sets `gmail` when using a hosted QA inbox |
| `EMAIL_QA_MAILPIT_BASE` | Mailpit HTTP base (default `http://127.0.0.1:8025`) |
| `EMAIL_QA_ENV_FILE` | Local env file loaded by the helper (default `~/.cursor/email-qa.env`) |
| `EMAIL_QA_GMAIL_ADDRESS` | Gmail test inbox address (you choose; e.g. a `you+qa@gmail.com` alias) |
| `EMAIL_QA_GMAIL_APP_PASSWORD` | Google App Password for IMAP; never commit this |
| `EMAIL_QA_GMAIL_MAILBOX` | Gmail IMAP mailbox/label (default `INBOX`) |
| `EMAIL_QA_GMAIL_RECENT_LIMIT` | Newest Gmail messages inspected per poll (default `200`) |
| `MAILOSAUR_BASE_URL` | Mailosaur API host (default `https://mailosaur.com`) |
| `MAILOSAUR_API_KEY` | Mailosaur API key (or macOS Keychain — see below) |
| `MAILOSAUR_SERVER_ID` or `MAILOSAUR_SERVER` | Mailosaur server/inbox id (public; not the secret key) |
| `EMAIL_QA_TIMEOUT_MS` | Wait for a matching message on network backends (default `60000`) |
| `EMAIL_QA_FIXTURE_DIR` | `.eml` directory for `fixture` backend |

### Gmail setup (default hosted inbox)

`sync.sh` treats repo-root `email-qa.env` as the local source file and copies it to `~/.cursor/email-qa.env` with mode `600`. The repo-root file is gitignored, so it can live beside this config without being committed. The helper loads the live `~/.cursor/email-qa.env` directly, so Gmail QA works from any project without relying on `.envrc` or `direnv`.

1. In Gmail settings for that inbox, open **Settings → See all settings → Forwarding and POP/IMAP** and confirm the **IMAP access** section is present. Some Gmail accounts no longer show a separate "Enable IMAP" toggle there.
2. In the Google Account security page, enable 2-Step Verification if needed, then create an **App Password** for the same Google account.
3. Put the app password in repo-root `email-qa.env`, then run `bash sync.sh`:

   ```bash
   EMAIL_QA_BACKEND=gmail
   EMAIL_QA_GMAIL_ADDRESS=your.qa.inbox@gmail.com
   EMAIL_QA_GMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx
   EMAIL_QA_GMAIL_MAILBOX=INBOX
   ```

Use the app password, not the normal Google password. App passwords do not require monthly browser refreshes; they stop working if revoked or if the Google account password changes.

### Mailosaur setup (user)

1. In [Mailosaur](https://mailosaur.com/), create a **server** (inbox). Note **Server ID** — the test addresses look like `anything@<serverId>.mailosaur.net`.
2. Create a **server-restricted API key** (least privilege for that server).
3. **macOS Keychain** (recommended for the secret): store the API key as a generic password (the script reads the password field).

   ```bash
   security add-generic-password -s cursor-email-qa-mailosaur-api-key -a mailosaur -w "YOUR_SERVER_RESTRICTED_KEY"
   ```

   Optional: store the server id the same way if you prefer not to use shell env for it:

   ```bash
   security add-generic-password -s cursor-email-qa-mailosaur-server-id -a mailosaur -w "YOUR_SERVER_ID"
   ```

   Services tried by the script: **API key** — `cursor-email-qa-mailosaur-api-key`, `mailosaur-api-key`; **server id** — `cursor-email-qa-mailosaur-server-id`, `mailosaur-server-id`.

4. Export **non-secret** server id in shell, **direnv**, or project QA docs:

   ```bash
   export MAILOSAUR_SERVER_ID="abcd1234"
   ```

   Set `MAILOSAUR_API_KEY` in CI only via masked variables; locally prefer Keychain.

### CLI examples

```bash
# Mailpit
EMAIL_QA_TIMEOUT_MS=120000 python3 ~/.cursor/skills/email-qa/scripts/email_qa.py \
  --backend mailpit \
  --mailpit-base "http://127.0.0.1:8025" \
  --to "user@example.test" \
  --subject-contains "Verify" \
  --body-contains "code" \
  --timeout-ms 120000

# Gmail (uses ~/.cursor/email-qa.env by default)
python3 ~/.cursor/skills/email-qa/scripts/email_qa.py \
  --backend gmail \
  --to "your.qa.inbox@gmail.com" \
  --subject-contains "Verify" \
  --timeout-ms 120000

# Mailosaur (requires MAILOSAUR_SERVER_ID; key from MAILOSAUR_API_KEY or Keychain)
python3 ~/.cursor/skills/email-qa/scripts/email_qa.py \
  --backend mailosaur \
  --mailosaur-base "https://mailosaur.com" \
  --to "anything@${MAILOSAUR_SERVER_ID}.mailosaur.net" \
  --subject-contains "Verify" \
  --timeout-ms 120000

# Fixture + attachments
python3 ~/.cursor/skills/email-qa/scripts/email_qa.py \
  --backend fixture \
  --fixture-dir ~/.cursor/skills/email-qa/fixtures \
  --to "qa-tester" \
  --subject-contains "login" \
  --download-attachments \
  --output-dir "${TMPDIR:-/tmp}/email_qa_out"
```

**Flags:** `--to`, `--from-contains`, `--subject-contains`, `--body-contains` are substrings; omit filters to take the **newest** message (network backends walk recent list; fixture picks newest matching `.eml` by mtime). `--poll-ms` applies to Mailpit/Gmail/Mailosaur polling.

### JSON output

`subject`, `from`, `to`, `date`, `text`, `html`, `otpCandidates`, `magicLinkCandidates` (http(s)/mailto URLs and parsed `href`s), `attachments` (`filename`, `path`, `contentType`, `sizeBytes` when saved), `backend` (`mailpit` | `gmail` | `mailosaur` | `fixture`).

## What parent agents should pass to QA

Copy into the **QA delegation prompt** when email is in scope:

1. `QA environment: cursor` / `real` / `cli` (unchanged from project QA).

2. **Email QA block (Mailpit)** — e.g.  
   `Email QA: email-qa skill; backend mailpit; base http://127.0.0.1:8025; match --to <addr> --subject-contains <needle>; timeout 120s; run email_qa.py; use otpCandidates / magicLinkCandidates as needed; save attachments under $TMPDIR/...; do not execute files.`

3. **Email QA block (Gmail)** — e.g.  
   `Email QA: email-qa skill; backend gmail; test inbox <addr from ~/.cursor/email-qa.env>; credentials from ~/.cursor/email-qa.env; match --to <same addr> --subject-contains <needle> or --body-contains <needle>; timeout 120s; run ~/.cursor/skills/email-qa/scripts/email_qa.py with --backend gmail; use JSON otpCandidates / magicLinkCandidates / attachments; do not post secrets or full email bodies.`

4. **Email QA block (Mailosaur)** — e.g.  
   `Email QA: email-qa skill; backend mailosaur; MAILOSAUR_SERVER_ID <id> (addresses anything@<id>.mailosaur.net); API key from env MAILOSAUR_API_KEY or macOS Keychain service cursor-email-qa-mailosaur-api-key; match --to <full test address> --subject-contains <needle>; timeout 120s; run ~/.cursor/skills/email-qa/scripts/email_qa.py with --backend mailosaur; use JSON otpCandidates / magicLinkCandidates; do not post secrets.`

5. **Fixtures** — path to `.eml` dir for offline runs.

Never commit API keys to shared cursor-config; project QA docs may name env vars only.

## Related

- Project-specific flows: `.cursor/skills/project-qa/` in the product repo when present.
- **quality-gates** / **qa** agent: OTP/magic-link email is **verifiable** when Mailpit, Gmail, Mailosaur, or fixtures are wired; only mark “Cannot verify” when no capture path was provided.
