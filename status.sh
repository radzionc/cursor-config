#!/usr/bin/env bash

# Subshell prevents set -euo pipefail from leaking when sourced (`. ./status.sh`)
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
all_tracked_dirs=("${required_dirs[@]}" "${optional_dirs[@]}")

get_dir_drift() {
  local dir_name="$1"
  local src_dir="${REPO_DIR}/${dir_name}"
  local dest_dir="${CURSOR_HOME}/${dir_name}"

  if [[ ! -d "$src_dir" ]]; then
    echo "repo directory missing"
    return 0
  fi

  if [[ ! -d "$dest_dir" ]]; then
    echo "live directory missing"
    return 0
  fi

  rsync -acni "$src_dir/" "$dest_dir/" 2>/dev/null \
    | grep -v '^\.d' \
    | sed 's/^[^ ]* /  /' || true
}


drift_header_shown=false

show_drift_if_any() {
  local label="$1"
  local output="$2"
  if [[ -z "$output" ]]; then
    return
  fi
  if [[ "$drift_header_shown" == false ]]; then
    echo "=== Drift (repo vs live) ==="
    echo
    drift_header_shown=true
  fi
  echo "== ${label} =="
  echo "$output"
  echo
}

for dir_name in "${required_dirs[@]}"; do
  show_drift_if_any "${dir_name}/" "$(get_dir_drift "$dir_name")"
done

for dir_name in "${optional_dirs[@]}"; do
  if [[ -d "${REPO_DIR}/${dir_name}" || -d "${CURSOR_HOME}/${dir_name}" ]]; then
    show_drift_if_any "${dir_name}/" "$(get_dir_drift "$dir_name")"
  fi
done

global_ignore_drift=""
patterns_file="${REPO_DIR}/global-cursorignore"
if [[ -f "$patterns_file" ]]; then
  settings_file=""
  case "$(uname -s)" in
    Darwin) settings_file="$HOME/Library/Application Support/Cursor/User/settings.json" ;;
    Linux)  settings_file="$HOME/.config/Cursor/User/settings.json" ;;
  esac
  if [[ -n "$settings_file" && -f "$settings_file" ]]; then
    global_ignore_drift="$(python3 - "$patterns_file" "$settings_file" << 'PYTHON'
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
text = re.sub(r',\s*([\]}])', r'\1', text)
settings = json.loads(text)
existing = settings.get('cursor.general.globalCursorIgnoreList', [])
if existing == patterns:
    pass
else:
    added = [p for p in patterns if p not in existing]
    removed = [p for p in existing if p not in patterns]
    extra_in_settings = [p for p in existing if p not in patterns]
    if not existing:
        print('not configured in settings.json')
    else:
        parts = []
        if added:
            parts.append(f'{len(added)} to add')
        if removed:
            parts.append(f'{len(removed)} to remove')
        if extra_in_settings:
            parts.append(f'{len(extra_in_settings)} only in settings')
        print(', '.join(parts) if parts else 'different')
PYTHON
    )" || true
  fi
fi
show_drift_if_any "global-cursorignore" "$global_ignore_drift"

hooks_drift=""
if [[ -f "${REPO_DIR}/hooks.json" && -f "${CURSOR_HOME}/hooks.json" ]]; then
  if ! cmp -s "${REPO_DIR}/hooks.json" "${CURSOR_HOME}/hooks.json"; then
    hooks_drift="different"
  fi
elif [[ -f "${REPO_DIR}/hooks.json" ]]; then
  hooks_drift="present only in repo"
elif [[ -f "${CURSOR_HOME}/hooks.json" ]]; then
  hooks_drift="present only in live Cursor home"
fi
show_drift_if_any "hooks.json" "$hooks_drift"

unique_header_shown=false

for dir_name in "${all_tracked_dirs[@]}"; do
  if [[ ! -d "${CURSOR_HOME}/${dir_name}" ]]; then
    continue
  fi

  dir_unique=""
  while IFS= read -r -d '' entry; do
    name="$(basename "$entry")"
    if [[ ! -e "${REPO_DIR}/${dir_name}/${name}" ]]; then
      dir_unique+="  ${name}"$'\n'
    fi
  done < <(find "${CURSOR_HOME}/${dir_name}" -maxdepth 1 -mindepth 1 -print0 2>/dev/null | sort -z)

  if [[ -n "$dir_unique" ]]; then
    if [[ "$unique_header_shown" == false ]]; then
      echo "=== Unique to live ~/.cursor (not in repo) ==="
      echo
      unique_header_shown=true
    fi
    echo "== ${dir_name}/ =="
    printf '%s' "$dir_unique"
    echo
  fi
done

)
