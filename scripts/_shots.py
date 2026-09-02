"""Capture guide screenshots with Playwright + PIL overlays."""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from playwright.sync_api import sync_playwright

OUT = Path("docs/guide-assets")
OUT.mkdir(parents=True, exist_ok=True)
BASE = "http://127.0.0.1:8765"


def font_pair():
    try:
        return (
            ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 22),
            ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 15),
        )
    except Exception:
        f = ImageFont.load_default()
        return f, f


def annotate(path: Path, label: str, boxes=None) -> None:
    img = Image.open(path).convert("RGBA")
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    font, small = font_pair()
    draw.rectangle([0, 0, img.width, 44], fill=(15, 23, 42, 220))
    draw.text((14, 10), label, fill=(248, 250, 252, 255), font=font)
    for box in boxes or []:
        x1, y1, x2, y2, caption = box
        draw.rectangle([x1, y1, x2, y2], outline=(250, 204, 21, 255), width=4)
        tw = max(120, len(caption) * 9)
        draw.rectangle([x1, max(44, y1 - 26), x1 + tw, y1], fill=(250, 204, 21, 230))
        draw.text((x1 + 6, max(46, y1 - 22)), caption, fill=(15, 23, 42, 255), font=small)
    Image.alpha_composite(img, overlay).convert("RGB").save(path, "PNG")


def box_from_locator(locator):
    bb = locator.bounding_box()
    if not bb:
        return None
    return (bb["x"] - 4, bb["y"] - 4, bb["x"] + bb["width"] + 4, bb["y"] + bb["height"] + 4)


def main() -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 900})

        # 01 home
        page.goto(BASE + "/", wait_until="networkidle")
        page.screenshot(path=str(OUT / "01-home.png"), full_page=False)
        annotate(OUT / "01-home.png", "Overview · paste public DID or + New Agent")

        # 02 register form — jump to DID step
        page.goto(BASE + "/ui/agents/new", wait_until="networkidle")
        page.click('[data-step-btn="2"]')
        page.wait_for_selector('section[data-step="2"]:not([hidden])')
        did_input = page.locator('input[name="did"]')
        page.screenshot(path=str(OUT / "02-register-form.png"), full_page=False)
        b = box_from_locator(did_input)
        boxes = []
        if b:
            boxes.append((*b, "Public DID field"))
        annotate(OUT / "02-register-form.png", "Register · step 2 Public DID", boxes)

        # 03 filled SAFE example (no secrets)
        page.fill('input[name="did"]', "did:example:guide-demo-agent")
        page.fill('input[name="public_key"]', "")
        page.fill('input[name="endpoint"]', "https://example.invalid/agents/guide-demo")
        page.click('[data-step-btn="1"]')
        page.wait_for_selector('section[data-step="1"]:not([hidden])')
        page.fill('input[name="name"]', "Guide Demo Agent")
        page.fill('input[name="id"]', "guide-demo-agent")
        page.fill('textarea[name="description"]', "Fictional demo agent for screenshots. Public identifier only.")
        page.click('[data-step-btn="3"]')
        page.wait_for_selector('section[data-step="3"]:not([hidden])')
        # check pdf-analysis if present
        cap = page.locator('input[name="capability"][value="pdf-analysis"]')
        if cap.count():
            cap.check()
        page.click('[data-step-btn="4"]')
        page.wait_for_selector('section[data-step="4"]:not([hidden])')
        # ensure fictional checked
        fic = page.locator('input[name="fictional"]')
        if not fic.is_checked():
            fic.check()
        page.select_option('select[name="status"]', "online")
        page.click('[data-step-btn="5"]')
        page.wait_for_selector('section[data-step="5"]:not([hidden])')
        # go back to DID step for a clear filled DID shot + review
        page.click('[data-step-btn="2"]')
        page.wait_for_selector('section[data-step="2"]:not([hidden])')
        page.screenshot(path=str(OUT / "03-register-filled.png"), full_page=False)
        b = box_from_locator(page.locator('input[name="did"]'))
        boxes = []
        if b:
            boxes.append((*b, "SAFE example DID"))
        annotate(OUT / "03-register-filled.png", "Filled form · SAFE public example data", boxes)

        # 04 agent profile
        page.goto(BASE + "/ui/agents/guide-demo-agent", wait_until="networkidle")
        page.screenshot(path=str(OUT / "04-agent-profile.png"), full_page=False)
        annotate(OUT / "04-agent-profile.png", "Agent profile · Registered (DEMO / FICTIONAL)")

        # 05 communicate
        page.goto(
            BASE + "/ui/communicate?requester=test-research&assignee=test-document&capability=pdf-analysis",
            wait_until="networkidle",
        )
        page.screenshot(path=str(OUT / "05-communicate.png"), full_page=False)
        annotate(OUT / "05-communicate.png", "Communicate · registry-mediated A2A task")

        # 06 tclk
        page.goto(BASE + "/ui/tclk", wait_until="networkidle")
        page.screenshot(path=str(OUT / "06-tclk.png"), full_page=False)
        annotate(OUT / "06-tclk.png", "tclk/1 · protocol vs unverified settlement")

        browser.close()

    print("screenshots:", sorted(p.name for p in OUT.glob("*.png")))


if __name__ == "__main__":
    main()
