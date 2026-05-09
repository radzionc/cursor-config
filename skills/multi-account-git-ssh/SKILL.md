---
name: multi-account-git-ssh
description: >-
  Multiple GitHub identities on one Mac: SSH Host aliases per account,
  path-scoped Git user.name/email, keys, remotes, and gh CLI. Use for
  clone/pull/push when fixing permission denied (publickey), wrong commit email,
  or "Repository not found" on private repos. User names the workspace root
  and org in chat.
disable-model-invocation: true
---

# Multiple GitHub accounts + SSH (one laptop)

**Convention:** Keep each GitHub identity under its own directory tree, for example `~/src-personal/` and `~/src-company/`. Pick a stable short **label** per identity (`personal`, `company`, `oss`, …). Reuse that label for the SSH `Host` alias (`github.com-<label>`), the private key filename (`id_ed25519_<label>`), and the `includeIf gitdir:` path.

This is the usual setup when **work and personal GitHub** (or two organizational accounts) share one machine: each identity gets its own key and commit **author**, and remotes use the matching SSH **Host** so the wrong account is never offered first.

Treat **three layers** separately:

1. **Git author** — `user.name` / `user.email` (what appears on commits).
2. **Remote URL** — which SSH **Host** label you use (`github.com` vs an **account-specific alias** like `github.com-<label>`).
3. **SSH identity** — which key GitHub sees (must match the account that has repo access).

---

## 1. Preferred pattern: one SSH `Host` per GitHub account (stable names)

GitHub documents **separate `Host` stanzas** in `~/.ssh/config` when several accounts use one machine. Each stanza sets `HostName github.com`, **one** `IdentityFile`, and `IdentitiesOnly yes`.

**Naming:** Use a **stable label per GitHub account**, not a vague word like `work` that might collide later. Examples: `github.com-personal`, `github.com-company`. When you **add another GitHub account**, add a new `Host` block and key — **do not rename** existing hosts or remotes; older clones keep working.

```sshconfig
# Personal — default for git@github.com:ORG/REPO.git
Host github.com
  HostName github.com
  User git
  IdentityFile ~/.ssh/id_ed25519_personal
  IdentitiesOnly yes

# Example: company GitHub account (matches id_ed25519_company)
Host github.com-company
  HostName github.com
  User git
  IdentityFile ~/.ssh/id_ed25519_company
  IdentitiesOnly yes

# When you add another account — new block + key; remotes use git@github.com-<label>:...
# Host github.com-oss
#   HostName github.com
#   User git
#   IdentityFile ~/.ssh/id_ed25519_oss
#   IdentitiesOnly yes
```

Remotes for that identity use the label: `git@github.com-<label>:ORG/REPO.git`.

**Why not `git@github.com` + `core.sshCommand` alone?**
If `Host github.com` pins your **personal** key, the agent may still try that key first against `github.com`. You can get the wrong user or **"Repository not found"** on private org repos. **Account-specific Host** labels avoid that.

---

## 2. Path-scoped Git user (name + email)

Each identity’s clones live under `~/<tree>/` (for example `~/src-company/`). Use `includeIf` so repos there get the right **author** (independent of SSH). One include file per identity:

```ini
# ~/.gitconfig
[includeIf "gitdir:~/src-company/"]
  path = ~/.gitconfig-company
```

```ini
# ~/.gitconfig-company — user only; remotes use Host github.com-company
[user]
  name = Your Name
  email = you@example.com
```

Use a **trailing slash** on `gitdir:` so nested repos match.

---

## 3. Keys and GitHub

- One Ed25519 key per GitHub account:
  `ssh-keygen -t ed25519 -C "you@example.com" -f ~/.ssh/id_ed25519_company`
- Naming: `~/.ssh/id_ed25519_<label>` lines up with the Host alias and directory convention.
- Add each **public** `.pub` to that GitHub account: **Settings → SSH and GPG keys**.
- **`IdentitiesOnly yes`** on each `Host` stops the agent from offering the wrong key first.

---

## 4. Remotes and cloning

Use the **account Host alias** from `~/.ssh/config`, not plain `github.com`, for repos that belong to that identity:

```bash
mkdir -p ~/src-company && cd ~/src-company
git clone git@github.com-company:ORG/REPO.git
```

General pattern: `mkdir -p ~/<tree> && cd ~/<tree>` then `git clone git@github.com-<label>:ORG/REPO.git`.

GitHub’s clone string shows `git@github.com:...` — **replace** `github.com` with your alias (e.g. `github.com-company`) before running.

**HTTPS** uses credential / `gh` tokens; not the same as SSH keys.

---

## 5. GitHub CLI (`gh`)

`gh` stores its own API token (`gh auth login`). Git **push/pull** follow `remote` + SSH. Match `gh` login to the org when opening PRs.

---

## 6. Verification

From a repo whose remote uses `git@github.com-<label>:...`:

```bash
git config --show-origin user.email
ssh -T git@github.com-company
git ls-remote origin HEAD
```

Personal repos (`git@github.com:...`):

```bash
ssh -T git@github.com
```

---

## 7. Troubleshooting

| Symptom | Likely cause |
|--------|----------------|
| `Permission denied (publickey)` | Wrong `Host` / key; key not on that GitHub account. |
| `Repository not found` (private) | Wrong account authenticated — use the **account-specific Host** in the remote, not bare `github.com`. |
| Commits wrong name/email | Repo outside `gitdir` for `includeIf`, or local override. |

---

## 8. If the user did not specify

Read `~/.ssh/config` for **Host** names, `~/.gitconfig` / `includeIf` for paths, then clone or fix remotes to match. Ask which **workspace directory** and **org/repo** if unclear.
