"""Tests for the Virtual Sparkles Flask app.

These tests mock Google Sheets and external HTTP calls so they can run
without credentials, network access, or font files.
"""
import io
import json
import os
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image


# ---------------------------------------------------------------------------
# We need to patch heavy side effects before importing app.py, since it runs
# load_google_sheets() and create_footer() at module level.
# ---------------------------------------------------------------------------

SAMPLE_QUOTES = [
    {"Quote": "Stay strong", "AddedBy": "Alice"},
    {"Quote": "Keep going", "AddedBy": "Bob"},
]

SAMPLE_PHOTOS = [
    {
        "photoUrl": "https://images.example.com/photo1.jpg",
        "instagramName": "@photographer",
        "instagramLink": "https://instagram.com/photographer",
    },
]


def _make_test_image(width=100, height=100):
    """Create a small RGBA test image in memory."""
    return Image.new("RGBA", (width, height), (200, 200, 200, 255))


class FakeFont:
    """Minimal font mock that satisfies Pillow's ImageDraw text methods."""

    def getbbox(self, text, *args, **kwargs):
        return (0, 0, len(str(text)) * 10, 40)

    def getmask(self, text, *args, **kwargs):
        w = max(len(str(text)) * 10, 1)
        return Image.new("L", (w, 40), 255).im

    def getmask2(self, text, *args, **kwargs):
        w = max(len(str(text)) * 10, 1)
        return Image.new("L", (w, 40), 255).im, (0, 0)

    def getlength(self, text, *args, **kwargs):
        return len(str(text)) * 10.0

    @property
    def size(self):
        return 40


@pytest.fixture()
def client():
    """Create a Flask test client with all external dependencies mocked."""
    footer_img = _make_test_image(1080, 150)
    fake_font = FakeFont()

    with (
        patch("pygsheets.authorize") as mock_auth,
        patch("app.ImageFont.truetype", return_value=fake_font),
    ):
        # Mock pygsheets so load_google_sheets() succeeds
        mock_sh = MagicMock()
        mock_sh.worksheet_by_title.side_effect = lambda name: {
            "Quotes": MagicMock(get_all_records=MagicMock(return_value=SAMPLE_QUOTES)),
            "Photos": MagicMock(get_all_records=MagicMock(return_value=SAMPLE_PHOTOS)),
            "Likes": MagicMock(),
            "Downloads": MagicMock(),
        }[name]
        mock_auth.return_value.open_by_key.return_value = mock_sh

        # Reload the app module so module-level code runs with our mocks
        import importlib
        import app as app_module

        importlib.reload(app_module)

        # Replace module-level objects that depend on real files
        app_module.QUOTE_FONT = fake_font
        app_module.CREDIT_FONT = fake_font
        app_module.FOOTER_FONT = fake_font
        app_module.FOOTER_IMAGE = footer_img
        app_module.FOOTER_HEIGHT = footer_img.height
        app_module.PHOTO_AREA_HEIGHT = 1920 - footer_img.height

        app_module.app.config["TESTING"] = True
        with app_module.app.test_client() as c:
            yield c, app_module


# ---------------------------------------------------------------------------
# GET /data
# ---------------------------------------------------------------------------

class TestGetData:
    def test_returns_quote_and_photo(self, client):
        c, _ = client
        resp = c.get("/data")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "quote" in data
        assert "photoUrl" in data
        assert "addedBy" in data
        assert "instagramName" in data
        assert "instagramLink" in data

    def test_returns_known_values(self, client):
        c, _ = client
        resp = c.get("/data")
        data = resp.get_json()
        assert data["quote"] in ["Stay strong", "Keep going"]
        assert data["photoUrl"] == "https://images.example.com/photo1.jpg"

    def test_returns_500_when_no_data(self, client):
        c, app_module = client
        original_quotes = app_module.quotes_data
        app_module.quotes_data = []
        try:
            resp = c.get("/data")
            assert resp.status_code == 500
            assert "error" in resp.get_json()
        finally:
            app_module.quotes_data = original_quotes


# ---------------------------------------------------------------------------
# POST /like
# ---------------------------------------------------------------------------

