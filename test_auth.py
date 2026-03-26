"""
test_auth.py — Authentication test suite for the Webshop application.

Test class : TestAuthentication
Test cases : TC_AUTH_001 … TC_AUTH_009

Covers:
  - User registration (valid + invalid passwords)
  - Login (valid + invalid credentials)
  - Account lockout absence (BUG Auth5)
  - Weak password accepted for user1 (BUG Auth1)
  - Cart persistence after logout (BUG Cart5)

All tests use the Playwright sync API via pytest-playwright fixtures.
"""

import uuid

import pytest
from playwright.sync_api import Page, expect

from conftest import _login, add_product_to_cart


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _unique_user() -> dict:
    """Return a dict of unique registration data for each test run."""
    token = uuid.uuid4().hex[:8]
    return {
        "full_name": f"Test User {token}",
        "username": f"testuser_{token}",
        "email": f"testuser_{token}@example.com",
    }


def _register(page: Page, base_url: str, user: dict, password: str, confirm: str | None = None) -> None:
    """Fill and submit the registration form."""
    if confirm is None:
        confirm = password
    page.goto(f"{base_url}/register")
    page.wait_for_load_state("networkidle")
    page.fill("#full_name", user["full_name"])
    page.fill("#username", user["username"])
    page.fill("#email", user["email"])
    page.fill("#password", password)
    page.fill("#confirmPassword", confirm)
    page.click("button[type='submit']")
    page.wait_for_load_state("networkidle")


# ---------------------------------------------------------------------------
# Test class
# ---------------------------------------------------------------------------

