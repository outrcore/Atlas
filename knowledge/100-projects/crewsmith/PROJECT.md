# Crewsmith — Project Documentation

**URL:** crewsmith.ai
**Repo:** `outrcore/crewsmith` (private) → GitHub auto-deploy to Vercel
**Status:** Live (launched Feb 16, 2026)
**Tagline:** "Build your AI crew in 60 seconds"

---

## Overview

Hosted SaaS platform where users build AI agent teams (crews) that collaborate on tasks. BYOK model — users bring their own API keys, no markup. All tiers free during beta.

## Stack

- **Frontend:** Next.js 15, App Router, TypeScript, Tailwind CSS
- **Database:** Supabase (project `uwrziguijewesknsbkzr`)
- **Hosting:** Vercel (auto-deploy from `main` branch)
- **Auth:** Supabase SSR + GitHub OAuth (email confirm disabled for dev)
- **Domain:** crewsmith.ai (Porkbun DNS → Vercel)

## Architecture

```
Company → Teams → Projects → Tasks
                     ↓
               Connected Repos (via GitHub App)
```

- **Company:** Top-level org, one per user
- **Teams:** Reusable groups of crew members (flat, no nesting for v1)
- **Projects:** Where work happens. Repos connect here, not to teams
- **Tasks:** Units of work, scoped to projects, auto-dispatched on creation

## Database (Supabase)

**DB Password:** `YOUR_DB_PASSWORD`
**Tables:** profiles, api_keys, companies, crew_members, tasks, blackboard_events, crew_templates, teams, team_members, projects, connected_repos
**Migrations:** 001 (initial) → 002 (RLS fix) → 003 (company context) → 004 (orchestration) → 005 (GitHub integration) → 006 (teams & projects) → 007 (max_follow_ups)

## Auth

- **GitHub OAuth App** (for Supabase login): Client ID `Ov23li49xK7Bqxjvk8c6`
- **GitHub App** (for repo access): ID `2881387`, install URL `https://github.com/apps/crewsmith-ai/installations/new`
  - Client ID: `Iv23liOTre8A6kWZzgDT`
  - Client Secret: `b0f5d54a7346583fcc58acfd7371ad023bda91b0`
  - Private key: `/workspace/projects/crewsmith/github-app-private-key.pem` (also `GITHUB_APP_PRIVATE_KEY` env var)
  - JWT generation: Node `crypto` (NOT jose — can't handle PKCS#1 keys)

## Execution Engine

### Providers (`src/lib/engine/providers.ts`)
Anthropic, OpenAI, Google, Fireworks (incl. MiniMax M2.5), DeepSeek — all raw fetch, no SDKs, BYOK.
Multi-turn `ChatMessage[]` support on all providers.
Fireworks max_tokens capped at 16,000 (API requires streaming above that).

### Orchestration (`src/lib/engine/orchestrate.ts`)
- CEO/CoS/Director detected by role name pattern (`LEADER_ROLE_PATTERNS` regex)
- Leader plans subtasks via JSON, delegates to crew, synthesizes results
- Leader excluded from grunt work pool
- Follow-up evaluation loop: CEO decides if more work needed
- Configurable follow-up rounds: 0/1/3/5/10/20/Unlimited (hard cap 50)
- Auto-retry on bad JSON parse (stricter prompt on retry)
- `maxDuration = 300s` for Vercel serverless

### Task Execution (`src/lib/engine/execute.ts`)
- Auto-dispatch: tasks fire immediately on creation
- Multi-turn tool use loop (max 5 rounds):
  - `<read_file repo="owner/repo" path="file" />` — reads via GitHub App, 50KB/file, 150KB total
  - `<web_search query="..." />` — via Perplexity API (max 3/round)
  - `<browse_url url="..." />` — fetches URLs, strips HTML, 30KB limit
- Tool tags stripped from final output
- Dynamic tool instructions based on available capabilities

### Dispatch (`src/lib/engine/dispatch.ts`)
Auto-assigns idle crew members by keyword matching.

## Pages

| Route | Purpose |
|-------|---------|
| `/` | Landing page (SEO, pricing, trust bar) |
| `/login`, `/signup` | Auth forms |
| `/onboarding` | 3-step wizard (company → template → launch) |
| `/dashboard` | Overview with stats, crew list, blackboard feed |
| `/dashboard/crew` | Crew CRUD (emoji, model, thinking level, personality) |
| `/dashboard/teams` | Team management |
| `/dashboard/projects` | Project management + repo linking |
| `/dashboard/tasks` | Task board with create, filter, detail modal |
| `/dashboard/history` | Task history with filters/sort/pagination |
| `/dashboard/templates` | 6 starter templates |
| `/dashboard/blackboard` | Event feed with icons |
| `/dashboard/settings` | Profile, company context, API keys, danger zone |

## Design System

- Background: slate-950
- Cards: slate-900, white/5 borders, rounded-2xl
- Accent: "forge" orange
- Icons: Lucide
- Mobile: hamburger sidebar

## Pricing (Beta)

All tiers FREE during beta (strikethrough on future prices):
- Starter: ~~$39/mo~~ Free
- Pro: ~~$99/mo~~ Free

## Key Decisions

- **BYOK over platform keys** — users bring API keys, no markup
- **Prompt-based tool use over native function calling** — XML tags work across all 5 providers
- **Repos connect to projects, not teams** — Task → Project → Repos is direct
- **Auto-dispatch over manual Run button** — better UX
- **Await follow-ups instead of fire-and-forget** — Vercel kills serverless after response
- **Flat teams for v1** — no nesting, sub-teams deferred
- **Perplexity for web search** — platform-provided during beta
- **Stricter planning prompts + auto-retry** — MiniMax M2.5 sometimes outputs natural language instead of JSON

## Matt's Test Results

- **Company:** "SkyForge" with 5 crew members (Architect, Builder, QA, Research, Chief of Staff) on MiniMax M2.5
- **First autonomous loop:** 12 tasks, 0 failures, ~$0.005 total cost
- **Validated:** CoS plans subtasks, delegates, synthesizes, auto-creates follow-ups

## TODO

- Stripe billing
- Team invitations
- GitHub App webhooks
- Code execution sandbox
- Playwright QA tool
- Mobile view polish

---

*Created: 2026-02-17*
*Source: Feb 14-17 build sessions*
