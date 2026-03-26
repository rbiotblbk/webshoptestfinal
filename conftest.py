"""
conftest.py — Pytest configuration and shared fixtures for the Webshop test suite.

Provides:
  - base_url fixture
  - browser_context_args fixture
  - authenticated_page / authenticated_page_user1 fixtures
  - Helper functions: _login, add_product_to_cart, complete_shipping_step,
    complete_payment_step
  - pytest_configure hook (custom markers)
  - pytest_runtest_makereport hookimpl (screenshot on failure)
"""

import os
import re
from pathlib import Path

import pytest
from playwright.sync_api import Page, BrowserContext, expect


# ---------------------------------------------------------------------------
# Directories
# ---------------------------------------------------------------------------
SCREENSHOTS_DIR = Path("test-results/screenshots")
SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

ENVIRONMENTS = {
    "local": "http://localhost",
    "dev":   "http://localhost:5173",
    "prod":  "https://webshop.xpert-hub.com",
}


@pytest.fixture(scope="session")
def base_url(request) -> str:
    """Return the base URL for the webshop under test.

    Resolution order (first match wins):
      1. --base-url  CLI flag:   pytest --base-url=https://webshop.xpert-hub.com
      2. --env       CLI flag:   pytest --env=prod   (local | dev | prod)
      3. BASE_URL    env var:    BASE_URL=https://webshop.xpert-hub.com pytest
      4. Default: http://localhost  (local Docker)

    Named environments:
      local  →  http://localhost          (Docker, default)
      dev    →  http://localhost:5173     (Vite dev server)
      prod   →  https://webshop.xpert-hub.com
    """
    # 1. Explicit --base-url flag
    try:
        cli_url = request.config.getoption("--base-url")
        if cli_url:
            return cli_url.rstrip("/")
    except ValueError:
        pass

    # 2. Named --env flag
    try:
        env_name = request.config.getoption("--env")
        if env_name:
            resolved = ENVIRONMENTS.get(env_name.lower())
            if not resolved:
                raise ValueError(
                    f"Unknown --env value '{env_name}'. "
                    f"Choose from: {', '.join(ENVIRONMENTS)}"
                )
            return resolved
    except ValueError as exc:
        if "Unknown --env" in str(exc):
            raise
        pass  # option not registered yet

    # 3. BASE_URL environment variable
    env_url = os.environ.get("BASE_URL", "").strip().rstrip("/")
    if env_url:
        return env_url

    # 4. Default
    return ENVIRONMENTS["local"]


def pytest_addoption(parser):
    """Register --env CLI option alongside pytest-playwright's --base-url."""
    parser.addoption(
        "--env",
        action="store",
        default=None,
        choices=list(ENVIRONMENTS.keys()),
        help=(
            "Named target environment: "
            "local (http://localhost), "
            "dev (http://localhost:5173), "
            "prod (https://webshop.xpert-hub.com)"
        ),
    )


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):
    """Override default browser context args to set viewport and video size."""
    return {
        **browser_context_args,
        "record_video_size": {"width": 1280, "height": 720},
        "viewport": {"width": 1280, "height": 720},
    }


@pytest.fixture
def authenticated_page(page: Page, base_url: str) -> Page:
    """Return a page that is already logged in as user2 (Password@2).

    user2 has a policy-compliant password and is the primary test user.
    """
    _login(page, base_url, "user2", "Password@2")
    return page


@pytest.fixture
def authenticated_page_user1(page: Page, base_url: str) -> Page:
    """Return a page that is already logged in as user1 (password123).

    Note: user1's password violates the password policy (BUG Auth1).
    """
    _login(page, base_url, "user1", "password123")
    return page


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _login(page: Page, base_url: str, username: str, password: str) -> None:
    """Navigate to /login and authenticate with the given credentials.

    Waits for network idle after submission to confirm redirect.
    """
    page.goto(f"{base_url}/login")
    page.wait_for_load_state("networkidle")
    page.fill("#username", username)
    page.fill("#password", password)
    page.click("button[type='submit']")
    page.wait_for_load_state("networkidle")


def add_product_to_cart(
    page: Page,
    base_url: str,
    product_name: str | None = None,
    category: str | None = None,
) -> None:
    """Navigate to the products page and add a product to the cart.

    If product_name is provided the function finds that specific card and
    clicks its "Add to Cart" button.  If only category is provided it clicks
    the category button and then adds the first available product.

    Args:
        page:         The Playwright page object.
        base_url:     Root URL of the application.
        product_name: Exact text of the product to add (optional).
        category:     Category button label to filter by first (optional).
    """
    page.goto(f"{base_url}/products")
    page.wait_for_load_state("networkidle")

    if category:
        page.click(f"button.category-btn:text('{category}')")
        page.wait_for_load_state("networkidle")

    if product_name:
        # Find the card containing the product name
        card = page.locator(".product-card").filter(has_text=product_name)
        card.locator("button:text('Add to Cart')").click()
    else:
        # Click the first available "Add to Cart" button
        page.locator(".product-card button:text('Add to Cart')").first.click()

    page.wait_for_load_state("networkidle")


