## Cursor Config

Source of truth for shared, universal Cursor editor configuration.

Everything here is general-purpose: it applies across any project, any machine, any organization. This repo encodes a high-level way of working with Cursor — workflows, quality gates, skills, and agent definitions that are useful regardless of context.

### What Belongs Here

Configuration that is universally useful:

- **Agents** — subagent definitions (code reviewer, QA)
- **Rules** — always-apply rules for quality gates
- **Skills** — reusable workflows (rebasing, handoffs, syncing, **read-only reference to sibling repos** via `reference-codebases` — org/repo lists live in each workspace’s `.cursor/references/codebases.md` when needed)
- **Scripts** — utilities deployed to `~/.cursor/scripts/` (notifications, etc.)
- **Hooks** — automation triggers (`preToolUse` direnv wrapper, etc.)
- **Global ignore** — patterns blocking AI from accessing foreign tool configs

### What Does NOT Belong Here

Anything tied to a specific **repository or organization** stays in that repo (or org ops), not in this global config:

- **Organization-specific skills** — e.g., a `slack-message` skill wired to a particular Slack workspace
- **Organization-specific repo catalogs** — list of sibling GitHub repos and key paths; keep in the project’s `.cursor/references/codebases.md` (or sync from org ops). The **`reference-codebases` skill here** is only the generic read-only workflow; it loads those local catalogs when present.
- **Project-specific rules** — e.g., a rule about a project's API conventions
- **Runtime state** — plans, transcripts, terminal output, extension data

That content lives directly in `~/.cursor` as local-only configuration, never committed to this repo.

### Architecture

```
~/.cursor  (live runtime — superset)
├── agents/          ← managed by this repo
├── rules/           ← managed by this repo + local-only rules
├── skills/          ← managed by this repo + local-only skills
├── scripts/         ← managed by this repo + local-only scripts
├── hooks/           ← managed by this repo
├── hooks.json       ← managed by this repo
├── skills-cursor/   ← local-only (Cursor-managed skills)
├── plans/           ← local-only (runtime)
├── projects/        ← local-only (runtime)
└── extensions/      ← local-only (runtime)

cursor-config  (this repo)
├── agents/
├── rules/
├── skills/
├── scripts/          ← deployed to ~/.cursor/scripts/
├── hooks/            ← hook scripts
├── hooks.json        ← hook configuration
├── global-cursorignore  ← patterns → settings.json
├── sync.sh           ← sync tooling (not deployed)
└── status.sh         ← sync tooling (not deployed)
```

The live `~/.cursor` directory is a **superset** of this repo. It contains everything from this repo plus local-only content. The sync scripts copy only the repo-managed subset between the two locations, leaving local-only content untouched.

`sync.sh` also writes `~/.cursor/.cursor-config-source` — a one-line file containing the absolute path to the cursor-config repo on this machine. Skills that need cursor-config awareness (e.g., review-config) read this file to discover the repo location without hardcoding machine-specific paths.

### Running Scripts

Cursor's built-in terminal can fail to execute repo scripts for unclear reasons. Run them from a standalone terminal using the full path instead:

```bash
bash ~/cursor-config/status.sh
bash ~/cursor-config/sync.sh
```

Use the path where you cloned this repo if it is not `~/cursor-config`.

### Workflow

For intentional config work:

1. Open `~/cursor-config` in Cursor
2. Edit `agents/`, `rules/`, `skills/`, `scripts/`, and optional hook files
3. Run `bash ~/cursor-config/sync.sh` (or the equivalent path on your machine)
4. Commit and push from `~/cursor-config`

To preview what sync would change:

- Run `bash ~/cursor-config/status.sh` (or the equivalent path on your machine)

### Sync Behavior

`./sync.sh` copies repo content into `~/.cursor` without deleting local-only files.

If you remove a skill or script from the repo, the stale copy in `~/.cursor` needs manual cleanup.

`./status.sh` previews what sync would change, without flagging local-only content as drift.

### Global Ignore (Foreign AI Tools)

Other developers may use Claude Code, Codex, Windsurf, Aider, and similar tools that place their own config files in repositories (`.claude/`, `CLAUDE.md`, `AGENTS.md`, etc.). The `global-cursorignore` file in this repo defines patterns that block Cursor's AI from accessing those files across all workspaces.

`sync.sh` writes these patterns to `cursor.general.globalCursorIgnoreList` in Cursor's `settings.json`. This has the same effect as adding them to a `.cursorignore` file in every project. To add or remove patterns, edit `global-cursorignore` and re-run sync.

Currently covered tools: Claude Code, OpenAI Codex, Windsurf/Codeium, Continue, Aider, Bolt, Sourcegraph Cody, GitHub Copilot.

### Notes

- This setup avoids symlinks because current Cursor builds have known issues detecting symlinked global `rules` and `skills` reliably after restart.
- `hooks/` and `hooks.json` are synced as a full overwrite — the repo copy replaces the live copy. Local-only hooks in `~/.cursor/hooks.json` are not yet supported (see future considerations).

### Future Considerations

- **Test coverage in code review**: The `code-reviewer` agent currently omits test coverage criteria. Most active codebases don't have tests yet. When testing practices are adopted, add a Test Coverage section to the reviewer's criteria (check for new/updated/deleted tests alongside code changes).
- **Hooks merging**: `hooks.json` is currently synced as a full overwrite (repo replaces live). If local-only hooks are needed alongside repo-managed hooks, the sync scripts will need to merge the `hooks` arrays per event type rather than replacing the entire file.
- **Real browser QA auto-detection**: The `real-browser-qa` skill requires manual one-time setup per machine (bridge extension + token). A future hook or sync step could detect whether extension mode is available and surface setup instructions automatically when a project first needs it.
