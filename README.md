# Virtual Sparkles

A web app that pairs inspirational quotes with nature/adventure photos. Users can browse random quote+photo combos, "like" quotes, and download composited images with the quote overlaid on the photo.

## How it works

- **Data source**: Google Sheets with four tabs — Quotes, Photos, Likes, Downloads
- **Backend**: Flask (Python) serves the single-page frontend and three API endpoints
- **Image compositing**: Pillow generates downloadable images (1080x1920) with quote text, photo credit, and a branded footer
- **Analytics**: Likes and downloads are logged back to Google Sheets with timestamp, IP, and geolocation

## Project structure

```
virtual-sparkles/
  app.py              # Flask backend (routes, caching, image processing)
  ARIAL.TTF           # Font for image text rendering
  footer.png          # Generated on first run, cached
  requirements.txt    # Python dependencies
  .env.example        # Documented environment variables
  .gitignore
  public/
    index.html        # Single-page frontend (HTML + inline CSS/JS)
    favicon.ico
```

## Prerequisites

- Python 3.11+
- A Google Cloud service account with Sheets API access
- A Google Sheet with tabs: `Quotes`, `Photos`, `Likes`, `Downloads`

### Google Sheet column format

| Tab | Columns |
|-----|---------|
| Quotes | Quote, AddedBy |
| Photos | photoUrl, instagramName, instagramLink |
| Likes | (auto-populated: date, time, quote, ip, country, city, referrer) |
| Downloads | (auto-populated: date, time, quote, image_url, ip, country, city, referrer) |

## Setup

```bash
# Clone / navigate to the project
cd virtual-sparkles

# Create and activate a virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Configuration

All config uses sensible defaults for local dev. Override via environment variables if needed:

| Variable | Default | Description |
|----------|---------|-------------|
| `GOOGLE_CREDS_PATH` | `./virtual-sparkles-*.json` | Path to GCP service account JSON |
| `SHEET_ID` | (hardcoded default) | Google Sheet ID |
| `FONT_PATH` | `./ARIAL.TTF` | Path to TTF font file |
| `ALLOWED_IMAGE_HOSTS` | (auto-populated from sheet) | Comma-separated allowlist for image URLs |

Copy `.env.example` to `.env` and edit if you need to override anything.

## Run locally

```bash
source venv/bin/activate
python3 app.py
# Open http://127.0.0.1:5000
```

## Deployment (Render — free tier)

1. Push this repo to GitHub (the `.gitignore` excludes credentials and venv)
2. Go to [render.com](https://render.com), sign in with GitHub
3. Click **New > Web Service**, select your `virtual-sparkles` repo
4. Render auto-detects `render.yaml` — accept the defaults
5. In the **Environment** tab, add two secret env vars:
   - `GOOGLE_CREDS_JSON` — paste the **entire contents** of your service account JSON file
   - `SHEET_ID` — your Google Sheet ID (default is already set in code, only needed if you change sheets)
6. Deploy. Render gives you a URL like `https://virtual-sparkles.onrender.com`

The free tier sleeps after 15 min of inactivity. First visit after sleep takes ~30s to wake up.

## API endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Serves the frontend |
| `/data` | GET | Returns a random quote + photo pair |
| `/like` | POST | Records a quote like (body: `{quote}`) |
| `/download_photo` | POST | Returns a composited PNG (body: `{imageUrl, quote, photoCredit}`) |
