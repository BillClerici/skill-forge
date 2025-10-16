#!/usr/bin/env python3
"""
Playwright test for the game session page
Tests UI elements, interactions, and captures screenshots
"""

import asyncio
import json
from datetime import datetime
from playwright.async_api import async_playwright, Page, Browser, BrowserContext
from pathlib import Path

# Configuration
TEST_URL = "http://localhost:8000/game/session/session_1760577331.303933_875f7b7e-2d6d-44e3-bfe7-b824cb1ad35f/"
SCREENSHOT_DIR = Path(__file__).parent / "screenshots"
RESULTS_FILE = Path(__file__).parent / "game_session_test_results.json"

# Create screenshots directory if it doesn't exist
SCREENSHOT_DIR.mkdir(exist_ok=True)

class GameSessionTester:
    def __init__(self):
        self.results = {
            "timestamp": datetime.now().isoformat(),
            "url": TEST_URL,
            "test_results": [],
            "ui_elements": {},
            "errors": [],
            "console_logs": [],
            "screenshots": []
        }

    async def run_tests(self):
        """Run all Playwright tests"""
        async with async_playwright() as p:
            # Launch browser (headless=False to see what's happening)
            browser = await p.chromium.launch(headless=False)
            context = await browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                record_video_dir=str(SCREENSHOT_DIR / "videos") if False else None
            )

            # Listen to console messages
            page = await context.new_page()
            page.on("console", lambda msg: self.results["console_logs"].append({
                "type": msg.type,
                "text": msg.text
            }))

            # Listen to page errors
            page.on("pageerror", lambda exc: self.results["errors"].append({
                "type": "page_error",
                "message": str(exc)
            }))

            try:
                # Run test sequence
                await self.test_page_load(page)
                await self.test_ui_elements(page)
                await self.test_interactive_elements(page)
                await self.test_responsiveness(page)

                # Final full-page screenshot
                await self.take_screenshot(page, "final_state")

            except Exception as e:
                self.results["errors"].append({
                    "type": "test_exception",
                    "message": str(e)
                })
                print(f"Error during testing: {e}")

            finally:
                await browser.close()

        # Save results
        self.save_results()
        return self.results

    async def test_page_load(self, page: Page):
        """Test basic page loading"""
        test_name = "Page Load Test"
        print(f"\n=== {test_name} ===")

        try:
            # Navigate to the page with timeout
            response = await page.goto(TEST_URL, wait_until="networkidle", timeout=30000)

            # Check response status
            status = response.status if response else None
            success = status == 200

            result = {
                "test": test_name,
                "success": success,
                "status_code": status,
                "url": page.url,
                "title": await page.title()
            }

            self.results["test_results"].append(result)
            print(f"Status: {status}")
            print(f"Title: {result['title']}")
            print(f"Success: {success}")

            # Take screenshot
            await self.take_screenshot(page, "page_load")

            # Wait a bit for dynamic content
            await page.wait_for_timeout(2000)

        except Exception as e:
            self.results["test_results"].append({
                "test": test_name,
                "success": False,
                "error": str(e)
            })
            print(f"Failed: {e}")

    async def test_ui_elements(self, page: Page):
        """Identify and catalog all UI elements on the page"""
        test_name = "UI Elements Discovery"
        print(f"\n=== {test_name} ===")

        ui_elements = {}

        try:
            # Check for common game session elements
            elements_to_check = {
                "scene_description": [
                    "#scene-description",
                    ".scene-description",
                    "[data-testid='scene-description']",
                    "div.scene",
                    ".story-content"
                ],
                "action_input": [
                    "#action-input",
                    "textarea[name='action']",
                    "input[type='text']",
                    "textarea",
                    ".action-input"
                ],
                "submit_button": [
                    "button[type='submit']",
                    "#submit-action",
                    "button.btn-primary",
                    "button:has-text('Submit')",
                    "button:has-text('Send')",
                    "button:has-text('Act')"
                ],
                "story_log": [
                    "#story-log",
                    ".story-log",
                    ".game-log",
                    ".history",
                    ".messages"
                ],
                "character_info": [
                    "#character-info",
                    ".character-info",
                    ".player-info",
                    ".stats"
                ],
                "inventory": [
                    "#inventory",
                    ".inventory",
                    ".items"
                ],
                "controls": [
                    ".controls",
                    ".game-controls",
                    "#controls"
                ]
            }

            for element_type, selectors in elements_to_check.items():
                found = False
                for selector in selectors:
                    try:
                        element = page.locator(selector).first
                        count = await element.count()
                        if count > 0:
                            # Get element details
                            is_visible = await element.is_visible(timeout=1000)
                            if is_visible:
                                text_content = await element.text_content()
                                html = await element.inner_html()

                                ui_elements[element_type] = {
                                    "found": True,
                                    "selector": selector,
                                    "visible": is_visible,
                                    "text_preview": text_content[:200] if text_content else None,
                                    "html_preview": html[:200] if html else None
                                }
                                print(f"[+] Found {element_type}: {selector}")
                                found = True
                                break
                    except Exception as e:
                        continue

                if not found:
                    ui_elements[element_type] = {"found": False}
                    print(f"[-] Not found: {element_type}")

            # Get all buttons
            buttons = page.locator("button")
            button_count = await buttons.count()
            button_texts = []
            for i in range(min(button_count, 20)):  # Limit to first 20
                try:
                    text = await buttons.nth(i).text_content()
                    if text:
                        button_texts.append(text.strip())
                except:
                    pass

            ui_elements["all_buttons"] = {
                "count": button_count,
                "texts": button_texts
            }
            print(f"\nTotal buttons: {button_count}")
            print(f"Button texts: {button_texts}")

            # Get all input fields
            inputs = page.locator("input, textarea")
            input_count = await inputs.count()
            input_types = []
            for i in range(min(input_count, 20)):
                try:
                    input_type = await inputs.nth(i).get_attribute("type")
                    placeholder = await inputs.nth(i).get_attribute("placeholder")
                    input_types.append({
                        "type": input_type or "text",
                        "placeholder": placeholder
                    })
                except:
                    pass

            ui_elements["all_inputs"] = {
                "count": input_count,
                "details": input_types
            }
            print(f"\nTotal input fields: {input_count}")

            # Get page structure
            main_content = await page.content()
            ui_elements["page_structure"] = {
                "has_form": "<form" in main_content,
                "has_script": "<script" in main_content,
                "has_websocket": "websocket" in main_content.lower() or "ws://" in main_content.lower(),
                "content_length": len(main_content)
            }

            self.results["ui_elements"] = ui_elements
            self.results["test_results"].append({
                "test": test_name,
                "success": True,
                "elements_found": sum(1 for e in ui_elements.values() if isinstance(e, dict) and e.get("found"))
            })

            # Take screenshot
            await self.take_screenshot(page, "ui_elements")

        except Exception as e:
            self.results["test_results"].append({
                "test": test_name,
                "success": False,
                "error": str(e)
            })
            print(f"Failed: {e}")

    async def test_interactive_elements(self, page: Page):
        """Test interaction with page elements"""
        test_name = "Interactive Elements Test"
        print(f"\n=== {test_name} ===")

        interactions = []

        try:
            # Test 1: Try to find and interact with text input
            textarea_selectors = ["textarea", "input[type='text']", "#action-input"]
            for selector in textarea_selectors:
                try:
                    textarea = page.locator(selector).first
                    if await textarea.count() > 0 and await textarea.is_visible(timeout=1000):
                        print(f"[+] Found input field: {selector}")

                        # Try to type in it
                        await textarea.click()
                        await textarea.fill("Test action: Look around")
                        await page.wait_for_timeout(500)

                        value = await textarea.input_value()
                        interactions.append({
                            "action": "fill_input",
                            "selector": selector,
                            "success": True,
                            "value": value
                        })
                        print(f"  Entered text: {value}")

                        await self.take_screenshot(page, "text_input_filled")
                        break
                except Exception as e:
                    print(f"  Failed to interact with {selector}: {e}")
                    continue

            # Test 2: Try to find and click buttons
            button_selectors = [
                "button[type='submit']",
                "button:has-text('Submit')",
                "button:has-text('Send')",
                "button.btn-primary",
                "button"
            ]

            for selector in button_selectors:
                try:
                    button = page.locator(selector).first
                    if await button.count() > 0 and await button.is_visible(timeout=1000):
                        button_text = await button.text_content()
                        print(f"[+] Found button: '{button_text}' ({selector})")

                        # Check if button is enabled
                        is_disabled = await button.is_disabled()

                        interactions.append({
                            "action": "found_button",
                            "selector": selector,
                            "text": button_text,
                            "disabled": is_disabled
                        })

                        if not is_disabled:
                            print(f"  Button is enabled (not clicking in this test)")
                            # Note: We're not actually clicking to avoid triggering real game actions
                        break
                except Exception as e:
                    continue

            # Test 3: Check for clickable links
            links = page.locator("a")
            link_count = await links.count()
            if link_count > 0:
                print(f"\n[+] Found {link_count} links on page")
                link_texts = []
                for i in range(min(link_count, 10)):
                    try:
                        text = await links.nth(i).text_content()
                        href = await links.nth(i).get_attribute("href")
                        if text:
                            link_texts.append({"text": text.strip(), "href": href})
                    except:
                        pass

                interactions.append({
                    "action": "found_links",
                    "count": link_count,
                    "samples": link_texts
                })

            # Test 4: Check for any error messages or warnings
            error_selectors = [".error", ".alert", ".warning", ".message.error"]
            for selector in error_selectors:
                try:
                    error_elem = page.locator(selector).first
                    if await error_elem.count() > 0 and await error_elem.is_visible(timeout=500):
                        error_text = await error_elem.text_content()
                        interactions.append({
                            "action": "found_error_message",
                            "selector": selector,
                            "text": error_text
                        })
                        print(f"[!] Found error message: {error_text}")
                except:
                    continue

            self.results["test_results"].append({
                "test": test_name,
                "success": True,
                "interactions": interactions
            })

        except Exception as e:
            self.results["test_results"].append({
                "test": test_name,
                "success": False,
                "error": str(e)
            })
            print(f"Failed: {e}")

    async def test_responsiveness(self, page: Page):
        """Test page at different viewport sizes"""
        test_name = "Responsiveness Test"
        print(f"\n=== {test_name} ===")

        viewports = [
            {"name": "mobile", "width": 375, "height": 667},
            {"name": "tablet", "width": 768, "height": 1024},
            {"name": "desktop", "width": 1920, "height": 1080}
        ]

        try:
            for viewport in viewports:
                print(f"Testing viewport: {viewport['name']} ({viewport['width']}x{viewport['height']})")
                await page.set_viewport_size({
                    "width": viewport["width"],
                    "height": viewport["height"]
                })
                await page.wait_for_timeout(1000)
                await self.take_screenshot(page, f"viewport_{viewport['name']}")

            # Reset to desktop
            await page.set_viewport_size({"width": 1920, "height": 1080})

            self.results["test_results"].append({
                "test": test_name,
                "success": True,
                "viewports_tested": len(viewports)
            })

        except Exception as e:
            self.results["test_results"].append({
                "test": test_name,
                "success": False,
                "error": str(e)
            })
            print(f"Failed: {e}")

    async def take_screenshot(self, page: Page, name: str):
        """Take a screenshot and save it"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{name}_{timestamp}.png"
            filepath = SCREENSHOT_DIR / filename

            await page.screenshot(path=str(filepath), full_page=True)
            self.results["screenshots"].append({
                "name": name,
                "path": str(filepath),
                "timestamp": timestamp
            })
            print(f"[SCREENSHOT] Saved: {filepath}")

        except Exception as e:
            print(f"Failed to take screenshot: {e}")

    def save_results(self):
        """Save test results to JSON file"""
        try:
            with open(RESULTS_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.results, f, indent=2, ensure_ascii=False)
            print(f"\n[+] Results saved to: {RESULTS_FILE}")
        except Exception as e:
            print(f"Failed to save results: {e}")

    def print_summary(self):
        """Print a summary of test results"""
        print("\n" + "="*80)
        print("TEST SUMMARY")
        print("="*80)

        total_tests = len(self.results["test_results"])
        passed_tests = sum(1 for t in self.results["test_results"] if t.get("success"))

        print(f"\nTests Run: {total_tests}")
        print(f"Tests Passed: {passed_tests}")
        print(f"Tests Failed: {total_tests - passed_tests}")

        print(f"\nUI Elements Found:")
        for element, details in self.results["ui_elements"].items():
            if isinstance(details, dict) and details.get("found"):
                print(f"  [+] {element}")

        print(f"\nConsole Logs: {len(self.results['console_logs'])}")
        for log in self.results["console_logs"][:5]:  # Show first 5
            print(f"  [{log['type']}] {log['text'][:100]}")

        print(f"\nErrors: {len(self.results['errors'])}")
        for error in self.results["errors"]:
            print(f"  [-] [{error['type']}] {error['message'][:100]}")

        print(f"\nScreenshots: {len(self.results['screenshots'])}")
        for screenshot in self.results["screenshots"]:
            print(f"  [IMG] {screenshot['name']}: {screenshot['path']}")

        print("\n" + "="*80)


async def main():
    """Main test runner"""
    print("="*80)
    print("GAME SESSION PAGE PLAYWRIGHT TEST")
    print("="*80)
    print(f"URL: {TEST_URL}")
    print(f"Screenshot Directory: {SCREENSHOT_DIR}")
    print(f"Results File: {RESULTS_FILE}")
    print("="*80)

    tester = GameSessionTester()
    await tester.run_tests()
    tester.print_summary()

    return tester.results


if __name__ == "__main__":
    results = asyncio.run(main())
