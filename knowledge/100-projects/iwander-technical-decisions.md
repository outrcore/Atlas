# iWander Technical Decisions

*Key technical decisions made during iWander development, extracted from Telegram conversations.*

## Image Strategy (Final Decision)

### Hero Images → Unsplash
- Pretty, editorial photos for tour hero images
- City skylines, vibes, mood shots
- Fallback for unknown cities: generic travel image

### Stop Images → Google Places
- Actual photos of specific venues (user-uploaded + business photos)
- Returns real photos of the exact venue (Salt Shed, House of Blues, etc.)
- Cost: ~$7 per 1000 requests

### Why Not Cloudinary Auto-Focus?
Tested Cloudinary's `g_auto` (gravity auto) for smart cropping:
- `g_auto` isn't smart enough for venue photos
- Better at faces than stage lighting
- Salt Shed kept showing the roof instead of the stage
- **Decision:** Stick with Google Places + CSS `object-position` for manual focal points

### Focal Point System
For better image cropping:
- CSS classes: `.focal-center`, `.focal-top`, `.focal-bottom`, `.focal-left`, `.focal-right`
- Custom inline: `style="object-position: center 70%;"`
- Store in route data: `{ "focalPoint": "center 70%" }`

## Mockup Options (UI/UX)

During development, 5 options were created for stop card layouts:

| Option | Description | Status |
|--------|-------------|--------|
| A | Current (no images) | Rejected |
| B | Small thumbnail by the number | Considered |
| C | Header image (bold, takes space) | Desktop consideration |
| D | Side image (balanced) | Tight on mobile |
| **E** | Compact header (thumbnail + text inline) | **CHOSEN** |

### Final Decision
- **Option E** for all devices
- Compact row with thumbnail + text inline
- Thumbnails handle cropping naturally since they're square
- Clean, scannable, doesn't overwhelm the narrative

### Why Not Hybrid (C desktop, E mobile)?
- Tested but Option C images didn't format well
- Salt Shed showed roof instead of stage even with Cloudinary
- Option E looked "incredible" on all screen sizes

## Walking Distance Validation

### The Problem
Claude generates stops based on "crow flies" distance, not actual walking distance:
- A 0.5km straight line can be a 1.5km walk with city blocks
- Routes were 200-250% of requested distance

### The Solution (Implemented)
**Option A: POI-Guided Generation**
1. Query Google Places/Mapbox for REAL POIs matching theme/area
2. Send Claude a list of valid locations WITH coordinates
3. Claude picks narratively interesting ones and writes stories
4. Mapbox Directions calculates actual walking route

**Option B: Validation + Haiku Revision (Fallback)**
- After generation, Mapbox validates distances
- If off by >30%, Haiku does quick surgical fix

### Technical Implementation
- `poi_service.py` - Fetches real POIs from Google Places by theme
- `directions_service.py` - Gets actual walking routes from Mapbox
- `route_generator_v2.py` - New flow using real POIs + validation
- Frontend: Draws actual walking path (solid purple line, not crow-flies)

### Mapbox Directions API Usage
```
GET /directions/v5/mapbox/walking/{coordinates}
Returns: legs[] array with walk time between each stop
```

## Start/End Point Handling

### The Problem
Users request "Start at Salt Shed, end at House of Blues" but:
- The distance between them might exceed requested route length
- POI system might not include these exact places

### The Solution (Three Layers)
1. **Explicit Fields (Prevention)** - "Start at" / "End at" optional inputs
2. **Smart Parsing (Flexibility)** - Scan special requests for location hints
3. **Validation + Feedback (Transparency)** - Show what worked and what didn't

---
*Created: 2026-02-04 | Source: Telegram export analysis*
