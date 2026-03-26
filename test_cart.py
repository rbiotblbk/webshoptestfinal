"""
test_cart.py — Shopping cart tests for the Webshop application.

Test class : TestCart
Test cases : TC_CART_001 … TC_CART_007

Covers:
  - Adding products to cart (smoke)
  - 10-item quantity limit per product (BUG Cart1)
  - VAT / tax rate correctness — expected 10% (BUG Cart2)
  - TEST10 discount code applies 10% (BUG Cart3)
  - STUDENT20 discount code applies 20% (expected to PASS)
  - Cart total updates after item removal (BUG Cart4)
  - Cart cleared after logout (BUG Cart5)
"""

import pytest
from playwright.sync_api import Page

from conftest import _login, add_product_to_cart


def _parse_price(price_text: str) -> float:
    """Convert '$29.99' → 29.99."""
    return float(price_text.replace("$", "").replace(",", "").strip())


def _get_summary_value(page: Page, label_text: str) -> float:
    """Return the float value from a .summary-row that contains label_text."""
    row = page.locator(f".summary-row:has-text('{label_text}')")
    spans = row.locator("span")
    # The value is in the second span
    raw = spans.nth(1).text_content() or "0"
    # Strip non-numeric except dot and minus
    clean = raw.replace("$", "").replace(",", "").replace("-", "").strip()
    return float(clean)


def _get_total(page: Page) -> float:
    """Return the float value from the .total-row."""
    row = page.locator(".total-row")
    spans = row.locator("span")
    raw = spans.nth(1).text_content() or "0"
    return _parse_price(raw)


def _clear_cart(page: Page, base_url: str) -> None:
    """Clear the cart via API and localStorage."""
    page.goto(base_url)
    page.wait_for_load_state("networkidle")
    page.evaluate("localStorage.clear()")
    page.request.delete(f"{base_url}/api/cart/clear")


