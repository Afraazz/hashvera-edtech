from importlib import import_module
from pathlib import Path
import re

try:
    sync_playwright = import_module("playwright.sync_api").sync_playwright
except ImportError as exc:
    raise RuntimeError(
        "Playwright is required. Install it with 'pip install playwright' "
        "and then run 'playwright install chromium'."
    ) from exc

BASE_URL = "http://127.0.0.1:5000"

# Routes detected from the original project.
# Only GET/browser-style pages should be added here.
ROUTES = ['/', '/login', '/register', '/verify', '/terms', '/privacy', '/faq', '/support', '/network/audit', '/certificate/verify', '/users', '/support-inbox', '/peers', '/audit-logs', '/system/bulk-issue', '/system', '/system/test-email', '/system/backup', '/system/import', '/export-pdf', '/export', '/security-audit', '/assistant', '/health', '/chain', '/chain/sync', '/logout', '/register/campus-lookup', '/forgot-password', '/forgot-password/verify', '/forgot-password/resend-code', '/forgot-password/reset', '/change-password', '/support/new', '/ledger/verify/ajax', '/chain/explorer', '/dashboard', '/portfolio', '/my-records', '/add', '/ledger/verify', '/notifications', '/notifications/mark-read', '/profile/settings', '/profiles', '/review-queue', '/archived', '/submit-request', '/bulk-mint', '/bulk-mint/template']

OUTPUT = Path("project-snapshots")
OUTPUT.mkdir(exist_ok=True)

def safe_name(route):
    if route == "/":
        return "01-home.png"
    name = re.sub(r"[^a-zA-Z0-9]+", "-", route.strip("/")).strip("-")
    return name + ".png"

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 1440, "height": 900})

    for route in ROUTES:
        url = BASE_URL + route
        print(f"Capturing: {url}")
        try:
            response = page.goto(url, wait_until="networkidle", timeout=30000)
            page.wait_for_timeout(1000)

            status = response.status if response else "unknown"
            print(f"  HTTP status: {status}")

            page.screenshot(
                path=str(OUTPUT / safe_name(route)),
                full_page=True
            )
            print(f"  Saved: {OUTPUT / safe_name(route)}")

        except Exception as e:
            print(f"  FAILED: {e}")

    browser.close()

print("\nSnapshot complete.")
print(f"Open the '{OUTPUT}' folder to see the screenshots.")