class TestLike:
    def test_like_success(self, client):
        c, app_module = client
        app_module.likes_sheet = MagicMock()
        with patch.object(app_module, "get_geolocation", return_value=("US", "NYC")):
            resp = c.post(
                "/like",
                data=json.dumps({"quote": "Stay strong"}),
                content_type="application/json",
            )
        assert resp.status_code == 200
        assert resp.get_json()["result"] == "success"
        app_module.likes_sheet.append_table.assert_called_once()

    def test_like_missing_quote(self, client):
        c, _ = client
        resp = c.post(
            "/like",
            data=json.dumps({}),
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_like_no_json_body(self, client):
        c, _ = client
        resp = c.post("/like", data="not json", content_type="text/plain")
        assert resp.status_code == 400

    def test_like_sheets_unavailable(self, client):
        c, app_module = client
        app_module.likes_sheet = None
        with patch.object(app_module, "get_geolocation", return_value=(None, None)):
            resp = c.post(
                "/like",
                data=json.dumps({"quote": "test"}),
                content_type="application/json",
            )
        assert resp.status_code == 503


# ---------------------------------------------------------------------------
# POST /download_photo
# ---------------------------------------------------------------------------

class TestDownloadPhoto:
    def test_rejects_missing_json(self, client):
        c, _ = client
        resp = c.post("/download_photo", data="nope", content_type="text/plain")
        assert resp.status_code == 400

    def test_rejects_missing_fields(self, client):
        c, _ = client
        resp = c.post(
            "/download_photo",
            data=json.dumps({"imageUrl": "", "quote": "", "photoCredit": ""}),
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_rejects_disallowed_url(self, client):
        c, app_module = client
        # Ensure the allowlist does NOT include evil.com
        app_module.ALLOWED_IMAGE_HOSTS.discard("evil.com")
        resp = c.post(
            "/download_photo",
            data=json.dumps({
                "imageUrl": "https://evil.com/steal-data",
                "quote": "test",
                "photoCredit": "credit",
            }),
            content_type="application/json",
        )
        assert resp.status_code == 403
        assert "not allowed" in resp.get_json()["error"]

    def test_allows_valid_url_and_returns_image(self, client):
        c, app_module = client

        app_module.ALLOWED_IMAGE_HOSTS.add("images.example.com")
        app_module.downloads_sheet = MagicMock()

        # Use real fonts for the compositing test — Pillow's C layer
        # requires actual ImagingCore objects from real TrueType fonts.
        font_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "ARIAL.TTF"
        )
        if not os.path.exists(font_path):
            pytest.skip("ARIAL.TTF not found — skipping integration test")

        from PIL import ImageFont as RealImageFont
        app_module.QUOTE_FONT = RealImageFont.truetype(font_path, 70)
        app_module.CREDIT_FONT = RealImageFont.truetype(font_path, 24)

        # Create a fake image that requests.get will return
        fake_img = _make_test_image(800, 1200)
        img_bytes = io.BytesIO()
        fake_img.save(img_bytes, format="PNG")
        img_bytes.seek(0)

        mock_response = MagicMock()
        mock_response.content = img_bytes.read()
        mock_response.raise_for_status = MagicMock()

        with (
            patch.object(app_module, "get_geolocation", return_value=("US", "NYC")),
            patch("app.requests.get", return_value=mock_response),
        ):
            resp = c.post(
                "/download_photo",
                data=json.dumps({
                    "imageUrl": "https://images.example.com/photo1.jpg",
                    "quote": "Stay strong",
                    "photoCredit": "@photographer",
                }),
                content_type="application/json",
            )

        assert resp.status_code == 200
        assert resp.content_type == "image/png"
        result_img = Image.open(io.BytesIO(resp.data))
        assert result_img.size == (1080, 1920)

    def test_downloads_sheet_unavailable(self, client):
        c, app_module = client
        app_module.ALLOWED_IMAGE_HOSTS.add("images.example.com")
        app_module.downloads_sheet = None
        with patch.object(app_module, "get_geolocation", return_value=(None, None)):
            resp = c.post(
                "/download_photo",
                data=json.dumps({
                    "imageUrl": "https://images.example.com/photo1.jpg",
                    "quote": "test",
                    "photoCredit": "credit",
                }),
                content_type="application/json",
            )
        assert resp.status_code == 503


# ---------------------------------------------------------------------------
# SSRF allowlist
# ---------------------------------------------------------------------------

class TestSSRFProtection:
    def test_is_url_allowed_rejects_no_scheme(self, client):
        _, app_module = client
        assert not app_module._is_url_allowed("//evil.com/image.png")

    def test_is_url_allowed_rejects_ftp(self, client):
        _, app_module = client
        assert not app_module._is_url_allowed("ftp://evil.com/image.png")

    def test_is_url_allowed_rejects_unknown_host(self, client):
        _, app_module = client
        app_module.ALLOWED_IMAGE_HOSTS.discard("evil.com")
        assert not app_module._is_url_allowed("https://evil.com/image.png")

    def test_is_url_allowed_accepts_known_host(self, client):
        _, app_module = client
        app_module.ALLOWED_IMAGE_HOSTS.add("images.example.com")
        assert app_module._is_url_allowed("https://images.example.com/photo.jpg")


# ---------------------------------------------------------------------------
# GET / (index)
# ---------------------------------------------------------------------------

class TestIndex:
    def test_serves_index_html(self, client):
        c, _ = client
        resp = c.get("/")
        assert resp.status_code == 200
        assert b"Virtual Sparkles" in resp.data
