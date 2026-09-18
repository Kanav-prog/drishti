# DRISHTI DevOps Free-Tier Plan

## Goal
Use a low-cost DevOps path without AWS or Azure, centered on Render and open-source tools.

## Active CI/CD Path
- CI workflow: `.github/workflows/ci.yml`
- Render deploy workflow: `.github/workflows/deploy-render.yml`

## Archived/Manual-Only Workflows
These are kept for reference but do not auto-run on push:
- `.github/workflows/build-push.yml`
- `.github/workflows/deploy-aws.yml`
- `.github/workflows/drishti_ci.yml`
- `.github/workflows/test-lint.yml`
- `.github/workflows/deploy.yml`

## Required GitHub Secrets (Render)
- `RENDER_DEPLOY_HOOK`: Render service deploy hook URL.
- `RENDER_HEALTH_URL` (optional): Full health endpoint URL.
  - Default used if missing: `https://drishti-api.onrender.com/api/health`

## Render Blueprint Notes
- Keep `render.yaml` as source of truth for services and env vars.
- Prefer managed Postgres and Redis free tiers first.
- Use `STREAMING_BACKEND=mock` for free-tier reliability when live feeds are unavailable.

## Free-Tier Friendly Practices
- Keep CI focused on critical tests only.
- Avoid duplicate workflows on push.
- Use manual dispatch for expensive image builds and enterprise pipelines.
- Keep logs and artifacts short retention where possible.

## Optional Open-Source Alternative (Self-Hosted)
Use one VPS with Coolify or Dokploy:
- Deploy backend, frontend, Postgres, and Redis from Docker images.
- Use automatic TLS via reverse proxy.
- Use nightly database backups to object storage.

## Recommended Next Steps
1. Add `RENDER_DEPLOY_HOOK` secret and run a manual `Render Deploy (Free Tier)` workflow.
2. Confirm smoke check passes against production health URL.
3. Add branch protection requiring CI before merge.
4. Add uptime monitor (free tier) against `/api/health`.
