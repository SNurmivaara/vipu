---
name: release
description: Prepare and publish a Vipu release. List what changed since the last release, choose the semver bump, draft release notes, and publish only after the maintainer approves. Use when the user asks to release, cut, tag or publish a version, or asks what the next version should be.
---

# Release Vipu

Publishing a GitHub release tags `main` and starts `.github/workflows/release.yml`,
which pushes GHCR images and moves their `latest` tags. Deployments that follow
`latest` pick the release up, so publishing is close to deploying. Never publish
without the maintainer's explicit approval of the version and notes in this
conversation, and never deploy.

## 1. Check the starting point

```sh
git fetch origin --tags
gh release view --json tagName,publishedAt
git tag --sort=-creatordate | head -n 1
gh run list --workflow CI --branch main --limit 1 --json headSha,conclusion
git rev-parse origin/main
```

The release target is `origin/main`. Stop and report when the latest CI run on
`main` is not for that commit or did not succeed, or when nothing landed since the
last release tag.

The notes cover changes since the latest release's tag, but `release.yml` compares
against the most recently created tag. They are normally the same; when they differ
(a tag pushed without a release), say so, and use the newest tag for step 4.

## 2. Collect the changes

```sh
git log --first-parent --format='%h %s' <last-tag>..origin/main
git diff --stat <last-tag> origin/main -- backend frontend mcp-server deploy
```

Read each merged PR with `gh pr view <n> --json title,body`, especially its
"Migration, deployment, and recovery" section, and sort it:

- **Users**: behavior visible in the app, the REST API or the MCP tools.
- **Deployers**: images, `deploy/`, environment variables, migrations, the database
  driver and other runtime dependencies, and the authentication setup.
- **Internal**: CI, tests, development tooling, `.claude/`, contributor docs, and
  dependency bumps without a runtime effect.

## 3. Choose the version

Vipu's public contract is the REST API under `/api`; MCP tool names, arguments and
result fields; and the documented deployment: `deploy/docker-compose.yml`,
`deploy/.env.example`, the image names, and the setup guides in `README.md`,
`docs/` and `mcp-server/OAUTH.md`. Configuration those do not document is not part
of it.

- **Major**: part of that contract stops working unless a client or deployer changes
  something. Examples: a removed or renamed endpoint, field, MCP tool or argument; a
  changed meaning of an existing field; a removed or renamed documented environment
  variable; an upgrade that needs more than `docker compose pull` and `up -d`.
- **Minor**: new backward-compatible capability, such as an endpoint, field, tool,
  optional setting or user-visible feature, or a migration that runs automatically.
- **Patch**: fixes, documentation and dependency updates only.
- **No release**: only internal changes. Say so and stop.

Name the change that decides the bump. A break limited to undocumented
configuration does not force a major; describe it under "Upgrade notes". When the
call is close, give both options and the reason for your recommendation.

## 4. Check the images

The release workflow builds only the components whose directories changed since the
most recently created tag (the second tag from step 1). An unchanged component gets
no `vX.Y.Z` image, and a deployment that pins `VERSION=vX.Y.Z` then fails to pull
it. Report which of `backend/`, `frontend/` and `mcp-server/` changed:

```sh
git diff --stat <newest-tag> origin/main -- backend frontend mcp-server
```

If one did not, plan the forced build in step 6.

## 5. Draft the notes and ask for approval

Match the tone of the latest release (`gh release view`): short, plain and written
for users and deployers, without AI attribution or real financial data.

- Title: `vX.Y.Z: <headline>`, naming the most important change.
- One or two opening paragraphs on what changes for users and deployers.
- `## Upgrade notes`, only when a deployer must check or change something:
  environment, migrations or recovery. When a migration is included, say that
  rolling back the image does not undo it.
- `## Changes`, grouped as Features, Fixes and Maintenance, one line each ending in
  the PR link `(#n)`. Collapse internal tooling into one or two Maintenance lines.

Show the user the version with its reason, the image check, and the full title and
notes. Wait for explicit approval, and revise on feedback.

## 6. Publish

Only after approval, write the notes to a file and run:

```sh
gh release create vX.Y.Z --target <commit from step 1> --title "<title>" --notes-file <file>
gh run list --workflow release.yml --event release --limit 1 --json databaseId,headSha,status
gh run watch <id> --exit-status
```

If step 4 found an unchanged component and the user agrees, rebuild all images at
the tag once that run finishes:

```sh
gh workflow run release.yml --ref vX.Y.Z -f tag=vX.Y.Z -f force_build=true
```

Report the release link, the workflow result and the image tags pushed. If the
workflow fails, show the failing step's log and leave the release in place; ask
before deleting or re-running anything. Deployment stays with the maintainer, as
`AGENTS.md` describes.
