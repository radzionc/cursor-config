#!/usr/bin/env bash

# Subshell prevents set -euo pipefail from leaking when sourced (`. ./sync.sh`)
(

# Resolve script location before set -u, since BASH_SOURCE is unavailable in zsh
if [ -n "${BASH_SOURCE:-}" ]; then
  _script="${BASH_SOURCE[0]}"
else
  _script="$0"
fi
REPO_DIR="$(cd "$(dirname "$_script")" && pwd)"
CURSOR_HOME="${CURSOR_HOME:-$HOME/.cursor}"

set -euo pipefail

required_dirs=(agents rules skills scripts)
optional_dirs=(hooks)

sync_dir() {
  local src_dir="$1"
  local dest_dir="$2"
  mkdir -p "$dest_dir"
  rsync -a "$src_dir/" "$dest_dir/"
}

# Paths under CURSOR_HOME that are not in the repo mirror (openrsync needs -i for *deleting lines;
# GNU rsync often emits "deleting path" without a leading asterisk).
append_dest_only_paths() {
  local dir_name="$1"
  local src="${REPO_DIR}/${dir_name}"
  local dest="${CURSOR_HOME}/${dir_name}"
  local line rel first

  [[ -d "$dest" ]] || return 0

  if [[ -d "$src" ]]; then
    while IFS= read -r line || [[ -n "$line" ]]; do
      rel="$(printf '%s\n' "$line" | sed -nE 's/^\*?deleting (.+)/\1/p')"
      [[ -n "$rel" ]] || continue
      # Top-level extra under dir_name (e.g. skills/junk.md): report the exact absolute path.
      if [[ "$rel" != */* ]]; then
        printf '%s\n' "${CURSOR_HOME}/${dir_name}/${rel}"
        continue
      fi
      first="${rel%%/*}"
      # Nested extra: if that subtree exists in the repo, only specific paths are stale → full path.
      # If the first segment has no counterpart in the repo, the whole subtree is orphan → one folder line.
      if [[ -d "${src}/${first}" ]]; then
        printf '%s\n' "${CURSOR_HOME}/${dir_name}/${rel}"
      else
        printf '%s\n' "${CURSOR_HOME}/${dir_name}/${first}/"
      fi
    done < <(rsync -ain --delete "${src}/" "${dest}/" 2>/dev/null || true)
  else
    # Optional folder absent from repo but still present under ~/.cursor
    find "$dest" -mindepth 1 -maxdepth 1 2>/dev/null | while IFS= read -r p || [[ -n "$p" ]]; do
      [[ -n "$p" ]] || continue
      printf '%s\n' "${CURSOR_HOME}/${dir_name}/$(basename "$p")"
    done
  fi
}

get_settings_path() {
  case "$(uname -s)" in
    Darwin) echo "$HOME/Library/Application Support/Cursor/User/settings.json" ;;
    Linux)  echo "$HOME/.config/Cursor/User/settings.json" ;;
    *)      return 1 ;;
  esac
}

sync_global_ignore() {
  local patterns_file="${REPO_DIR}/global-cursorignore"

  if [[ ! -f "$patterns_file" ]]; then
    return
  fi

  local settings_file
  if ! settings_file="$(get_settings_path)"; then
    echo "  skipped global ignore (unsupported OS)"
    return
  fi

  if [[ ! -f "$settings_file" ]]; then
    echo "  skipped global ignore (settings.json not found)"
    return
  fi

  local result
  result="$(python3 - "$patterns_file" "$settings_file" << 'PYTHON'
import json, re, sys

patterns_path, settings_path = sys.argv[1], sys.argv[2]

patterns = []
with open(patterns_path) as f:
    for line in f:
        stripped = line.split('#')[0].strip()
        if stripped:
            patterns.append(stripped)

with open(settings_path) as f:
    text = f.read()

# Strip trailing commas (JSONC → JSON)
text = re.sub(r',\s*([\]}])', r'\1', text)
settings = json.loads(text)

existing = settings.get('cursor.general.globalCursorIgnoreList', [])
if existing == patterns:
    print('up-to-date')
    sys.exit(0)

settings['cursor.general.globalCursorIgnoreList'] = patterns

with open(settings_path, 'w') as f:
    json.dump(settings, f, indent=2)
    f.write('\n')

print(f'synced {len(patterns)} patterns')
PYTHON
  )"

  if [[ "$result" == "up-to-date" ]]; then
    echo "  global ignore already up-to-date"
  else
    echo "  ${result} → settings.json"
  fi
}

sync_email_qa_env() {
  local repo_env_file="${REPO_DIR}/email-qa.env"
  local live_env_file="${CURSOR_HOME}/email-qa.env"

  if [[ -f "$repo_env_file" ]]; then
    cp "$repo_env_file" "$live_env_file"
    chmod 600 "$repo_env_file" "$live_env_file"
    echo "  synced email-qa.env"
    return
  fi

  if [[ -f "$live_env_file" ]]; then
    cp "$live_env_file" "$repo_env_file"
    chmod 600 "$repo_env_file" "$live_env_file"
    echo "  seeded repo email-qa.env from live Cursor home"
    return
  fi

  cat >"$repo_env_file" <<'EOF'
# Local-only credentials for ~/.cursor/skills/email-qa/scripts/email_qa.py
# This repo-root file is gitignored. sync.sh copies it to ~/.cursor/email-qa.env.
EMAIL_QA_BACKEND=gmail
EMAIL_QA_GMAIL_ADDRESS=your.qa.inbox@gmail.com
EMAIL_QA_GMAIL_APP_PASSWORD=
EMAIL_QA_GMAIL_MAILBOX=INBOX
EMAIL_QA_GMAIL_RECENT_LIMIT=200
EOF

  cp "$repo_env_file" "$live_env_file"
  chmod 600 "$repo_env_file" "$live_env_file"
  echo "  created email-qa.env (add Gmail app password)"
}

echo "Syncing tracked Cursor config to ${CURSOR_HOME}"

for dir_name in "${required_dirs[@]}"; do
  sync_dir "${REPO_DIR}/${dir_name}" "${CURSOR_HOME}/${dir_name}"
  echo "  synced ${dir_name}/"
done

for dir_name in "${optional_dirs[@]}"; do
  if [[ -d "${REPO_DIR}/${dir_name}" ]]; then
    sync_dir "${REPO_DIR}/${dir_name}" "${CURSOR_HOME}/${dir_name}"
    echo "  synced ${dir_name}/"
  else
    echo "  skipped ${dir_name}/ (not present in repo)"
  fi
done

if [[ -f "${REPO_DIR}/hooks.json" ]]; then
  cp "${REPO_DIR}/hooks.json" "${CURSOR_HOME}/hooks.json"
  echo "  synced hooks.json"
else
  echo "  skipped hooks.json (not present in repo)"
fi

sync_global_ignore
sync_email_qa_env

printf '%s\n' "$REPO_DIR" > "${CURSOR_HOME}/.cursor-config-source"
echo "  wrote cursor-config source path"

# Clean up stale account-type rule from previous versions
account_rule="${CURSOR_HOME}/rules/account-type.mdc"
if [[ -f "$account_rule" ]]; then
  rm "$account_rule"
  echo "  removed stale account-type rule"
fi

extras_tmp="$(mktemp "${TMPDIR:-/tmp}/cursor-sync-extras.XXXXXX")"
for dir_name in "${required_dirs[@]}" "${optional_dirs[@]}"; do
  append_dest_only_paths "$dir_name" >>"$extras_tmp"
done

if [[ -s "$extras_tmp" ]]; then
  echo ""
  echo "Present under ${CURSOR_HOME} but not in this repo (not removed by sync; delete manually if obsolete):"
  sort -u "$extras_tmp"
fi
rm -f "$extras_tmp"

)
