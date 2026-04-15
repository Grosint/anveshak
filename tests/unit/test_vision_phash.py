"""Unit tests: pHash computation and Hamming distance logic.

Criteria 4.6: pHash stored as BIGINT (Python int).
Criteria 4.25–4.27: reverse lookup uses Hamming distance threshold from settings.
"""
import io
import pytest
from unittest.mock import patch, MagicMock


# ---------------------------------------------------------------------------
# Tests: pHash computation
# ---------------------------------------------------------------------------

class TestComputePhash:
    @pytest.mark.unit
    def test_phash_returns_int(self):
        """compute_phash() must return Python int (stored as BIGINT in DB)."""
        from PIL import Image
        import numpy as np

        # Create a simple 100x100 red image for testing
        img = Image.fromarray(np.zeros((100, 100, 3), dtype=np.uint8) + np.array([255, 0, 0], dtype=np.uint8))
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        image_bytes = buf.getvalue()

        from anveshak.vision.media_store import compute_phash
        result = compute_phash(image_bytes)
        assert result is not None
        assert isinstance(result, int)

    @pytest.mark.unit
    def test_phash_same_image_deterministic(self):
        """Same image bytes → same pHash value (deterministic)."""
        from PIL import Image
        import numpy as np

        arr = np.zeros((100, 100, 3), dtype=np.uint8)
        arr[40:60, 40:60] = [200, 100, 50]  # a small coloured square
        img = Image.fromarray(arr)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        image_bytes = buf.getvalue()

        from anveshak.vision.media_store import compute_phash
        result1 = compute_phash(image_bytes)
        result2 = compute_phash(image_bytes)
        assert result1 == result2

    @pytest.mark.unit
    def test_phash_different_images_differ(self):
        """Different images → different pHash values."""
        from PIL import Image
        import numpy as np

        def _make_checkerboard(block_size: int, invert: bool) -> bytes:
            # Checkerboard pattern in grayscale — pHash uses DCT of grayscale,
            # so solid-colour images (zero AC components) produce identical hashes.
            # Two checkerboards with opposite polarity are perceptually distinct.
            arr = np.zeros((64, 64, 3), dtype=np.uint8)
            for r in range(64):
                for c in range(64):
                    cell = (r // block_size + c // block_size) % 2
                    val = 255 if (cell == 0) ^ invert else 0
                    arr[r, c] = [val, val, val]
            buf = io.BytesIO()
            Image.fromarray(arr).save(buf, format="PNG")  # PNG avoids JPEG artefacts
            return buf.getvalue()

        from anveshak.vision.media_store import compute_phash
        h1 = compute_phash(_make_checkerboard(8, invert=False))
        h2 = compute_phash(_make_checkerboard(8, invert=True))
        # Opposite-polarity checkerboards are perceptually distinct
        assert h1 != h2

    @pytest.mark.unit
    def test_phash_none_on_invalid_bytes(self):
        """compute_phash() returns None for non-image bytes (graceful failure)."""
        from anveshak.vision.media_store import compute_phash
        result = compute_phash(b"not an image at all")
        assert result is None


# ---------------------------------------------------------------------------
# Tests: EXIF extraction
# ---------------------------------------------------------------------------

class TestExtractExif:
    @pytest.mark.unit
    def test_exif_returns_dict(self):
        """extract_exif() returns a dict (possibly empty, never None for valid image)."""
        from PIL import Image
        import numpy as np

        arr = np.zeros((50, 50, 3), dtype=np.uint8)
        buf = io.BytesIO()
        Image.fromarray(arr).save(buf, format="JPEG")

        from anveshak.vision.media_store import extract_exif
        result = extract_exif(buf.getvalue(), backend="pillow")
        assert isinstance(result, dict)

    @pytest.mark.unit
    def test_exif_ai_software_detected_flag_present(self):
        """extract_exif() always includes 'ai_software_detected' boolean key."""
        from PIL import Image
        import numpy as np

        arr = np.zeros((50, 50, 3), dtype=np.uint8)
        buf = io.BytesIO()
        Image.fromarray(arr).save(buf, format="JPEG")

        from anveshak.vision.media_store import extract_exif
        result = extract_exif(buf.getvalue(), backend="pillow")
        assert "ai_software_detected" in result
