import json
import logging
import io
import os
import random
import tempfile
import textwrap
import threading
from datetime import datetime
from urllib.parse import urlparse

import pygsheets
import requests
from flask import Flask, jsonify, send_from_directory, request, send_file
from PIL import Image, ImageDraw, ImageFont

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__, static_folder='public')

# Paths — relative to this file, overridable via env vars
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FONT_PATH = os.environ.get("FONT_PATH", os.path.join(BASE_DIR, "ARIAL.TTF"))
SHEET_ID = os.environ.get(
    "SHEET_ID", "153am0Y29gzQWFhlpxHLIaxQiHXVDTRasST484d7DYpg"
)

# Google credentials: either a file path or the JSON blob as an env var.
# GOOGLE_CREDS_JSON takes priority (for platforms like Render with no persistent disk).
# Falls back to GOOGLE_CREDS_PATH (file on disk, for local dev).
_creds_json = os.environ.get("GOOGLE_CREDS_JSON")
if _creds_json:
    _creds_tmpfile = tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False
    )
    _creds_tmpfile.write(_creds_json)
    _creds_tmpfile.close()
    GOOGLE_CREDS_PATH = _creds_tmpfile.name
else:
    GOOGLE_CREDS_PATH = os.environ.get(
        "GOOGLE_CREDS_PATH",
        os.path.join(BASE_DIR, "virtual-sparkles-2d7ffc2eda03.json"),
    )

# Image constants
TARGET_WIDTH = 1080
TARGET_HEIGHT = 1920
FOOTER_TEXT = "Remember: Go outside. Have adventures. Do hard things.\nCreated by @lucyschodell"
FOOTER_FONT_SIZE = 30
FOOTER_PATH = os.path.join(BASE_DIR, "footer.png")
DATA_REFRESH_INTERVAL = 600  # Reload data every 10 minutes

# SSRF protection — allowed hostnames for image downloads
ALLOWED_IMAGE_HOSTS = set(
    h.strip() for h in
    os.environ.get("ALLOWED_IMAGE_HOSTS", "").split(",")
    if h.strip()
)

# Load fonts once at startup
QUOTE_FONT = ImageFont.truetype(FONT_PATH, 70)
CREDIT_FONT = ImageFont.truetype(FONT_PATH, 24)
FOOTER_FONT = ImageFont.truetype(FONT_PATH, FOOTER_FONT_SIZE)

# Google Sheets Data Cache
quotes_data = []
photos_data = []
likes_sheet = None
downloads_sheet = None
last_data_refresh = 0
_sheets_lock = threading.Lock()

def load_google_sheets():
    """Loads quotes, photos, and likes from Google Sheets and caches them."""
    global quotes_data, photos_data, likes_sheet, downloads_sheet, last_data_refresh
    if not _sheets_lock.acquire(blocking=False):
        return  # Another thread is already refreshing
    try:
        gc = pygsheets.authorize(service_account_file=GOOGLE_CREDS_PATH)
        sh = gc.open_by_key(SHEET_ID)

        quotes_data = sh.worksheet_by_title('Quotes').get_all_records()
        photos_data = sh.worksheet_by_title('Photos').get_all_records()
        likes_sheet = sh.worksheet_by_title('Likes')
        downloads_sheet = sh.worksheet_by_title('Downloads')

        # Rebuild SSRF allowlist from current photo URLs (clear stale hosts)
        new_hosts = set(
            h.strip() for h in
            os.environ.get("ALLOWED_IMAGE_HOSTS", "").split(",")
            if h.strip()
        )
        for photo in photos_data:
            url = photo.get('photoUrl', '')
            if url:
                parsed = urlparse(url)
                if parsed.hostname:
                    new_hosts.add(parsed.hostname)
        ALLOWED_IMAGE_HOSTS.clear()
        ALLOWED_IMAGE_HOSTS.update(new_hosts)

        last_data_refresh = datetime.now().timestamp()
        logger.info("Google Sheets data loaded successfully.")
    except Exception as e:
        logger.error("Error loading sheets: %s", e)
    finally:
        _sheets_lock.release()

# Preload Google Sheets Data
load_google_sheets()

def get_geolocation(ip_address):
    """Fetches the user's country and city based on their IP address."""
    try:
        response = requests.get(
            f"https://ipapi.co/{ip_address}/json/", timeout=5
        )
        response.raise_for_status()
        geo = response.json()
        return geo.get('country_name'), geo.get('city')
    except requests.exceptions.RequestException as e:
        logger.warning("Error fetching geolocation: %s", e)
        return None, None


