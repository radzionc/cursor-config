#!/bin/bash
# preToolUse hook: wrap Shell commands with `direnv exec .`
# so .envrc environment variables are always available.
# Safe when no .envrc exists — direnv passes through silently.

input=$(cat)

if ! command -v direnv &>/dev/null; then
  echo '{"permission": "allow"}'
  exit 0
fi

command_str=$(echo "$input" | jq -r '.tool_input.command // empty')

if [[ "$command_str" == direnv\ exec* ]]; then
  echo '{"permission": "allow"}'
  exit 0
fi

jq -n --arg cmd "$command_str" '{
  permission: "allow",
  updated_input: {
    command: ("direnv exec . bash -c " + ($cmd | @sh))
  }
}'