class TestCart:
    """Shopping cart behaviour tests."""

    # ------------------------------------------------------------------
    # TC_CART_001
    # ------------------------------------------------------------------
    @pytest.mark.cart
    @pytest.mark.smoke
    def test_TC_CART_001_add_product_to_cart(
        self, authenticated_page: Page, base_url: str
    ):
        """TC_CART_001 — A product can be added to the cart and appears on /cart.

        Adds 'Introduction to Testing' to the cart, navigates to /cart, and
        asserts that at least one cart item is present and the product name
        is visible in the cart.

        Expected result (PASS): Cart contains at least 1 item; product name found.
        """
        page = authenticated_page
        _clear_cart(page, base_url)

        add_product_to_cart(page, base_url, product_name="Introduction to Testing")

        page.goto(f"{base_url}/cart")
        page.wait_for_load_state("networkidle")

        page.screenshot(
            path="test-results/screenshots/TC_CART_001_cart_with_item.png",
            full_page=True,
        )

        cart_items = page.locator(".cart-item")
        assert cart_items.count() > 0, (
            "TC_CART_001: Cart should contain at least one item after adding a product."
        )

        cart_text = page.locator(".cart-item").all_text_contents()
        found = any("Introduction to Testing" in t for t in cart_text)
        assert found, (
            f"TC_CART_001: 'Introduction to Testing' not found in cart items. "
            f"Cart contents: {cart_text}"
        )

    # ------------------------------------------------------------------
    # TC_CART_002
    # ------------------------------------------------------------------
    @pytest.mark.cart
    @pytest.mark.bug_cart1
    def test_TC_CART_002_max_10_items_limit(
        self, authenticated_page: Page, base_url: str
    ):
        """TC_CART_002 — Adding the same product more than 10 times should cap at qty=10.

        Clicks 'Add to Cart' for 'Introduction to Testing' 11 times, then checks
        the quantity shown in the cart is ≤ 10.

        Expected result (PASS on correct app): qty shown is 10.

        BUG Cart1: No maximum quantity limit is enforced.  After 11 clicks the
        cart will show qty=11, causing this test to FAIL.
        """
        page = authenticated_page
        _clear_cart(page, base_url)

        # Add the same product 11 times
        for _ in range(11):
            add_product_to_cart(page, base_url, product_name="Introduction to Testing")

        page.goto(f"{base_url}/cart")
        page.wait_for_load_state("networkidle")

        page.screenshot(
            path="test-results/screenshots/TC_CART_002_max_items.png",
            full_page=True,
        )

        # Find the quantity displayed for the cart item
        # Typical quantity selectors: input[type="number"], .quantity, .cart-item-qty
        qty_locators = [
            page.locator(".cart-item input[type='number']").first,
            page.locator(".cart-item .quantity").first,
            page.locator(".cart-item-qty").first,
            page.locator(".cart-item").first.locator("input").first,
        ]

        qty = None
        for loc in qty_locators:
            try:
                if loc.is_visible():
                    val = loc.get_attribute("value") or loc.text_content() or ""
                    if val.strip().isdigit():
                        qty = int(val.strip())
                        break
            except Exception:
                continue

        assert qty is not None, (
            "TC_CART_002: Could not find a quantity display element in the cart."
        )
        assert qty <= 10, (
            f"BUG Cart1: No maximum quantity limit enforced. After adding 11 times, "
            f"cart shows qty={qty}. Expected ≤ 10."
        )

    # ------------------------------------------------------------------
    # TC_CART_003
    # ------------------------------------------------------------------
    @pytest.mark.cart
    @pytest.mark.bug_cart2
    def test_TC_CART_003_tax_is_10_percent(
        self, authenticated_page: Page, base_url: str
    ):
        """TC_CART_003 — VAT / tax should be calculated at 10% of the subtotal.

        Adds one 'Introduction to Testing' ($29.99) to the cart, reads the VAT
        row, and asserts VAT ≈ subtotal × 0.10.

        Expected result (PASS on correct app): VAT ≈ $3.00 (10% of $29.99).

        BUG Cart2: TAX_RATE is set to 0.05 (5%) instead of 0.10.  Actual VAT
        will be ~$1.50, causing this test to FAIL.
        """
        page = authenticated_page
        _clear_cart(page, base_url)

        add_product_to_cart(page, base_url, product_name="Introduction to Testing")

        page.goto(f"{base_url}/cart")
        page.wait_for_load_state("networkidle")

        page.screenshot(
            path="test-results/screenshots/TC_CART_003_tax_rate.png",
            full_page=True,
        )

        # Get subtotal
        subtotal = _get_summary_value(page, "Subtotal")
        # Get VAT amount
        actual_vat = _get_summary_value(page, "VAT")
        expected_vat = round(subtotal * 0.10, 2)

        assert abs(actual_vat - expected_vat) <= 0.01, (
            f"BUG Cart2: VAT should be 10% of subtotal. "
            f"Subtotal=${subtotal:.2f}, expected VAT=${expected_vat:.2f}, "
            f"actual VAT=${actual_vat:.2f}. "
            "TAX_RATE=0.05 (5%) is used instead of 0.10 (10%)."
        )

    # ------------------------------------------------------------------
    # TC_CART_004
    # ------------------------------------------------------------------
    @pytest.mark.cart
    @pytest.mark.bug_cart3
    def test_TC_CART_004_TEST10_discount_is_10_percent(
        self, authenticated_page: Page, base_url: str
    ):
        """TC_CART_004 — Discount code TEST10 should apply exactly 10% off the subtotal.

        Adds a product to the cart, applies discount code 'TEST10', reads the
        discount amount from the summary row, and asserts discount ≈ subtotal × 0.10.

        Expected result (PASS on correct app): discount = 10% of subtotal.

        BUG Cart3: The TEST10 code applies a 20% discount instead of 10%.
        This test will FAIL on the buggy app.
        """
        page = authenticated_page
        _clear_cart(page, base_url)

        add_product_to_cart(page, base_url, product_name="Introduction to Testing")

        page.goto(f"{base_url}/cart")
        page.wait_for_load_state("networkidle")

        # Apply discount code
        page.fill("input[placeholder='Discount code']", "TEST10")
        page.click("button:text('Apply')")
        page.wait_for_load_state("networkidle")

        page.screenshot(
            path="test-results/screenshots/TC_CART_004_TEST10_discount.png",
            full_page=True,
        )

        subtotal = _get_summary_value(page, "Subtotal")
        actual_discount = _get_summary_value(page, "Discount")
        expected_discount = round(subtotal * 0.10, 2)

        assert abs(actual_discount - expected_discount) <= 0.01, (
            f"BUG Cart3: Discount code TEST10 should apply 10% off subtotal. "
            f"Subtotal=${subtotal:.2f}, expected discount=${expected_discount:.2f}, "
            f"actual discount=${actual_discount:.2f}. "
            "The code applies 20% instead of 10%."
        )

    # ------------------------------------------------------------------
    # TC_CART_005
    # ------------------------------------------------------------------
    @pytest.mark.cart
    def test_TC_CART_005_STUDENT20_discount_is_20_percent(
        self, authenticated_page: Page, base_url: str
    ):
        """TC_CART_005 — Discount code STUDENT20 should apply exactly 20% off the subtotal.

        Expected result (PASS): discount = 20% of subtotal.
        """
        page = authenticated_page
        _clear_cart(page, base_url)

        add_product_to_cart(page, base_url, product_name="Clean Code")

        page.goto(f"{base_url}/cart")
        page.wait_for_load_state("networkidle")

        page.fill("input[placeholder='Discount code']", "STUDENT20")
        page.click("button:text('Apply')")
        page.wait_for_load_state("networkidle")

        page.screenshot(
            path="test-results/screenshots/TC_CART_005_STUDENT20_discount.png",
            full_page=True,
        )

        subtotal = _get_summary_value(page, "Subtotal")
        actual_discount = _get_summary_value(page, "Discount")
        expected_discount = round(subtotal * 0.20, 2)

        assert abs(actual_discount - expected_discount) <= 0.01, (
            f"TC_CART_005: STUDENT20 discount should be 20% of subtotal. "
            f"Subtotal=${subtotal:.2f}, expected=${expected_discount:.2f}, "
            f"actual=${actual_discount:.2f}."
        )

    # ------------------------------------------------------------------
    # TC_CART_006
    # ------------------------------------------------------------------
    @pytest.mark.cart
    @pytest.mark.bug_cart4
    def test_TC_CART_006_total_updates_after_item_removal(
        self, authenticated_page: Page, base_url: str
    ):
        """TC_CART_006 — Cart total must decrease after removing an item.

        Adds two different products to the cart, records the initial total,
        removes one item, then asserts the new total is lower.

        Expected result (PASS on correct app): new_total < initial_total.

        BUG Cart4: The cart total (displayed in the summary) is not recalculated
        after item removal.  The stale total persists, causing this test to FAIL.
        """
        page = authenticated_page
        _clear_cart(page, base_url)

        # Add two different products
        add_product_to_cart(page, base_url, product_name="Introduction to Testing")
        add_product_to_cart(page, base_url, product_name="Clean Code")

        page.goto(f"{base_url}/cart")
        page.wait_for_load_state("networkidle")

        page.screenshot(
            path="test-results/screenshots/TC_CART_006_before_removal.png",
            full_page=True,
        )

        initial_total = _get_total(page)

        # Remove the first item
        remove_btn = page.locator("button.btn-danger:text('Remove')").first
        remove_btn.click()
        page.wait_for_load_state("networkidle")

        page.screenshot(
            path="test-results/screenshots/TC_CART_006_after_removal.png",
            full_page=True,
        )

        new_total = _get_total(page)

        assert new_total < initial_total, (
            f"BUG Cart4: Cart total was not updated after removing an item. "
            f"Initial total=${initial_total:.2f}, new total=${new_total:.2f}. "
            "The displayed total stays stale after removal."
        )

    # ------------------------------------------------------------------
    # TC_CART_007
    # ------------------------------------------------------------------
    @pytest.mark.cart
    @pytest.mark.bug_cart5
    def test_TC_CART_007_cart_cleared_after_logout(
        self, page: Page, base_url: str
    ):
        """TC_CART_007 — Cart must be empty after the user logs out.

        Logs in as user2, adds a product, verifies the cart has items, then
        logs out and navigates to /cart.  Asserts the cart is empty.

        Expected result (PASS on correct app): cart-empty message visible or
        no .cart-item elements present.

        BUG Cart5: Cart data is stored in localStorage and not cleared on logout.
        After logout, navigating to /cart shows the previous cart contents.
        This test will FAIL on the buggy app.
        """
        _login(page, base_url, "user2", "Password@2")
        _clear_cart(page, base_url)

        add_product_to_cart(page, base_url, product_name="Introduction to Testing")

        # Verify cart has items
        page.goto(f"{base_url}/cart")
        page.wait_for_load_state("networkidle")

        assert page.locator(".cart-item").count() > 0, (
            "TC_CART_007 pre-condition: Cart should have items before logout."
        )

        page.screenshot(
            path="test-results/screenshots/TC_CART_007_cart_before_logout.png",
            full_page=True,
        )

        # Logout
        page.click("button:text('Logout')")
        page.wait_for_load_state("networkidle")

        # Navigate to cart as anonymous user
        page.goto(f"{base_url}/cart")
        page.wait_for_load_state("networkidle")

        page.screenshot(
            path="test-results/screenshots/TC_CART_007_cart_after_logout.png",
            full_page=True,
        )

        empty_msg = page.locator(".cart-empty")
        items = page.locator(".cart-item")

        is_empty = empty_msg.is_visible() or items.count() == 0

        assert is_empty, (
            "BUG Cart5: Cart is NOT empty after logout. "
            f"Found {items.count()} cart item(s). "
            "localStorage is not cleared on logout, so cart data persists."
        )