@app.route('/data')
def get_random_data():
    if datetime.now().timestamp() - last_data_refresh > DATA_REFRESH_INTERVAL:
        load_google_sheets()

    if not quotes_data or not photos_data:
        return jsonify({"error": "No data available"}), 500

    random_quote = random.choice(quotes_data)
    random_photo = random.choice(photos_data)

    return jsonify({
        'quote': random_quote['Quote'],
        'addedBy': random_quote['AddedBy'],
        'photoUrl': random_photo['photoUrl'],
        'instagramName': random_photo['instagramName'],
        'instagramLink': random_photo['instagramLink'],
    })

@app.route('/like', methods=['POST'])
def like():
    try:
        payload = request.get_json(silent=True)
        if payload is None:
            return jsonify({'result': 'error', 'error': 'Invalid or missing JSON body'}), 400
        quote = payload.get('quote')
        if not quote:
            return jsonify({'result': 'error', 'error': 'Missing quote'}), 400

        now = datetime.now()
        ip_address = request.remote_addr
        country, city = get_geolocation(ip_address)
        referring_url = request.headers.get('Referer')

        if likes_sheet is None:
            return jsonify({'result': 'error', 'error': 'Service unavailable'}), 503
        likes_sheet.append_table(
            values=[[now.strftime('%Y-%m-%d'), now.strftime('%H:%M:%S'),
                     quote, ip_address, country, city, referring_url]],
            start='A1',
            end=None,
            dimension='ROWS',
            overwrite=False,
        )
        return jsonify({'result': 'success'})
    except Exception as e:
        logger.error("Error in /like: %s", e)
        return jsonify({'result': 'error', 'error': 'Failed to record like'}), 500


def create_footer():
    """Pre-renders and caches the footer image."""
    if os.path.exists(FOOTER_PATH):
        return Image.open(FOOTER_PATH)

    footer_img = Image.new("RGBA", (TARGET_WIDTH, 150), (255, 255, 255, 255))
    draw_footer = ImageDraw.Draw(footer_img)

    # Centered Footer Text
    lines = FOOTER_TEXT.split("\n")
    start_y = (150 - (len(lines) * 40)) // 2  # Adjust text position
    for i, line in enumerate(lines):
        text_width = FOOTER_FONT.getbbox(line)[2]
        text_x = (TARGET_WIDTH - text_width) // 2
        draw_footer.text((text_x, start_y + (i * 40)), line, font=FOOTER_FONT, fill="black")

    footer_img.save(FOOTER_PATH)
    return footer_img

# Load pre-rendered footer
FOOTER_IMAGE = create_footer()
FOOTER_HEIGHT = FOOTER_IMAGE.height
PHOTO_AREA_HEIGHT = TARGET_HEIGHT - FOOTER_HEIGHT

def _is_url_allowed(url):
    """Validate that the URL host is in the allowlist (SSRF protection)."""
    parsed = urlparse(url)
    if not parsed.scheme or parsed.scheme not in ('http', 'https'):
        return False
    if not parsed.hostname:
        return False
    return parsed.hostname in ALLOWED_IMAGE_HOSTS


