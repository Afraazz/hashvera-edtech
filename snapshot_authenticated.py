from importlib import import_module

try:
    sync_playwright = import_module("playwright.sync_api").sync_playwright
except ModuleNotFoundError as error:
    raise SystemExit(
        "Playwright is required. Install it with "
        "'python -m pip install playwright' and then run "
        "'python -m playwright install chromium'."
    ) from error
from pathlib import Path
import re

BASE_URL = "http://127.0.0.1:5000"
LOGIN_URL = BASE_URL + "/login"

# Main UI pages detected in the original project.
# Pages that require a different role/login will simply be skipped
# if the application redirects them back to /login.
ROUTES = [
    ("/", "home"),
    ("/login", "login"),
    ("/register", "register"),
    ("/verify", "verify"),
    ("/forgot-password", "forgot-password"),
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

OUTPUT = Path("project-snapshots")
OUTPUT.mkdir(exist_ok=True)

SESSION_FILE = OUTPUT / "browser-session.json"

with sync_playwright() as p:
    browser = p.chromium.launch()
    context = browser.new_context(
        viewport={"width": 1440, "height": 900}
    )
    page = context.new_page()

    # Open login page and let the user log in manually.
    print("=" * 65)
    print("HASHVERA FULL PROJECT SNAPSHOT")
    print("=" * 65)
    print()
    print("Opening the login page...")
    print()

    page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=30000)

    print("A Chromium browser window has opened.")
    print()
    print("1. Enter your Campus Email ID.")
    print("2. Enter your password.")
    print("3. Click 'Login to Dashboard'.")
    print("4. Wait until the dashboard appears.")
    print()
    input("When you are successfully logged in, come back here and press ENTER... ")

    # Save the authenticated session.
    context.storage_state(path=str(SESSION_FILE))
    print(f"\nLogin session saved to: {SESSION_FILE}")

    print("\nCapturing pages...\n")

    captured = 0
    skipped = 0

    for route, name in ROUTES:
        url = BASE_URL + route
        print(f"[{route}]")

        try:
            response = page.goto(
                url,
                wait_until="networkidle",
                timeout=30000
            )
            page.wait_for_timeout(700)

            final_url = page.url
            status = response.status if response else "unknown"

            # If the app redirected us to login, this route is protected
            # by a permission/role that the current account does not have.
            if "/login" in final_url and route != "/login":
                print("  SKIPPED: redirected to login (not available for this account)")
                skipped += 1
                continue

            # Don't save obvious error pages.
            title = (page.title() or "").lower()
            body_start = (page.locator("body").inner_text()[:1000]).lower()

            if status == 404 or "page not found" in body_start or "404" in title:
                print(f"  SKIPPED: page returned {status}/404")
                skipped += 1
                continue

            filename = f"{name}.png"
            path = OUTPUT / filename

            page.screenshot(
                path=str(path),
                full_page=True
            )

            print(f"  SAVED: {path}")
            print(f"  HTTP: {status}")
            print(f"  URL:  {final_url}")
            captured += 1

        except Exception as e:
            print(f"  FAILED: {e}")
            skipped += 1

    browser.close()

print("\n" + "=" * 65)
print("SNAPSHOT COMPLETE")
print("=" * 65)
print(f"Captured: {captured}")
print(f"Skipped/failed: {skipped}")
print(f"Folder: {OUTPUT.resolve()}")
print()
print("Your screenshots are in the project-snapshots folder.")
