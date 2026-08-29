"""Layout helpers for wkhtmltopdf 0.12.6 (Qt4).

min-height on tables is ignored by this engine. A single computed spacer
height is the stable way to park signatures in the lower third on short
documents without position:absolute.
"""

_DX_SPACER_GIF = (
    "data:image/gif;base64," "R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7"
)


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
