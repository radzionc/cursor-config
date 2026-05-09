---
name: private
description: Keeps Cursor rules, skills, or other files out of git by using .git/info/exclude.
disable-model-invocation: true
---

# Private (no git)

## Purpose

When the user wants to add or edit Cursor rules, skills, or other files that are for personal use only and must **never** be committed:

1. Create or edit the files as requested.
2. **Exclude them from git** so they never appear in the repository.

## Process

### 1. Create or edit the files

Do whatever the user asked for (new rule, new skill, edit an existing file, etc.).

### 2. Untrack if already tracked

For each private file path, check whether git is already tracking it:

```bash
git ls-files --error-unmatch <path>
```

If the file is tracked, untrack it without deleting the working copy:

```bash
git rm --cached <path>
```

This is necessary because `.git/info/exclude` has no effect on files git already tracks.

### 3. Add exclude entries

Use the **current repository's** `.git/info/exclude` (repo-local, not committed). Each repo has its own; update the one for the repo where the user is working.

1. Add one line per path. Patterns follow `.gitignore` syntax (e.g. `.cursor/rules/private.mdc`, `.cursor/skills/local/`).
2. Only add paths the user asked to keep private — don't add unrelated paths.
3. If the workspace is not a git repository (no `.git` directory), skip this step — creating the files is enough.

### 4. Verify

Run `git status` and confirm the private file(s) do not appear as untracked or modified. If they still show up, diagnose (wrong pattern, file still tracked) and fix.

## Rules

- **Never** `git add` or `git add -f` paths that are meant to be private.
- If the workspace has no `.git` (e.g. `~/.cursor` as the project), there is no exclude file to update — creating the files is enough.
