---
name: reference-codebases
description: >-
  Inspect sibling or related Git repositories as read-only reference material while
  editing only the current workspace. Use when the user asks to check another repo,
  compare behavior with backend or product docs, port from a sibling codebase, or
  search for implementations outside the current project.
---

# Reference Codebases

Use this skill when work depends on reading code, specs, or history in repositories other than the **current workspace**. All edits, commits, and project-specific commands apply only here unless the user explicitly asks otherwise.

## Canonical layout (always the same)

Assume a **flat checkout layout**: every related repo is a **sibling directory** of the current workspace — same parent directory as the git root (`git rev-parse --show-toplevel`). Resolve paths with `PARENT_DIR` below; clone new repos **into that parent** so names stay flat and predictable.

Do not invent alternate layouts (nested `src/deps/`, monorepo subfolders as clone roots, etc.) unless the user explicitly says their machine differs.

## Catalog first (repo-specific facts)

Before cloning or guessing paths, read the project catalog at `.cursor/references/codebases.md` when it exists.

Catalogs should stay **lightweight**: GitHub org, repository list, key paths, and **only** naming exceptions (local folder name vs GitHub repo name). Layout is defined above, not repeated per project.

## Ground rules

- **Read-only in reference repos.** Do not modify, format, commit, stash, reset, generate files, or run write-heavy scripts there.
- **Safe operations elsewhere:** search (`rg`), read files, `git status`, `git log`, `git diff`, and `git pull --ff-only` (or equivalent fast-forward sync only).
- **Prefer stable local directory names** that match how the team clones (often identical to the GitHub repository name). If the catalog says otherwise, follow the catalog.
- A reference repo does not need to exist yet. Clone beside the workspace when needed and the user/org allows it.

## Resolve paths (flat siblings)

```bash
WORKSPACE_ROOT="$(git rev-parse --show-toplevel)"
PARENT_DIR="$(cd "$WORKSPACE_ROOT/.." && pwd)"
REPO_DIR="$PARENT_DIR/<local-directory-name>"
```

Use the catalog's **local directory name** for `<local-directory-name>` (usually the GitHub repo name; the catalog calls out exceptions such as `api` vs `api-client`).

If the repo exists locally, sync read-only:

```bash
git -C "$REPO_DIR" pull --ff-only
```

If it is missing and the catalog (or user) gives `org` and the GitHub repository name:

```bash
gh repo clone <org>/<github-repo-name> "$REPO_DIR"
```

When the local directory name differs from `<github-repo-name>`, clone into the path the catalog implies (see **Canonical layout** — still one flat parent, explicit local name).

If `gh` is unavailable, unauthenticated, or clone/pull fails (network, dirty tree), report the blocker and continue with any usable local copy. **Do not repair reference-repo git state** unless the user explicitly asks.

## Discover repos when the catalog is missing

1. List sibling directories: `ls "$PARENT_DIR"`.
2. If you need remote names and have `gh`, infer GitHub `org` from `git remote get-url origin` when it matches `github.com/<org>/...`, then:

   ```bash
   gh repo list <org> --limit 100 --json name,description
   ```

## Inspection workflow

1. Resolve path; pull `--ff-only` or clone as above.
2. Read that repo's own agent guidance first when present: `AGENTS.md`, `CLAUDE.md`, `.cursor/rules/`, `.agents/`, etc.
3. Search and read only what is needed for the question.
4. Bring conclusions back to the **current workspace**. Implement changes only here.

## Porting note

When porting behavior from a reference repo: match inputs, outputs, edge cases, and errors; implement using **this** repo's conventions, types, and patterns (see that repo's rules and the current workspace's rules).
