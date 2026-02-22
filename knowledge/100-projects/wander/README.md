# iWander - AI Walking Tours

> AI-powered narrative walking tours that make the journey the destination.

## Quick Reference

| Item | Value |
|------|-------|
| **Repo** | github.com/outrcore/iwander |
| **Production** | https://iwander.app |
| **API** | https://api.iwander.app |
| **Stable Tag** | v1.0-stable |

## Infrastructure

### Frontend (Vercel)
- **Host:** Vercel (auto-deploy on push to master)
- **Framework:** React + Vite + Tailwind + Framer Motion
- **Location:** `/workspace/projects/wander/app/`
- **Build:** `npm run build` in app/ directory

### Backend API (DigitalOcean)
- **Host:** DigitalOcean Droplet
- **IP:** YOUR_SERVER_IP
- **Path on server:** `/var/www/wander`
- **Service:** `systemctl restart wander-api`
- **Framework:** FastAPI + Python

### Database (Supabase)
- **Project:** byhtzbbaopdvgevtecpm
- **URL:** https://byhtzbbaopdvgevtecpm.supabase.co
- **Tables:** routes, route_stops, users, signups

### Deployment
- **Frontend:** Push to master → Vercel auto-deploys
- **Backend:** Push to `backend/**` → GitHub Action SSHs to DO → restarts service
- **GitHub Secret Required:** `DO_SSH_KEY` (SSH private key for root@YOUR_SERVER_IP)

## Key Files

### Backend (`/workspace/projects/wander/backend/`)
- `main.py` — API endpoints (FastAPI)
- `route_generator_v2.py` — AI route generation with Claude
- `database.py` — Supabase integration
- `poi_service.py` — Google Places POI fetching
- `directions_service.py` — Mapbox walking directions

### Frontend (`/workspace/projects/wander/app/src/`)
- `pages/Explore.jsx` — Browse all tours
- `pages/Generate.jsx` — Create custom tour
- `pages/TourDetail.jsx` — View single tour
- `components/TourCard.jsx` — Tour preview card

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/routes/featured` | GET | Get published routes (limit 12) |
| `/api/routes/{slug}` | GET | Get single route with stops |
| `/api/routes/generate` | POST | Generate new AI route |
| `/health` | GET | Health check + version |

## Route Generation

Routes are generated via Claude with:
1. **POI Fetching** — Google Places API for real locations
2. **Narrative Generation** — Claude writes stories for each stop
3. **Directions** — Mapbox calculates walking path
4. **Images** — Unsplash for hero images

**Cost:** ~$0.06 per route generation

## Emergency Recovery

```bash
# If production breaks, restore stable version:
cd /workspace/projects/wander
git fetch origin
git reset --hard v1.0-stable
git push --force origin master
```

## Local Development (on RunPod)

```bash
# Start backend
cd /workspace/projects/wander/backend
python main.py  # Runs on port 8080

# Start frontend dev
cd /workspace/projects/wander/app
npm run dev  # Runs on port 5173
```

## Environment Variables

### Backend (.env)
- `ANTHROPIC_API_KEY` — Claude API
- `GOOGLE_PLACES_API_KEY` — POI fetching
- `MAPBOX_ACCESS_TOKEN` — Walking directions
- `SUPABASE_URL` — Database URL
- `SUPABASE_SERVICE_KEY` — Database key
- `UNSPLASH_ACCESS_KEY` — Hero images

### Frontend (.env)
- `VITE_SUPABASE_URL` — Client-side Supabase
- `VITE_SUPABASE_ANON_KEY` — Client-side key
- `VITE_API_URL` — Backend API URL

## Troubleshooting

### Routes not showing on Explore page
1. Check API: `curl https://api.iwander.app/api/routes/featured`
2. If returns sample routes → backend needs update
3. If returns DB routes → frontend caching, hard refresh

### GitHub Action stuck in queue
- GitHub runners can be slow (1-5 min)
- Cancel old queued runs to help
- Manual deploy: SSH to DO, `cd /var/www/wander && git pull && systemctl restart wander-api`

### Route generation fails
- Check Claude API key
- Check Google Places quota
- Check Mapbox quota