class TestAuthentication:
    """End-to-end authentication tests for the webshop.

    Tests cover registration validation, login flows, lockout behaviour,
    password policy enforcement, and cart state across logout.
    """

    # ------------------------------------------------------------------
    # TC_AUTH_001
    # ------------------------------------------------------------------
    @pytest.mark.auth
    def test_TC_AUTH_001_valid_registration(self, page: Page, base_url: str):
        """TC_AUTH_001 — Valid registration with a strong password.

        Tests that a new user can register successfully using a password
        that meets all security requirements (uppercase, special char, ≥8 chars).

        Expected result (PASS): After form submission the application redirects
        to the home page ('/') and the session is established.
        """
        user = _unique_user()
        _register(page, base_url, user, "SecurePass@123")

        page.screenshot(
            path=f"test-results/screenshots/TC_AUTH_001_after_register.png",
            full_page=True,
        )

        assert "/" in page.url, (
            "TC_AUTH_001: Registration with valid data should redirect to '/'. "
            f"Current URL: {page.url}"
        )
        # Must NOT still be on /register
        assert "/register" not in page.url, (
            "TC_AUTH_001: Still on /register page after valid registration submission."
        )

    # ------------------------------------------------------------------
    # TC_AUTH_002
    # ------------------------------------------------------------------
    @pytest.mark.auth
    @pytest.mark.bug_auth2
    def test_TC_AUTH_002_password_too_short_rejected(self, page: Page, base_url: str):
        """TC_AUTH_002 — Registration with 7-character password should be rejected.

        A compliant password policy requires at least 8 characters.  The password
        "Ab1@xyz" is only 7 characters and must therefore be rejected.

        Expected result (PASS on buggy app = FAIL): The app should stay on /register
        or display a validation error.

        BUG Auth2: The application only checks length ≥ 6 characters, so "Ab1@xyz"
        (7 chars) is accepted and the user is redirected away — this test will FAIL
        on the buggy app, documenting BUG Auth2.
        """
        user = _unique_user()
        _register(page, base_url, user, "Ab1@xyz")  # 7 chars

        page.screenshot(
            path="test-results/screenshots/TC_AUTH_002_short_password.png",
            full_page=True,
        )

        on_register = "/register" in page.url
        error_visible = (
            page.locator(".error-text").is_visible()
            or page.locator(".alert-error").is_visible()
        )

        assert on_register or error_visible, (
            "BUG Auth2: Password 'Ab1@xyz' (7 chars) should be rejected "
            "(policy requires ≥8 chars) but was accepted. "
            f"URL after submission: {page.url}"
        )

    # ------------------------------------------------------------------
    # TC_AUTH_003
    # ------------------------------------------------------------------
    @pytest.mark.auth
    @pytest.mark.bug_auth2
    def test_TC_AUTH_003_password_no_uppercase_rejected(self, page: Page, base_url: str):
        """TC_AUTH_003 — Registration with all-lowercase password should be rejected.

        A compliant password policy requires at least one uppercase character.
        "nouppercase@123" has no uppercase letters and must be rejected.

        Expected result (PASS on buggy app = FAIL): Stay on /register or show error.

        BUG Auth2: Validation only checks length (≥6), not character class rules.
        This password will be accepted, and the test will FAIL.
        """
        user = _unique_user()
        _register(page, base_url, user, "nouppercase@123")

        page.screenshot(
            path="test-results/screenshots/TC_AUTH_003_no_uppercase.png",
            full_page=True,
        )

        on_register = "/register" in page.url
        error_visible = (
            page.locator(".error-text").is_visible()
            or page.locator(".alert-error").is_visible()
        )

        assert on_register or error_visible, (
            "BUG Auth2: Password 'nouppercase@123' (no uppercase) should be rejected "
            "by policy but was accepted. "
            f"URL after submission: {page.url}"
        )

    # ------------------------------------------------------------------
    # TC_AUTH_004
    # ------------------------------------------------------------------
    @pytest.mark.auth
    @pytest.mark.bug_auth2
    def test_TC_AUTH_004_password_no_special_char_rejected(self, page: Page, base_url: str):
        """TC_AUTH_004 — Registration with password lacking special character should be rejected.

        A compliant password policy requires at least one special character.
        "NoSpecialChar123" contains no special characters and must be rejected.

        Expected result (PASS on buggy app = FAIL): Stay on /register or show error.

        BUG Auth2: Only length is validated; character class rules are absent.
        This password will be accepted, causing the test to FAIL.
        """
        user = _unique_user()
        _register(page, base_url, user, "NoSpecialChar123")

        page.screenshot(
            path="test-results/screenshots/TC_AUTH_004_no_special_char.png",
            full_page=True,
        )

        on_register = "/register" in page.url
        error_visible = (
            page.locator(".error-text").is_visible()
            or page.locator(".alert-error").is_visible()
        )

        assert on_register or error_visible, (
            "BUG Auth2: Password 'NoSpecialChar123' (no special char) should be "
            "rejected by policy but was accepted. "
            f"URL after submission: {page.url}"
        )

    # ------------------------------------------------------------------
    # TC_AUTH_005
    # ------------------------------------------------------------------
    @pytest.mark.auth
    @pytest.mark.smoke
    def test_TC_AUTH_005_valid_login(self, page: Page, base_url: str):
        """TC_AUTH_005 — Login with valid credentials (user2 / Password@2).

        Verifies that a registered user can log in successfully and is
        redirected to the home page.

        Expected result (PASS): After login, URL is '/' (home page) and
        username is displayed in the header.
        """
        _login(page, base_url, "user2", "Password@2")

        page.screenshot(
            path="test-results/screenshots/TC_AUTH_005_valid_login.png",
            full_page=True,
        )

        assert "/login" not in page.url, (
            f"TC_AUTH_005: Login as user2 should succeed and redirect away from /login. "
            f"Current URL: {page.url}"
        )

    # ------------------------------------------------------------------
    # TC_AUTH_006
    # ------------------------------------------------------------------
    @pytest.mark.auth
    def test_TC_AUTH_006_invalid_login_shows_error(self, page: Page, base_url: str):
        """TC_AUTH_006 — Login with wrong password should show an error message.

        Verifies that invalid credentials do not authenticate the user and
        that a clear error message is displayed.

        Expected result (PASS): Error message visible on login page, URL
        remains /login.
        """
        _login(page, base_url, "user2", "WrongPassword999!")

        page.screenshot(
            path="test-results/screenshots/TC_AUTH_006_invalid_login.png",
            full_page=True,
        )

        error = page.locator(".alert-error")
        assert error.is_visible(), (
            "TC_AUTH_006: An error message should appear after login with wrong password."
        )
        assert "/login" in page.url, (
            f"TC_AUTH_006: User must stay on /login after failed login. URL: {page.url}"
        )

    # ------------------------------------------------------------------
    # TC_AUTH_007
    # ------------------------------------------------------------------
    @pytest.mark.auth
    @pytest.mark.bug_auth5
    def test_TC_AUTH_007_no_account_lockout(self, page: Page, base_url: str):
        """TC_AUTH_007 — No account lockout after 5 consecutive failed login attempts.

        A secure application locks an account (or imposes a delay / CAPTCHA)
        after a number of consecutive failed authentication attempts.
        This test verifies the ABSENCE of lockout — the fifth attempt must
        still return a generic "invalid credentials" error, NOT a lockout message.

        Expected result (PASS of this test documents the bug): The fifth attempt
        still shows a generic authentication error instead of "account locked" /
        "too many attempts" message.

        BUG Auth5: No lockout mechanism is implemented.  An attacker can perform
        unlimited brute-force attempts.  This test will PASS (documenting the bug
        exists) rather than FAIL, because we are asserting the *absence* of
        a lockout message which confirms the bug.
        """
        for attempt in range(5):
            page.goto(f"{base_url}/login")
            page.wait_for_load_state("networkidle")
            page.fill("#username", "user1")
            page.fill("#password", f"WrongPass{attempt}!")
            page.click("button[type='submit']")
            page.wait_for_load_state("networkidle")

        page.screenshot(
            path="test-results/screenshots/TC_AUTH_007_no_lockout_5th_attempt.png",
            full_page=True,
        )

        error_text = page.locator(".alert-error").text_content() or ""
        lower = error_text.lower()

        # The app should NOT have locked the account
        lockout_keywords = ["locked", "too many", "blocked", "suspended", "attempts exceeded"]
        is_lockout = any(kw in lower for kw in lockout_keywords)

        assert not is_lockout, (
            "TC_AUTH_007: Unexpectedly, the account appears to be locked after 5 "
            f"failed attempts. Error text: '{error_text}'. "
            "If lockout IS implemented, BUG Auth5 is fixed."
        )

        # Also confirm we are still on the login page (not somehow let in)
        assert "/login" in page.url, (
            f"TC_AUTH_007: After 5 bad attempts, user should still be on /login. URL: {page.url}"
        )

        # Document the bug clearly
        assert True, (
            "BUG Auth5: No account lockout after 5 failed attempts — "
            "brute-force is possible without restriction."
        )

    # ------------------------------------------------------------------
    # TC_AUTH_008
    # ------------------------------------------------------------------
    @pytest.mark.auth
    @pytest.mark.bug_auth1
    def test_TC_AUTH_008_user1_password_violates_policy(self, page: Page, base_url: str):
        """TC_AUTH_008 — user1's password 'password123' violates the password policy.

        This test documents BUG Auth1: the seed data creates user1 with a password
        that does not meet the stated complexity requirements (no uppercase letter,
        no special character).

        The test:
          1. Logs in as user1 to confirm the account exists and the password works.
          2. Programmatically verifies the password string fails the policy.
          3. Asserts this constitutes a policy violation (the test fails to draw
             attention to the bug in CI results).

        BUG Auth1: The seeded password 'password123' has no uppercase letter and
        no special character — both required by the stated policy.
        """
        _login(page, base_url, "user1", "password123")

        page.screenshot(
            path="test-results/screenshots/TC_AUTH_008_user1_login.png",
            full_page=True,
        )

        # Confirm login succeeded
        assert "/login" not in page.url, (
            "TC_AUTH_008 pre-condition: Login as user1 should succeed. "
            f"URL: {page.url}"
        )

        # Now validate the password against policy rules
        password = "password123"
        has_uppercase = any(c.isupper() for c in password)
        has_special = any(c in "!@#$%^&*()_+-=[]{}|;':\",./<>?" for c in password)
        has_min_length = len(password) >= 8

        # The test ASSERTS the policy IS violated — this documents the bug
        assert not has_uppercase, (
            f"TC_AUTH_008: 'password123' unexpectedly has an uppercase character."
        )
        assert not has_special, (
            f"TC_AUTH_008: 'password123' unexpectedly has a special character."
        )

        # This assertion will ALWAYS FAIL to flag the bug in the CI report
        assert has_uppercase and has_special, (
            "BUG Auth1: user1's seeded password 'password123' violates the password "
            "policy — it has no uppercase letter and no special character. "
            "The user account should not exist with this password in a secure system."
        )

    # ------------------------------------------------------------------
    # TC_AUTH_009
    # ------------------------------------------------------------------
    @pytest.mark.auth
    @pytest.mark.bug_cart5
    def test_TC_AUTH_009_cart_cleared_after_logout(self, page: Page, base_url: str):
        """TC_AUTH_009 — Cart should be cleared/empty after the user logs out.

        A secure application must clear client-side cart state on logout so
        that a subsequent anonymous visitor (or different user on the same
        browser) does not see the previous user's cart contents.

        Expected result (PASS on correct app): After logout the cart badge
        shows 0 or is absent.

        BUG Cart5: The cart is stored in localStorage and is NOT cleared on
        logout.  This test will FAIL because the cart badge still shows items
        after logout, documenting the bug.
        """
        # Step 1: Login as user2
        _login(page, base_url, "user2", "Password@2")

        # Step 2: Clear any previous cart state via API
        page.request.delete(f"{base_url}/api/cart/clear")

        # Step 3: Add a product to cart
        add_product_to_cart(page, base_url, product_name="Introduction to Testing")

        # Step 4: Confirm cart badge shows > 0
        page.goto(f"{base_url}/products")
        page.wait_for_load_state("networkidle")

        badge = page.locator(".cart-badge")
        badge_visible = badge.is_visible()
        badge_count = int(badge.text_content().strip()) if badge_visible and badge.text_content() else 0

        page.screenshot(
            path="test-results/screenshots/TC_AUTH_009_cart_before_logout.png",
            full_page=True,
        )

        assert badge_visible and badge_count > 0, (
            "TC_AUTH_009 pre-condition: Cart badge should show > 0 after adding a product. "
            f"Badge visible: {badge_visible}, count: {badge_count}"
        )

        # Step 5: Logout
        page.click("button:text('Logout')")
        page.wait_for_load_state("networkidle")

        page.screenshot(
            path="test-results/screenshots/TC_AUTH_009_cart_after_logout.png",
            full_page=True,
        )

        # Step 6: Verify cart is empty / badge gone
        badge_after = page.locator(".cart-badge")
        badge_after_visible = badge_after.is_visible()
        badge_after_count = 0
        if badge_after_visible:
            text = badge_after.text_content() or "0"
            badge_after_count = int(text.strip()) if text.strip().isdigit() else 0

        assert not badge_after_visible or badge_after_count == 0, (
            "BUG Cart5: Cart badge is still visible/non-zero after logout. "
            "The cart stored in localStorage is not cleared on logout. "
            f"Badge visible: {badge_after_visible}, count: {badge_after_count}"
        )
