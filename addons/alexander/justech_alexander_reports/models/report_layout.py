"""Layout helpers for wkhtmltopdf 0.12.6 (Qt4).

min-height, transparent borders and stretched 1x1 GIFs are ignored or
collapsed. A real white PNG with intrinsic height is the stable spacer.
"""

import base64
import struct
import zlib

_DX_SPACER_GIF = (
    "data:image/gif;base64," "R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7"
)


def white_png_data_uri(height_px, width_px=2):
    """Tiny true-size white PNG so Qt4 cannot collapse the spacer."""
    h = max(1, int(height_px or 1))
    w = max(1, int(width_px or 2))

    def chunk(tag, data):
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    raw = b"".join(b"\x00" + (b"\xff" * (w * 3)) for _ in range(h))
    png = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw, 9))
        + chunk(b"IEND", b"")
    )
    return "data:image/png;base64," + base64.b64encode(png).decode("ascii")


def count_body_lines(lines):
    return sum(1 for line in lines or [] if (line or {}).get("kind") == "line")


def spacer_mm(line_count, paper="A4", extra_mm=0):
    """Return spacer millimetres so signatures sit in the last third.

    1 / 3 / 8 lines get a gap. 15+ lines collapse the spacer so totals and
    signatures stay with the table instead of jumping to an empty page.
    """
    n = int(line_count or 0)
    extra = float(extra_mm or 0)
    if paper == "A5":
        useful = 125.0
        party = 42.0
        line_h = 7.0
        tail = 28.0
        target = 96.0
    else:
        useful = 198.0
        party = 40.0
        line_h = 8.0
        tail = 40.0
        target = 168.0
    used = party + 8.0 + n * line_h + extra
    gap = min(target - used, useful - used - tail)
    if gap < 8:
        return 0
    return int(round(gap))
