"""
Integration tests for pagination API.

These tests verify that:
1. Initial page load returns exactly 25 rows
2. The rows.lua endpoint correctly returns cursor-based pagination
3. All 1000 rows can be fetched by following pagination cursors

Run with: pytest tests/test_pagination.py -v

Note: Requires a running redbean server on port 9876. Start it manually:
  ./dist/contacts_1000_test.redbean.com -p 9876
"""

import subprocess
import time
from pathlib import Path

import pytest
import requests
from bs4 import BeautifulSoup


def extract_rows_from_html(html: str) -> list[dict]:
    """Parse table rows from HTML response."""
    soup = BeautifulSoup(html, "html.parser")
    rows = []
    for tr in soup.find_all("tr"):
        # Skip header and sentinel rows
        if tr.get("id", "").startswith("load-more"):
            continue
        if tr.find("th"):
            continue
        tds = tr.find_all("td")
        if tds and len(tds) >= 4:
            rows.append(
                {
                    "name": tds[0].text.strip(),
                    "email": tds[1].text.strip(),
                    "age": tds[2].text.strip(),
                    "subscribed": tds[3].text.strip(),
                }
            )
    return rows


def extract_cursor_from_html(html: str) -> str | None:
    """Extract the next cursor from the load-more sentinel row."""
    soup = BeautifulSoup(html, "html.parser")
    sentinel = soup.find("tr", id=lambda x: x and x.startswith("load-more"))
    if not sentinel:
        return None
    # Extract cursor from id like "load-more-976"
    row_id = sentinel.get("id", "")
    if row_id.startswith("load-more-"):
        cursor = row_id.replace("load-more-", "")
        return cursor
    return None


@pytest.fixture(scope="session", autouse=True)
def ensure_server():
    """Ensure server is running. If not, start it."""
    base_url = "http://127.0.0.1:9876"
    
    for attempt in range(3):
        try:
            response = requests.get(base_url, timeout=2)
            if response.status_code == 200:
                yield
                return
        except requests.exceptions.RequestException:
            time.sleep(0.5)
    
    # Server not running, try to start it
    workspace = Path(__file__).parent.parent
    dist_file = workspace / "dist" / "contacts_1000_test.redbean.com"
    
    if not dist_file.exists():
        # Build it
        result = subprocess.run(
            [
                "uv",
                "run",
                "csvpak",
                "build",
                "--data",
                str(workspace / "examples" / "contacts" / "contacts_1000.csv"),
                "--schema",
                str(workspace / "examples" / "contacts" / "contacts.json"),
                "--output",
                str(dist_file),
            ],
            cwd=workspace,
            capture_output=True,
            timeout=30,
        )
        if result.returncode != 0:
            pytest.skip(f"Could not build distributable: {result.stderr}")
    
    # Start server
    subprocess.Popen(
        f"{dist_file} -p 9876 > /dev/null 2>&1",
        shell=True,
        preexec_fn=getattr(__import__("os"), "setsid", None),
    )
    time.sleep(2)
    
    # Verify it started
    for attempt in range(10):
        try:
            response = requests.get(base_url, timeout=2)
            if response.status_code == 200:
                yield
                return
        except requests.exceptions.RequestException:
            time.sleep(0.5)
    
    pytest.skip("Could not start or connect to server on port 9876")


def test_initial_page_load(ensure_server):
    """Test that the initial page load returns exactly 25 rows + sentinel."""
    response = requests.get("http://127.0.0.1:9876/", timeout=5)
    assert response.status_code == 200

    rows = extract_rows_from_html(response.text)
    cursor = extract_cursor_from_html(response.text)

    assert len(rows) == 25, f"Expected 25 rows, got {len(rows)}"
    assert cursor is not None, "Expected load-more sentinel with cursor"
    assert cursor == "976", f"Expected cursor 976 (rowid of 26th row), got {cursor}"


def test_pagination_full_cycle(ensure_server):
    """Test fetching all pages through pagination cursors."""
    all_rows = []
    response = requests.get("http://127.0.0.1:9876/", timeout=5)
    assert response.status_code == 200

    # Collect initial 25 rows
    rows = extract_rows_from_html(response.text)
    all_rows.extend(rows)
    cursor = extract_cursor_from_html(response.text)

    assert len(rows) == 25
    assert cursor is not None

    # Follow pagination until no more rows
    page_count = 1
    max_pages = 50  # Safety limit
    while cursor is not None and page_count < max_pages:
        response = requests.get(
            f"http://127.0.0.1:9876/rows.lua?cursor={cursor}&limit=25", timeout=5
        )
        assert response.status_code == 200, f"Failed to fetch page {page_count + 1}"

        rows = extract_rows_from_html(response.text)
        if not rows:
            # Last page with only sentinel
            break

        all_rows.extend(rows)
        cursor = extract_cursor_from_html(response.text)
        page_count += 1

    assert len(all_rows) == 1000, f"Expected 1000 total rows, got {len(all_rows)}"
    assert page_count == 40, f"Expected 40 pages (1000 rows / 25 per page), got {page_count}"


def test_rows_endpoint_with_cursor(ensure_server):
    """Test the /rows.lua endpoint with a specific cursor."""
    # Start from cursor=976 (the sentinel cursor from first page)
    response = requests.get(
        "http://127.0.0.1:9876/rows.lua?cursor=976&limit=25", timeout=5
    )
    assert response.status_code == 200

    rows = extract_rows_from_html(response.text)
    cursor = extract_cursor_from_html(response.text)

    assert len(rows) == 25, f"Expected 25 rows, got {len(rows)}"
    assert cursor is not None, "Expected cursor in response"
    # The next cursor should be 951 (976 - 25)
    assert cursor == "951", f"Expected cursor 951, got {cursor}"


def test_rows_endpoint_last_page(ensure_server):
    """Test the /rows.lua endpoint on the final page."""
    # Skip to near the end: 26 rows remaining (25 + 1 over limit)
    response = requests.get(
        "http://127.0.0.1:9876/rows.lua?cursor=26&limit=25", timeout=5
    )
    assert response.status_code == 200

    rows = extract_rows_from_html(response.text)
    cursor = extract_cursor_from_html(response.text)

    # Should have 25 rows (the last 25)
    assert len(rows) == 25, f"Expected 25 rows on last page, got {len(rows)}"
    # No sentinel on last page (cursor should be None or pointing to 1)
    # If there's a sentinel, it means there's still one more row
    if cursor:
        # Fetch one more time
        response = requests.get(
            f"http://127.0.0.1:9876/rows.lua?cursor={cursor}&limit=25", timeout=5
        )
        rows = extract_rows_from_html(response.text)
        assert len(rows) <= 1, f"Expected <=1 row, got {len(rows)}"

