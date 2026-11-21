"""Browser regression for a timeline period containing events on multiple contracts."""
import argparse
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from playwright.sync_api import expect, sync_playwright


def check_timeline(page, url):
    page.goto(url)
    bars = page.locator(".timeline-bar")
    expect(bars.first).to_be_visible()
    initial_count = bars.count()
    page.get_by_role("button", name="Filters").click()
    picker = page.get_by_role("combobox", name="Rental Contract")
    picker.click()
    page.get_by_role("option").nth(1).click()
    contract = page.locator(".timeline-contract")
    expect(contract).to_be_visible()
    contract_id = contract.get_attribute("href").rsplit("/", 1)[-1]
    selected_label = picker.input_value()
    assert 0 < bars.count() < initial_count
    page.get_by_role("button", name="Reset filters").click()
    expect(picker).to_have_value("")
    expect(bars).to_have_count(initial_count)

    for width in (1440, 390):
        page.set_viewport_size({"width": width, "height": 850})
        opener = bars.first
        opener.focus()
        page.keyboard.press("Enter")
        dialog = page.get_by_role("dialog")
        close = dialog.get_by_role("button", name="Close")
        link = dialog.get_by_role("link")
        expect(close).to_be_focused()
        for key, target in (("Tab", link), ("Tab", close), ("Shift+Tab", link), ("Shift+Tab", close)):
            page.keyboard.press(key)
            expect(target).to_be_focused()
        page.keyboard.press("Escape")
        expect(dialog).to_be_hidden()
        expect(opener).to_be_focused()

    parts = urlsplit(url)
    params = dict(parse_qsl(parts.query), assignment=contract_id)
    page.goto(urlunsplit(parts._replace(query=urlencode(params))))
    expect(bars.first).to_be_visible()
    page.get_by_role("button", name="Filters").click()
    page.get_by_role("button", name="Reset filters").click()
    expect(picker).to_have_value(selected_label)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url", help="Unscoped timeline URL with a populated date range")
    parser.add_argument("--storage-state", required=True, help="Playwright storage state for a signed-in English user")
    parser.add_argument("--site", help="Frappe site header when testing via localhost")
    parser.add_argument("--chromium", help="Optional path to a local Chromium executable")
    args = parser.parse_args()
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path=args.chromium)
        context = browser.new_context(storage_state=args.storage_state,
            extra_http_headers={"X-Frappe-Site-Name": args.site} if args.site else {})
        try:
            check_timeline(context.new_page(), args.url)
        finally:
            browser.close()