@app.route('/download_photo', methods=['POST'])
def download_photo():
    payload = request.get_json(silent=True)
    if payload is None:
        return jsonify({"error": "Invalid or missing JSON body"}), 400
    image_url = payload.get('imageUrl', '').strip()
    quote_text = payload.get('quote', '').strip()
    photo_credit = payload.get('photoCredit', '').strip()

    if not image_url or not quote_text:
        return jsonify({"error": "Missing required fields"}), 400

    # SSRF protection: only fetch URLs whose hosts came from our Photos sheet
    if not _is_url_allowed(image_url):
        logger.warning("Blocked disallowed image URL: %s", image_url)
        return jsonify({"error": "Image URL not allowed"}), 403

    try:
        # Log download metadata
        now = datetime.now()
        ip_address = request.remote_addr
        country, city = get_geolocation(ip_address)
        referring_url = request.headers.get('Referer')

        if downloads_sheet is None:
            return jsonify({"error": "Service unavailable"}), 503
        downloads_sheet.append_table(
            values=[[now.strftime('%Y-%m-%d'), now.strftime('%H:%M:%S'),
                     quote_text, image_url, ip_address, country, city, referring_url]],
            start='A1',
            end=None,
            dimension='ROWS',
            overwrite=False,
        )

        response = requests.get(image_url, timeout=15)
        response.raise_for_status()
        orig_img = Image.open(io.BytesIO(response.content)).convert("RGBA")

        # Resize image while maintaining aspect ratio
        scale = PHOTO_AREA_HEIGHT / orig_img.height
        new_width = int(orig_img.width * scale)
        resized_img = orig_img.resize((new_width, PHOTO_AREA_HEIGHT), Image.LANCZOS)

        # Crop or pad to fit exactly into TARGET_WIDTH
        if new_width > TARGET_WIDTH:
            left = (new_width - TARGET_WIDTH) // 2
            photo_area = resized_img.crop((left, 0, left + TARGET_WIDTH, PHOTO_AREA_HEIGHT))
        else:
            photo_area = Image.new("RGBA", (TARGET_WIDTH, PHOTO_AREA_HEIGHT), (0, 0, 0, 255))
            left = (TARGET_WIDTH - new_width) // 2
            photo_area.paste(resized_img, (left, 0))

        # Final image composition
        final_img = Image.new("RGBA", (TARGET_WIDTH, TARGET_HEIGHT), (255, 255, 255, 255))
        final_img.paste(photo_area, (0, 0))
        final_img.paste(FOOTER_IMAGE, (0, PHOTO_AREA_HEIGHT))

        # Create overlay for transparency
        overlay = Image.new("RGBA", final_img.size, (0, 0, 0, 0))
        overlay_draw = ImageDraw.Draw(overlay)

        box_opacity = 150
        corner_radius = 20
        padding = 20

        # Wrap and center quote text
        wrapped_lines = textwrap.wrap(quote_text, width=25)
        total_text_height = sum(QUOTE_FONT.getbbox(line)[3] for line in wrapped_lines) + (len(wrapped_lines) - 1) * 15
        max_text_width = max(QUOTE_FONT.getbbox(line)[2] for line in wrapped_lines)

        box_x1 = (TARGET_WIDTH - max_text_width) // 2 - padding
        box_x2 = box_x1 + max_text_width + (2 * padding)
        box_y1 = (PHOTO_AREA_HEIGHT - total_text_height) // 2
        box_y2 = box_y1 + total_text_height + (2 * padding)

        overlay_draw.rounded_rectangle([box_x1, box_y1, box_x2, box_y2], radius=corner_radius, fill=(0, 0, 0, box_opacity))

        # Render photo credit
        credit_box_x1 = 0
        credit_box_y1 = 0
        if photo_credit:
            bbox = overlay_draw.textbbox((0, 0), photo_credit, font=CREDIT_FONT)
            text_width, text_height = bbox[2] - bbox[0], bbox[3] - bbox[1]

            credit_box_x1 = TARGET_WIDTH - text_width - 2 * padding - 20
            credit_box_y1 = PHOTO_AREA_HEIGHT - text_height - 2 * padding - 20
            credit_box_x2 = credit_box_x1 + text_width + 2 * padding
            credit_box_y2 = credit_box_y1 + text_height + 2 * padding

            overlay_draw.rounded_rectangle([credit_box_x1, credit_box_y1, credit_box_x2, credit_box_y2], radius=corner_radius, fill=(0, 0, 0, box_opacity))

        # Merge overlay with final image
        final_img = Image.alpha_composite(final_img, overlay)

        # Draw wrapped text inside the box
        final_draw = ImageDraw.Draw(final_img)
        text_y = box_y1 + padding

        for line in wrapped_lines:
            text_width = QUOTE_FONT.getbbox(line)[2]
            text_x = (TARGET_WIDTH - text_width) // 2
            final_draw.text((text_x, text_y), line, font=QUOTE_FONT, fill="white")
            text_y += QUOTE_FONT.getbbox(line)[3] + 15

        # Draw photo credit text
        if photo_credit:
            final_draw.text((credit_box_x1 + padding, credit_box_y1 + padding), photo_credit, font=CREDIT_FONT, fill="white")

        img_buffer = io.BytesIO()
        final_img.save(img_buffer, format="PNG")
        img_buffer.seek(0)
        return send_file(img_buffer, mimetype="image/png", as_attachment=True, download_name="photo.png")
    except requests.exceptions.RequestException:
        logger.error("Failed to fetch image: %s", image_url)
        return jsonify({"error": "Error downloading image"}), 500
    except Exception as e:
        logger.error("Error in /download_photo: %s", e)
        return jsonify({"error": "Failed to generate image"}), 500


@app.route('/')
def index():
    return send_from_directory('public', 'index.html')

if __name__ == '__main__':
    app.run(debug=False)