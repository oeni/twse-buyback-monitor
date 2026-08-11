"""Shared fixtures for the test suite."""
from __future__ import annotations

from pathlib import Path

FIXTURE_DIR = Path(__file__).parent / "fixtures"
SAMPLE_HTML = (FIXTURE_DIR / "t35sc09_sample.html").read_text(encoding="utf-8")

_HEAD = (
    "<html><head><title>公開資訊觀測站</title></head><body>\n"
    "<table class='noBorder'><tr><td class='reportName'>"
    "上市公司買回自己公司股份彙總統計表</td></tr></table>\n"
    "<table class='hasBorder'>\n"
)
_TAIL = "</table>\n</body></html>\n"


def data_row(code, board_date="115/08/01", purpose="1", period_start="115/08/02",
             period_end="115/10/01", done="N", bought="", ratio="", amount="",
             note="", seq="1", name=None):
    """One 20-cell table row, matching the live column layout."""
    cells = [
        seq, code, name or f"公司{code}", board_date, purpose, "1,000,000,000",
        "1,000,000", "10.00", "20.00", period_start, period_end,
        done, "", bought, "", ratio, amount, "15.00", "0.50", note,
    ]
    return "<tr>" + "".join(f"<td>{c}</td>" for c in cells) + "</tr>\n"


def build_html(rows, complete=True):
    """Assemble a response body.

    Args:
        rows: Iterable of row strings from :func:`data_row`.
        complete: When False, the body is cut off mid-table exactly the way a
            truncated MOPS response is -- valid rows, no closing tags.
    """
    body = _HEAD + "".join(rows)
    return body + _TAIL if complete else body


def codes_html(codes, complete=True, **kwargs):
    """Response containing one case per stock code."""
    return build_html([data_row(c, **kwargs) for c in codes], complete=complete)


class FakeSession:
    """Stands in for ``requests.Session``, returning canned bodies in order.

    The last body is reused once the script is exhausted, so a test only has to
    describe the attempts it cares about.
    """

    def __init__(self, bodies):
        self.bodies = list(bodies)
        self.calls = 0

    def post(self, url, data=None, headers=None, timeout=None):
        body = self.bodies[min(self.calls, len(self.bodies) - 1)]
        self.calls += 1
        return FakeResponse(body)


class FakeResponse:
    def __init__(self, text, status_code=200):
        self.status_code = status_code
        self.content = text.encode("utf-8")
        self.headers = {}


def no_sleep(_seconds):
    """Injected in place of ``time.sleep`` so retry tests run instantly."""
