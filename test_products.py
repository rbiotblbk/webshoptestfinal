"""
test_products.py — Product display, filtering, sorting and availability tests.

Test class : TestProductDisplay
Test cases : TC_PROD_001 … TC_PROD_009

Covers:
  - Electronics image path (BUG PD1)
  - Price filter inclusivity — min (PASS) and max (BUG PD2)
  - Alphabetical sorting (name_asc / name_desc) — expected to PASS
  - Numeric price sorting (BUG PD5 — string sort used)
  - Out-of-stock badge display (BUG PD4)
  - "Add to Cart" button visibility on mobile for Books (BUG PD3)
"""

import pytest
from playwright.sync_api import Page, expect


def _parse_price(price_text: str) -> float:
    """Convert a price string like '$29.99' to a float 29.99."""
    return float(price_text.replace("$", "").replace(",", "").strip())


def _go_to_products(page: Page, base_url: str) -> None:
    """Navigate to the products page and wait for it to be ready."""
    page.goto(f"{base_url}/products")
    page.wait_for_load_state("networkidle")
    # Ensure at least one product card is rendered
    page.wait_for_selector(".product-card")


def _click_category(page: Page, category_label: str) -> None:
    """Click a category filter button and wait for the list to update."""
    page.click(f"button.category-btn:text('{category_label}')")
    page.wait_for_load_state("networkidle")


