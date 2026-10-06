"""Browser-backed layout check; optional dependency errors are actionable."""
import argparse
from pathlib import Path
import sys

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--negative', choices=['console', 'clipping'])
    parser.add_argument('--browser', help='Optional installed Chromium executable')
    args = parser.parse_args()
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print('Optional Playwright is unavailable. Create an isolated environment: '
              'python -m venv .venv; then use its Python to run '
              "-m pip install playwright and -m playwright install chromium. "
              'Do not install into the agent environment.', file=sys.stderr)
        return 2
    out = Path(__file__).resolve().parents[1] / 'outputs'
    out.mkdir(exist_ok=True)
    errors = []
    try:
        with sync_playwright() as engine:
            browser = engine.chromium.launch(**({'executable_path': args.browser} if args.browser else {}))
            page = browser.new_page(viewport={'width': 1280, 'height': 720})
            page.on('console', lambda msg: errors.append(msg.text) if msg.type == 'error' else None)
            page.on('pageerror', lambda error: errors.append(str(error)))
            for layout in ('a-cards', 'b-columns'):
                page.goto((Path(__file__).resolve().parents[1] / 'fixtures' / layout / 'index.html').as_uri())
                page.evaluate('document.fonts.ready')
                if args.negative == 'console':
                    page.evaluate("console.error('Deliberate test error')")
                if args.negative == 'clipping':
                    page.evaluate("document.querySelector('[data-check]').style.width='1px'")
                clipped = page.locator('[data-check]').evaluate_all('(els) => els.some(e => e.scrollWidth > e.clientWidth || e.scrollHeight > e.clientHeight)')
                if errors or clipped:
                    print(f'FAIL {layout}: console_errors={len(errors)}, clipped={clipped}')
                    browser.close()
                    return 1
                page.screenshot(path=str(out / (layout + '.png')), full_page=True)
                print(f'PASS {layout}: console_errors=0, clipped=False')
            browser.close()
    except Exception as error:
        print('Browser unavailable or rendering failed. Run isolated-environment Python '
              '-m playwright install chromium, or pass --browser with an installed Chromium executable. '
              + type(error).__name__, file=sys.stderr)
        return 2
    return 0
if __name__ == '__main__':
    sys.exit(main())
