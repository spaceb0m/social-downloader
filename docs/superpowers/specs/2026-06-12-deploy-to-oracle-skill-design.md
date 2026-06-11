# Skill design: `deploy-to-oracle`

**Date:** 2026-06-12
**Type:** Personal user skill (`~/.claude/skills/deploy-to-oracle/`), usable from any project.

## Purpose

A skill you invoke from any project in Claude Code to perform a **triple-sync deploy**:
keep code in **Local → GitHub → Oracle server (production)**, containerized, in one flow.

Two modes, auto-detected:
- **Setup** (first time): containerize the project, deploy it, leave it running.
- **Update** (subsequent): commit + push locally, server does `git pull` and rebuilds.

## Flow / architecture

```
LOCAL (PC)                    GITHUB (source of truth)   ORACLE SERVER (prod)
──────────                    ────────────────────────   ────────────────────
1. detect project type
2. generate Dockerfile +  ──► 3. git push           ────► 4. ssh: git pull
   compose if missing                                      5. docker compose up -d --build
   (committed to repo)                                     6. health check
```

- **Connection:** via a `Host` alias in `~/.ssh/config`. The skill never reads or copies
  the private key — it only references the alias.
- **GitHub auth:** repos are **public**; the server clones/pulls over HTTPS with no auth.
  (Local push uses the user's normal git auth.)
- **Server as a git client:** reproducible and auditable; no copying loose files via rsync.

## Decisions locked during brainstorming

| Topic | Decision |
|-------|----------|
| Container tech | Docker + `docker compose` (skill confirms by SSH on connect) |
| Code flow | GitHub as source of truth; server pulls |
| External access | **To be detected** — skill inspects server (n8n's proxy?) and proposes proxy vs direct port |
| Connection persistence | `Host` alias in `~/.ssh/config` |
| Containerization | Generate `Dockerfile` + `docker-compose.yml` if missing; commit them |
| GitHub auth (server) | Public repos — no auth for pull |
| Skill location | Personal: `~/.claude/skills/deploy-to-oracle/` |

## Components

1. **`SKILL.md`** — main workflow + safety rules.
2. **Server environment detection** — on connect, verify `docker` / `docker compose`,
   and **detect an existing reverse proxy** (the one fronting n8n) to propose attaching to
   it; otherwise expose a direct port. Ask before touching anything shared.
3. **Project type detection** (local) — Python/FastAPI, Node, static — and generate a
   suitable `Dockerfile` + `docker-compose.yml`.
   - For `social-downloader`: Python base image, install `ffmpeg`, expose 8000, run uvicorn.
4. **Per-project deploy config** — a `deploy.json` in the repo recording: SSH alias,
   server path (`/opt/apps/<project>`), port, domain (if any).

## Safety & confirmations

- Never copies or commits private keys or secrets.
- **Confirm before** any action touching shared services (proxy, n8n, in-use ports) or
  anything destructive (stop/remove containers).
- Show each SSH command before running it during first-time setup.

## Verification

After deploy: `docker compose ps` + an HTTP health check on the port/domain; report the
final URL back to the user.

## Out of scope (YAGNI)

- CI/CD via GitHub Actions.
- Private-repo auth (deploy keys / PAT) — can be added later if repos go private.
- Kubernetes / Podman / Portainer paths.
