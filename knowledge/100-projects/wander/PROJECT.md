# iWander Project Documentation

## Overview
AI-powered walking tour generator. Users select city, themes, and preferences → Claude generates personalized tours with narratives, fun facts, and walking directions.

## Architecture

### Frontend (Vercel)
- **URL**: iwander.app
- **Stack**: React, Vite, Tailwind CSS, Framer Motion
- **Repo**: github.com/outrcore/iwander (app/ directory)
- **Deploy**: Auto-deploy via Vercel webhook on push to master
- **Root Directory**: `app/`

### Backend (DigitalOcean)
- **URL**: api.iwander.app
- **Server**: YOUR_SERVER_IP
- **Stack**: FastAPI, Python
- **Deploy**: GitHub Actions → SSH → git pull → systemctl restart wander-api

### Database (Supabase)
- **URL**: byhtzbbaopdvgevtecpm.supabase.co
- Tables: routes, route_stops, favorites, users

## Critical Deployment Rules

⚠️ **Git author MUST be `outrcore <outrcore@users.noreply.github.com>`**
- Vercel rejects commits from non-team members
- Atlas commits will fail deployment!

## Database Schema

### routes table
- id, user_id, city, title, description, theme, themes[], duration_minutes
- **image_url** - Unsplash hero image
- created_at, share_id

### route_stops table
- id, route_id, order_index, name, tagline, address, narrative, fun_fact
- latitude, longitude, location (PostGIS), duration_minutes
- **photo_url** - Google Places venue photo
- **focal_point** - CSS object-position value (e.g., "center 70%")

## Image Strategy

### Hero Images (Tour Page Header)
- Source: Curated Unsplash URLs per city
- Stored in: `routes.image_url`
- 16 cities have curated images, fallback for others

### Stop Images (Venue Thumbnails)
- Source: Google Places Photos API
- Stored in: `route_stops.photo_url`
- Focal points control cropping via `object-position`

## Theme System

### Available Themes (13)
Primary 6: Literary, History, Architecture, Food & Drink, Music, Local Secrets
Expandable 7: Sustainable, Nature & Parks, Street Art, Haunted, Craft Beer, Shopping, Photography

### Multi-Theme Selection
- Users can select up to 3 themes
- Backend weaves themes together (finds intersections)
- Popular combos: History+Crime, Architecture+Sustainable, Food+Hidden

## API Endpoints

### POST /api/routes/generate
Request:
```json
{
  "city": "Chicago",
  "themes": ["music", "food"],
  "duration": 120,
  "interests": "Start at Salt Shed, end at House of Blues",
  "save": true
}
```

### GET /api/routes/id/{route_id}
### GET /api/routes/shared/{share_id}
### POST /api/routes/favorite
### DELETE /api/routes/favorite/{route_id}

## Environment Variables

### Frontend (.env)
- VITE_SUPABASE_URL
- VITE_SUPABASE_ANON_KEY
- VITE_API_URL=https://api.iwander.app
- VITE_MAPBOX_TOKEN

### Backend (.env)
- SUPABASE_URL, SUPABASE_KEY
- ANTHROPIC_API_KEY
- GOOGLE_MAPS_API_KEY
- UNSPLASH_ACCESS_KEY

## UI Design Guidelines

### Colors
- Primary: wander-600=#16a34a (green)
- Secondary: emerald-500=#10b981
- Accent: teal-400=#2dd4bf

### Unified Tour Layout (v1.5)
All three tour pages now share the same layout:

**Mobile:**
1. Hero image with stats overlay (duration, distance, location)
2. Map section (`lg:hidden`)
3. Location Details card (city, start/end points)
4. About This Tour
5. Tour Stops (with thumbnails)
6. Fixed bottom bar: Start Tour + Save + Share

**Desktop:**
- 3-column grid (`lg:grid-cols-3`)
- Main content (col-span-2): About, Tour Stops
- Sidebar (col-span-1): Map, Actions, Location Details, Generate link

### Stop Card Layout (Option E)
- Compact header: number badge + 64px thumbnail + text
- Text stack: Title (bold) → Place Name → Address (with pin icon)
- Address hidden if it duplicates place_name
- Expandable: narrative + fun fact (amber box)

### Tour Pages
- `/generated/:id` → GeneratedTour.jsx (freshly generated)
- `/tour/shared/:id` → SharedTour.jsx (shared links)
- `/tour/:id` → TourDetail.jsx (explore/saved tours)

## Route Generation

### SSE Streaming Endpoint
`POST /api/routes/generate/stream` returns Server-Sent Events:
- `finding_places` → `crafting` → `mapping` → `refining` → `photos` → `complete`
- Frontend timeout: 90 seconds
- Uses Claude Sonnet for quality (60-80s total)

### Time-Based Validation
- Formula: `time = (distance / 2.5 mph × 60) + (stops × dwell_time)`
- Asymmetric tolerance: Under OK, over NOT OK (+5 min max)
- Duration tiers: 1hr (50-65min), 2hr (105-125min), 3hr (160-185min)

### Address Enrichment
- Nearby search returns `vicinity` (incomplete)
- Text search returns `formatted_address` (complete)
- If address < 20 chars or matches place name → call Place Details API

## Version History
- **v1.5** (2026-02-06): Unified tour UI, SSE streaming, share functionality
- **v1.2** (2026-02-04): SEO hub pages, 257-URL sitemap, breadcrumbs

### Matt's Rules
1. Once UI is approved and live, DON'T change without discussion
2. Use mockups FIRST before pushing to production
3. NO fake stats - always use real database data
4. Units: MILES only (no metric)
