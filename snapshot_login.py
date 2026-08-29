from playwright.sync_api import sync_playwright
from pathlib import Path
import time

BASE_URL = "http://127.0.0.1:5000"
LOGIN_URL = BASE_URL + "/login"
OUTPUT = Path("project-snapshots")
OUTPUT.mkdir(exist_ok=True)

# Use a separate browser profile so the login is fully interactive.
PROFILE = Path("snapshot-browser-profile")
PROFILE.mkdir(exist_ok=True)

# These are the main visual pages from the original project.
ROUTES = [
    ("/", "home"),
    ("/dashboard", "dashboard"),
    ("/portfolio", "portfolio"),
    ("/my-records", "my-records"),
    ("/add", "add-record"),
    ("/notifications", "notifications"),
    ("/profile/settings", "profile-settings"),
    ("/profiles", "profiles"),
    ("/review-queue", "review-queue"),
    ("/archived", "archived"),
    ("/peers", "peers"),
    ("/users", "users"),
    ("/support", "support"),
    ("/faq", "faq"),
    ("/network/audit", "network-audit"),
    ("/chain", "chain"),
    ("/chain/explorer", "chain-explorer"),
    ("/audit-logs", "audit-logs"),
    ("/security-audit", "security-audit"),
    ("/assistant", "assistant"),
    ("/system", "system"),
]

with sync_playwright() as p:
    print("=" * 65)
    print("HASHVERA FULL PROJECT SNAPSHOT")
    print("=" * 65)
    print()
    print("Opening a separate interactive Chromium profile...")
    print()

    context = p.chromium.launch_persistent_context(
        user_data_dir=str(PROFILE.resolve()),
        headless=False,
        viewport={"width": 1440, "height": 900},
        args=["--start-maximized"]
    )

    page = context.pages[0] if context.pages else context.new_page()

    page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=30000)

    print("Chromium is open.")
    print()
    print("LOGIN IN THE BROWSER WINDOW:")
    print("  1. Enter your Campus Email ID.")
    print("  2. Enter your password.")
    print("  3. Click the login button.")
    print("  4. Wait until your dashboard is visible.")
    print()
    print("IMPORTANT: Keep the browser window open.")
    input("After you are logged in, return here and press ENTER... ")

    print()
    print("Starting snapshots...")
    print()

    captured = 0
    skipped = 0

    for route, name in ROUTES:
        url = BASE_URL + route
        print(f"Capturing {route}...")

        try:
            response = page.goto(
                url,
                wait_until="networkidle",
                timeout=30000
            )
            page.wait_for_timeout(1000)

            status = response.status if response else "unknown"
            final_url = page.url

            # Protected route redirected to login.
            if "/login" in final_url and route != "/login":
                print("  SKIPPED - redirected to login")
                skipped += 1
                continue

            # Avoid obvious 404 pages.
            body = page.locator("body").inner_text(timeout=5000).lower()
            if status == 404 or "page not found" in body:
                print("  SKIPPED - 404/page not found")
                skipped += 1
                continue

            filename = OUTPUT / f"{name}.png"

            page.screenshot(
                path=str(filename),
                full_page=True
            )

            print(f"  SAVED -> {filename}")
            captured += 1

        except Exception as error:
            print(f"  FAILED -> {error}")
            skipped += 1

    context.close()

print()
print("=" * 65)
print("SNAPSHOT COMPLETE")
print("=" * 65)
print(f"Captured: {captured}")
print(f"Skipped/failed: {skipped}")
print(f"Snapshots folder: {OUTPUT.resolve()}")
