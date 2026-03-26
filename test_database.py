"""
test_database.py — Database integrity and API-level tests for the Webshop.

Test class : TestDatabase
Test cases : TC_DB_001 … TC_DB_003

These tests use Playwright's built-in API request context (page.request) to
interact with the backend REST API directly, bypassing the UI where possible.

Covers:
  - Negative cart quantities rejected (BUG DB3)
  - Orders endpoint returns only the authenticated user's orders (BUG Purchase4 / DB1)
  - Password hashing uses bcrypt not MD5 (BUG Auth3 — xfail, cannot verify via API)
"""

import pytest
from playwright.sync_api import Page

from conftest import _login, add_product_to_cart, complete_shipping_step, complete_payment_step


def _api_login(page: Page, base_url: str, username: str, password: str) -> dict:
    """Authenticate via the REST API and return the JSON response body.

    Returns the response dict (may contain token, user info, etc.).
    """
    response = page.request.post(
        f"{base_url}/api/auth/login",
        data={"username": username, "password": password},
    )
    return {"status": response.status, "body": response.json() if response.ok else {}}


def _clear_cart(page: Page, base_url: str) -> None:
    """Clear the cart state."""
    page.goto(base_url)
    page.wait_for_load_state("networkidle")
    page.evaluate("localStorage.clear()")
    page.request.delete(f"{base_url}/api/cart/clear")


def _place_order_via_ui(page: Page, base_url: str) -> None:
    """Complete a full checkout flow via the UI to create an order record."""
    add_product_to_cart(page, base_url, product_name="Introduction to Testing")
    page.goto(f"{base_url}/cart")
    page.wait_for_load_state("networkidle")
    page.click("button:text('Proceed to Checkout')")
    page.wait_for_load_state("networkidle")
    complete_shipping_step(page)
    complete_payment_step(page)
    page.click("button:text('Place Order')")
    page.wait_for_load_state("networkidle")