def complete_shipping_step(
    page: Page,
    full_name: str = "Test User",
    street: str = "123 Test Street",
    city: str = "Testville",
    postcode: str = "TE5 7ST",
    country: str = "Testland",
) -> None:
    """Fill the shipping details form (step 1 of checkout) and continue.

    Uses nth-based selectors because the shipping inputs have no IDs.
    The order is: Full Name (0), Street Address (1), City (2),
    Postcode (3), Country (4).

    Args:
        page:      The Playwright page object (should be on /checkout).
        full_name: Cardholder / recipient full name.
        street:    Street address line.
        city:      City name.
        postcode:  Postal / ZIP code.
        country:   Country name.
    """
    inputs = page.locator(".checkout-step input.form-control")
    inputs.nth(0).fill(full_name)
    inputs.nth(1).fill(street)
    inputs.nth(2).fill(city)
    inputs.nth(3).fill(postcode)
    inputs.nth(4).fill(country)
    page.click("button:text('Continue to Payment')")
    page.wait_for_load_state("networkidle")


def complete_payment_step(
    page: Page,
    cardholder: str = "Test User",
    card_number: str = "4111111111111111",
    expiry: str = "12/99",
    cvv: str = "123",
) -> None:
    """Fill the payment details form (step 2 of checkout) and click Review Order.

    Args:
        page:        The Playwright page object (should be on payment step).
        cardholder:  Name as shown on card.
        card_number: 16-digit card number string.
        expiry:      Expiry date in MM/YY format.
        cvv:         3- or 4-digit security code.
    """
    page.fill("input[placeholder='As shown on card']", cardholder)
    page.fill("input[placeholder='1234 5678 9012 3456']", card_number)
    page.fill("input[placeholder='MM/YY']", expiry)
    page.fill("input[placeholder='123']", cvv)
    page.click("button:text('Review Order')")
    page.wait_for_load_state("networkidle")


# ---------------------------------------------------------------------------
# pytest hooks
# ---------------------------------------------------------------------------

def pytest_configure(config):
    """Register custom markers so pytest does not warn about unknown markers."""
    markers = [
        "auth: Authentication-related tests",
        "products: Product display and filtering tests",
        "cart: Shopping cart tests",
        "checkout: Checkout and purchase flow tests",
        "database: Database integrity and API tests",
        "smoke: Smoke tests for basic functionality",
        "regression: Regression tests",
        "bug_auth1: BUG Auth1 - user1 password violates policy",
        "bug_auth2: BUG Auth2 - password validation only checks length",
        "bug_auth3: BUG Auth3 - MD5 used instead of bcrypt",
        "bug_auth4: BUG Auth4 - Session timeout too long",
        "bug_auth5: BUG Auth5 - No account lockout",
        "bug_pd1: BUG PD1 - Electronics images wrong path",
        "bug_pd2: BUG PD2 - Price filter max exclusive",
        "bug_pd3: BUG PD3 - Add to Cart hidden on mobile for Books",
        "bug_pd4: BUG PD4 - Out of stock always shows In Stock",
        "bug_pd5: BUG PD5 - Price sort uses string comparison",
        "bug_cart1: BUG Cart1 - No max 10 items limit",
        "bug_cart2: BUG Cart2 - Tax rate 5% instead of 10%",
        "bug_cart3: BUG Cart3 - TEST10 applies 20% not 10%",
        "bug_cart4: BUG Cart4 - Cart total not updated after removal",
        "bug_cart5: BUG Cart5 - Cart persists after logout",
        "bug_purchase1: BUG Purchase1 - Order created before payment validation",
        "bug_purchase2: BUG Purchase2 - CVV accepts 5 digits",
        "bug_purchase3: BUG Purchase3 - Expired dates accepted",
        "bug_purchase4: BUG Purchase4 - Order history shows all users orders",
        "bug_purchase5: BUG Purchase5 - No order confirmation message",
        "bug_db1: BUG DB1 - Missing foreign key on orders.user_id",
        "bug_db2: BUG DB2 - Product deletion cascades",
        "bug_db3: BUG DB3 - cart_items allows negative quantities",
    ]
    for marker in markers:
        config.addinivalue_line("markers", marker)


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Take an extra screenshot on test failure and save to test-results/screenshots/."""
    outcome = yield
    report = outcome.get_result()

    if report.when == "call" and report.failed:
        # Retrieve the page fixture if it exists in the test
        page: Page | None = item.funcargs.get("page") or item.funcargs.get(
            "authenticated_page"
        ) or item.funcargs.get("authenticated_page_user1")

        if page is not None:
            safe_name = re.sub(r"[^\w\-]", "_", item.nodeid)
            screenshot_path = SCREENSHOTS_DIR / f"{safe_name}.png"
            screenshot_path.parent.mkdir(parents=True, exist_ok=True)
            try:
                page.screenshot(path=str(screenshot_path), full_page=True)
            except Exception:
                pass  # Don't let screenshot errors mask the real failure