class TestProductDisplay:
    """Product listing, filtering, sorting and display tests."""

    # ------------------------------------------------------------------
    # TC_PROD_001
    # ------------------------------------------------------------------
    @pytest.mark.products
    @pytest.mark.bug_pd1
    def test_TC_PROD_001_electronics_images_broken(self, page: Page, base_url: str):
        """TC_PROD_001 — Electronics product images should use the correct path /images/.

        Navigates to the Electronics category and inspects the src attribute of
        the first product image.  A correct path starts with '/images/electronics/'
        (the public assets folder).

        Expected result (PASS on correct app): image src starts with '/images/'.

        BUG PD1: Electronics images are served from '/img/electronics/' which does
        not exist, resulting in broken images.  This test will FAIL on the buggy app.
        """
        _go_to_products(page, base_url)
        _click_category(page, "Electronics")

        # Get the first product card image
        first_img = page.locator(".product-card img").first
        page.wait_for_selector(".product-card img")

        img_src = first_img.get_attribute("src") or ""

        page.screenshot(
            path="test-results/screenshots/TC_PROD_001_electronics_images.png",
            full_page=True,
        )

        assert img_src.startswith("/images/"), (
            f"BUG PD1: Electronics product image src should start with '/images/' "
            f"but was '{img_src}'. The wrong path '/img/electronics/' is used, "
            "resulting in 404 broken images."
        )

    # ------------------------------------------------------------------
    # TC_PROD_002
    # ------------------------------------------------------------------
    @pytest.mark.products
    def test_TC_PROD_002_price_filter_min_inclusive(self, page: Page, base_url: str):
        """TC_PROD_002 — Min price filter should include products at exactly the min price.

        Sets min price to $89.99 and expects 'Wireless Headphones Pro' ($89.99)
        to appear in results.  The minimum filter is implemented correctly (>=)
        so this test should PASS.

        Expected result (PASS): 'Wireless Headphones Pro' is visible.
        """
        _go_to_products(page, base_url)

        page.fill("input[placeholder='Min $']", "89.99")
        page.click("button:text('Apply')")
        page.wait_for_load_state("networkidle")

        page.screenshot(
            path="test-results/screenshots/TC_PROD_002_min_price_filter.png",
            full_page=True,
        )

        product_names = page.locator(".product-card-name").all_text_contents()
        assert "Wireless Headphones Pro" in product_names, (
            "TC_PROD_002: 'Wireless Headphones Pro' ($89.99) should appear when "
            f"min filter is $89.99. Visible products: {product_names}"
        )

    # ------------------------------------------------------------------
    # TC_PROD_003
    # ------------------------------------------------------------------
    @pytest.mark.products
    @pytest.mark.bug_pd2
    def test_TC_PROD_003_price_filter_max_inclusive(self, page: Page, base_url: str):
        """TC_PROD_003 — Max price filter should include products at exactly the max price.

        Sets max price to $29.99 and expects 'Introduction to Testing' ($29.99)
        to appear in results (price == max, should be included with <=).

        Expected result (PASS on correct app): 'Introduction to Testing' is visible.

        BUG PD2: The price filter max comparison uses strict less-than (<) instead
        of less-than-or-equal (<=).  Products priced exactly at the max value are
        excluded.  This test will FAIL on the buggy app.
        """
        _go_to_products(page, base_url)

        page.fill("input[placeholder='Max $']", "29.99")
        page.click("button:text('Apply')")
        page.wait_for_load_state("networkidle")

        page.screenshot(
            path="test-results/screenshots/TC_PROD_003_max_price_filter.png",
            full_page=True,
        )

        product_names = page.locator(".product-card-name").all_text_contents()
        assert "Introduction to Testing" in product_names, (
            "BUG PD2: 'Introduction to Testing' ($29.99) should appear when max "
            "filter is $29.99 (inclusive <=) but was excluded. "
            f"Visible products: {product_names}"
        )

    # ------------------------------------------------------------------
    # TC_PROD_004
    # ------------------------------------------------------------------
    @pytest.mark.products
    def test_TC_PROD_004_sort_name_asc(self, page: Page, base_url: str):
        """TC_PROD_004 — Sort by name ascending (A-Z) should produce alphabetical order.

        Retrieves all product names after selecting name_asc sort and verifies
        the list is in non-decreasing alphabetical order.

        Expected result (PASS): Names are in A-Z order.
        """
        _go_to_products(page, base_url)

        page.select_option("select.sort-select", "name_asc")
        page.wait_for_load_state("networkidle")

        page.screenshot(
            path="test-results/screenshots/TC_PROD_004_sort_name_asc.png",
            full_page=True,
        )

        names = page.locator(".product-card-name").all_text_contents()
        assert len(names) > 0, "TC_PROD_004: No product cards found."

        sorted_names = sorted(names, key=str.lower)
        assert names == sorted_names or [n.lower() for n in names] == [n.lower() for n in sorted_names], (
            f"TC_PROD_004: Products are not sorted A-Z by name. "
            f"Got: {names}, expected: {sorted_names}"
        )

    # ------------------------------------------------------------------
    # TC_PROD_005
    # ------------------------------------------------------------------
    @pytest.mark.products
    def test_TC_PROD_005_sort_name_desc(self, page: Page, base_url: str):
        """TC_PROD_005 — Sort by name descending (Z-A) should produce reverse alphabetical order.

        Expected result (PASS): Names are in Z-A order.
        """
        _go_to_products(page, base_url)

        page.select_option("select.sort-select", "name_desc")
        page.wait_for_load_state("networkidle")

        page.screenshot(
            path="test-results/screenshots/TC_PROD_005_sort_name_desc.png",
            full_page=True,
        )

        names = page.locator(".product-card-name").all_text_contents()
        assert len(names) > 0, "TC_PROD_005: No product cards found."

        sorted_desc = sorted(names, key=str.lower, reverse=True)
        assert [n.lower() for n in names] == [n.lower() for n in sorted_desc], (
            f"TC_PROD_005: Products are not sorted Z-A by name. "
            f"Got: {names}, expected: {sorted_desc}"
        )

    # ------------------------------------------------------------------
    # TC_PROD_006
    # ------------------------------------------------------------------
    @pytest.mark.products
    @pytest.mark.bug_pd5
    def test_TC_PROD_006_sort_price_asc_numeric(self, page: Page, base_url: str):
        """TC_PROD_006 — Sort by price ascending should use numeric (not string) ordering.

        Retrieves all product prices, converts them to floats, and verifies
        they are in non-decreasing numeric order.  Also asserts that the first
        product is 'Programmer Socks' ($9.99), the cheapest item.

        Expected result (PASS on correct app): prices are numerically sorted;
        first price is $9.99.

        BUG PD5: The backend sorts using string comparison.  Under string sort
        "$9.99" > "$89.99" (because "9" > "8"), so $9.99 appears last instead
        of first.  This test will FAIL on the buggy app.
        """
        _go_to_products(page, base_url)

        page.select_option("select.sort-select", "price_asc")
        page.wait_for_load_state("networkidle")

        page.screenshot(
            path="test-results/screenshots/TC_PROD_006_sort_price_asc.png",
            full_page=True,
        )

        price_texts = page.locator(".product-card-price").all_text_contents()
        assert len(price_texts) > 0, "TC_PROD_006: No price elements found."

        prices = [_parse_price(p) for p in price_texts]

        # Assert numerically non-decreasing
        for i in range(len(prices) - 1):
            assert prices[i] <= prices[i + 1], (
                f"BUG PD5: Price sort (ascending) is not numeric. "
                f"Position {i} = ${prices[i]:.2f} is greater than "
                f"position {i+1} = ${prices[i+1]:.2f}. "
                f"String comparison is used instead of numeric sort."
            )

        # The cheapest product overall is Programmer Socks at $9.99
        assert prices[0] == pytest.approx(9.99, abs=0.01), (
            f"BUG PD5: First product in price_asc order should be $9.99 "
            f"(Programmer Socks) but was ${prices[0]:.2f}. "
            "String sort puts '$9.99' after '$89.99'."
        )

    # ------------------------------------------------------------------
    # TC_PROD_007
    # ------------------------------------------------------------------
    @pytest.mark.products
    @pytest.mark.bug_pd5
    def test_TC_PROD_007_sort_price_desc_numeric(self, page: Page, base_url: str):
        """TC_PROD_007 — Sort by price descending should use numeric (not string) ordering.

        Verifies prices are in non-increasing numeric order and that the first
        product is the most expensive ($249.99 — Smart Watch Series X).

        Expected result (PASS on correct app): prices are numerically sorted
        descending; first price is $249.99.

        BUG PD5: Same string-comparison issue as TC_PROD_006.
        """
        _go_to_products(page, base_url)

        page.select_option("select.sort-select", "price_desc")
        page.wait_for_load_state("networkidle")

        page.screenshot(
            path="test-results/screenshots/TC_PROD_007_sort_price_desc.png",
            full_page=True,
        )

        price_texts = page.locator(".product-card-price").all_text_contents()
        assert len(price_texts) > 0, "TC_PROD_007: No price elements found."

        prices = [_parse_price(p) for p in price_texts]

        for i in range(len(prices) - 1):
            assert prices[i] >= prices[i + 1], (
                f"BUG PD5: Price sort (descending) is not numeric. "
                f"Position {i} = ${prices[i]:.2f} is less than "
                f"position {i+1} = ${prices[i+1]:.2f}."
            )

        assert prices[0] == pytest.approx(249.99, abs=0.01), (
            f"BUG PD5: First product in price_desc order should be $249.99 "
            f"(Smart Watch Series X) but was ${prices[0]:.2f}."
        )

    # ------------------------------------------------------------------
    # TC_PROD_008
    # ------------------------------------------------------------------
    @pytest.mark.products
    @pytest.mark.bug_pd4
    def test_TC_PROD_008_out_of_stock_shows_badge(self, page: Page, base_url: str):
        """TC_PROD_008 — Products with quantity=0 must display 'Out of Stock' badge.

        'Portable Bluetooth Speaker' has qty=0 in the database.  Its badge
        should show "Out of Stock" rather than "In Stock".

        Expected result (PASS on correct app): badge text is 'Out of Stock'.

        BUG PD4: The application always returns 'In Stock' regardless of
        the quantity field.  This test will FAIL on the buggy app.
        """
        _go_to_products(page, base_url)
        _click_category(page, "Electronics")

        # Find the specific out-of-stock product card
        oos_card = page.locator(".product-card").filter(has_text="Portable Bluetooth Speaker")
        page.wait_for_selector(".product-card")

        page.screenshot(
            path="test-results/screenshots/TC_PROD_008_out_of_stock_badge.png",
            full_page=True,
        )

        badge = oos_card.locator(".badge")
        badge_text = badge.text_content().strip() if badge.is_visible() else ""

        assert badge_text == "Out of Stock", (
            f"BUG PD4: 'Portable Bluetooth Speaker' has qty=0 and should show "
            f"'Out of Stock' badge but shows '{badge_text}'. "
            "The availability field always reports 'In Stock'."
        )

    # ------------------------------------------------------------------
    # TC_PROD_009
    # ------------------------------------------------------------------
    @pytest.mark.products
    @pytest.mark.bug_pd3
    def test_TC_PROD_009_add_to_cart_button_visible_mobile_books(
        self, page: Page, base_url: str
    ):
        """TC_PROD_009 — 'Add to Cart' button must be visible on mobile for Books products.

        Sets the viewport to 375×667 (typical mobile) then navigates to the Books
        category.  The 'Add to Cart' button on any product card must be visible.

        Expected result (PASS on correct app): button is_visible() returns True.

        BUG PD3: A CSS rule `display: none` hides the 'Add to Cart' button for
        Books category on mobile (viewport ≤767px).  This test will FAIL on the
        buggy app.
        """
        # Set mobile viewport
        page.set_viewport_size({"width": 375, "height": 667})

        _go_to_products(page, base_url)
        _click_category(page, "Books")

        # Find the first product card
        first_card = page.locator(".product-card").first
        page.wait_for_selector(".product-card")

        add_btn = first_card.locator("button:text('Add to Cart')")

        page.screenshot(
            path="test-results/screenshots/TC_PROD_009_mobile_books_add_to_cart.png",
            full_page=True,
        )

        assert add_btn.is_visible(), (
            "BUG PD3: 'Add to Cart' button is not visible on mobile (375px wide) "
            "for Books category products. "
            "CSS rule 'display: none' hides it for viewport ≤767px."
        )

        # Restore desktop viewport for subsequent tests
        page.set_viewport_size({"width": 1280, "height": 720})