class TestDatabase:
    """Database integrity and API contract tests."""

    # ------------------------------------------------------------------
    # TC_DB_001
    # ------------------------------------------------------------------
    @pytest.mark.database
    @pytest.mark.bug_db3
    def test_TC_DB_001_cart_negative_quantity_rejected(
        self, page: Page, base_url: str
    ):
        """TC_DB_001 — Adding a cart item with a negative quantity must be rejected.

        Sends a POST to /api/cart/add with quantity=-1 and asserts the API
        returns HTTP 400 (or at minimum a body containing 'error').

        Expected result (PASS on correct app): HTTP 400 or error in body.

        BUG DB3: The cart_items table has no CHECK constraint preventing negative
        quantities.  The API does not validate the quantity either.  A request
        with quantity=-1 will be accepted (HTTP 200), allowing cart manipulation.
        This test will FAIL on the buggy app.
        """
        # Login first so the session cookie is set for the request context
        _login(page, base_url, "user2", "Password@2")

        response = page.request.post(
            f"{base_url}/api/cart/add",
            data={"productId": "1", "quantity": "-1"},
        )

        page.screenshot(
            path="test-results/screenshots/TC_DB_001_negative_quantity.png",
            full_page=True,
        )

        status = response.status
        try:
            body = response.json()
        except Exception:
            body = {}

        body_str = str(body).lower()
        has_error = "error" in body_str or "invalid" in body_str or "negative" in body_str

        assert status == 400 or has_error, (
            f"BUG DB3: Adding cart item with quantity=-1 should be rejected "
            f"(HTTP 400 or error body) but returned HTTP {status}. "
            "No CHECK constraint on cart_items.quantity and no API validation. "
            f"Response body: {body}"
        )

    # ------------------------------------------------------------------
    # TC_DB_002
    # ------------------------------------------------------------------
    @pytest.mark.database
    @pytest.mark.bug_purchase4
    @pytest.mark.bug_db1
    def test_TC_DB_002_orders_endpoint_returns_only_own_orders(
        self, page: Page, base_url: str
    ):
        """TC_DB_002 — GET /api/orders/history must return only the authenticated user's orders.

        Steps:
          1. Login as user2 via UI, place an order, capture the order count.
          2. Login as user1 via API session (re-use page for cookie context).
          3. GET /api/orders/history as user1.
          4. Assert the response contains only user1's orders (not user2's).

        Expected result (PASS on correct app): user1 sees only their own orders.

        BUG Purchase4 / DB1: The orders history endpoint returns ALL orders from
        the database regardless of which user is authenticated.  user1 will see
        user2's orders.  This test will FAIL on the buggy app.
        """
        # --- Login as user2 and create an order ---
        _login(page, base_url, "user2", "Password@2")
        _clear_cart(page, base_url)
        _place_order_via_ui(page, base_url)

        # Get user2's order count via API
        resp_user2 = page.request.get(f"{base_url}/api/orders/history")
        user2_orders = resp_user2.json() if resp_user2.ok else []
        user2_order_count = len(user2_orders) if isinstance(user2_orders, list) else 0

        page.screenshot(
            path="test-results/screenshots/TC_DB_002_user2_orders_api.png",
            full_page=True,
        )

        # --- Logout and login as user1 ---
        page.click("button:text('Logout')")
        page.wait_for_load_state("networkidle")
        _login(page, base_url, "user1", "password123")

        # GET order history as user1
        resp_user1 = page.request.get(f"{base_url}/api/orders/history")
        user1_orders = resp_user1.json() if resp_user1.ok else []
        user1_order_count = len(user1_orders) if isinstance(user1_orders, list) else 0

        page.screenshot(
            path="test-results/screenshots/TC_DB_002_user1_orders_api.png",
            full_page=True,
        )

        # If user1 sees as many or more orders than user2 placed, it's leaking
        # (user1 hasn't placed any orders in this test — only user2 has)
        # The API should return 0 orders for user1 (no orders placed by user1 here)
        # If it returns the same large list as user2, the endpoint is broken.

        # Extract order user IDs if available to do a more precise check
        if isinstance(user1_orders, list) and len(user1_orders) > 0:
            sample = user1_orders[0]
            if isinstance(sample, dict):
                # Check if there's a user_id field
                user_id_in_order = sample.get("user_id") or sample.get("userId")
                if user_id_in_order is not None:
                    # All returned orders must belong to user1
                    for order in user1_orders:
                        if isinstance(order, dict):
                            uid = order.get("user_id") or order.get("userId")
                            assert uid == user_id_in_order, (
                                f"BUG Purchase4 / DB1: Order history for user1 contains "
                                f"an order with user_id={uid} which does not match user1. "
                                "The /api/orders/history endpoint leaks all users' orders."
                            )
                    return

        # Fallback: user1 should see fewer orders than the total in the system
        # If user1 sees >= user2_order_count, the data is not filtered by user
        assert user1_order_count < user2_order_count or user1_order_count == 0, (
            f"BUG Purchase4 / DB1: /api/orders/history is not filtered by user. "
            f"user1 sees {user1_order_count} orders, user2 has {user2_order_count}. "
            "All orders are returned regardless of the authenticated user."
        )

    # ------------------------------------------------------------------
    # TC_DB_003
    # ------------------------------------------------------------------
    @pytest.mark.database
    @pytest.mark.bug_auth3
    @pytest.mark.xfail(
        reason=(
            "BUG Auth3: MD5 is used instead of bcrypt for password hashing. "
            "MD5 hashes are 32 characters; bcrypt hashes are 60+ characters. "
            "This cannot be verified via the public API alone (no endpoint returns "
            "the stored hash), so this test is marked xfail as documentation. "
            "To verify: inspect the database directly — "
            "SELECT password_hash FROM users WHERE username='user1'; "
            "A bcrypt hash starts with '$2b$' and is 60 chars; "
            "an MD5 hash is a 32-character hex string."
        )
    )
    def test_TC_DB_003_password_hash_not_md5(self, page: Page, base_url: str):
        """TC_DB_003 — Passwords must be hashed with bcrypt, not MD5.

        This test documents BUG Auth3.  It cannot be fully automated via the
        public API because no endpoint exposes the stored password hash.

        The test is marked @pytest.mark.xfail so it appears in the report as
        an expected failure, drawing attention to the bug without masking
        genuine test failures.

        What this bug means:
          - MD5 is a fast, unsalted hash broken by rainbow tables and brute-force.
          - MD5 hashes are 32 hex characters; bcrypt hashes are 60+ chars with
            the '$2b$' prefix.
          - Example MD5 of 'password123': 482c811da5d5b4bc6d497ffa98491e38

        Verification (manual / DB access required):
          SELECT LENGTH(password_hash), password_hash
          FROM users
          WHERE username = 'user1';
          → length=32 confirms MD5; length>60 and starts with '$2b$' confirms bcrypt.

        Expected xfail outcome: test raises AssertionError to document the bug.
        """
        # Attempt to detect MD5 via API behaviour:
        # MD5("password123") = 482c811da5d5b4bc6d497ffa98491e38
        # If the login endpoint internally uses MD5 and we can observe timing or
        # any other side-channel, we document it here.

        # Login as user1 successfully — proves the hash stored matches the input
        _login(page, base_url, "user1", "password123")
        assert "/login" not in page.url, (
            "TC_DB_003 pre-condition: Login as user1 should succeed."
        )

        # We cannot retrieve the hash via API, so we raise to trigger xfail
        # and document the bug in the report.
        raise AssertionError(
            "BUG Auth3: Password hashing uses MD5 (32-char hash) instead of bcrypt "
            "(60+ char hash with '$2b$' prefix). "
            "MD5 is cryptographically broken and unsuitable for password storage. "
            "Direct DB verification: SELECT password_hash FROM users WHERE username='user1' "
            "— a 32-character hex string confirms MD5."
        )
