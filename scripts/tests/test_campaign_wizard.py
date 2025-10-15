"""
Playwright automation script for Campaign Design Wizard
Creates a full campaign by going through all 11 wizard steps
"""

import asyncio
from playwright.async_api import async_playwright, expect
import time
import sys

# Fix encoding for Windows console
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

async def run_campaign_wizard():
    async with async_playwright() as p:
        # Launch browser
        browser = await p.chromium.launch(headless=False, slow_mo=500)
        context = await browser.new_context()
        page = await context.new_page()

        print("=" * 80)
        print("CAMPAIGN DESIGN WIZARD - AUTOMATED TEST")
        print("=" * 80)

        try:
            # Navigate to campaigns page
            print("\n[0/11] Navigating to Campaigns page...")
            await page.goto('http://localhost:8000/campaigns/', wait_until='domcontentloaded')
            await page.wait_for_timeout(2000)

            # Click first Campaign Design Wizard button
            print("  → Clicking 'Campaign Design Wizard' button...")
            wizard_button = page.get_by_text('Campaign Design Wizard', exact=False).first
            await wizard_button.click()
            await page.wait_for_timeout(3000)

            # Wait for the wizard form to be visible
            print("  → Waiting for wizard to load...")
            await page.wait_for_selector('#wizard-form', timeout=10000)

            # Step 1: Campaign Name & Universe
            print("\n[1/11] STEP 1: Campaign Name & Universe Selection")
            campaign_name = f"Playwright Test Campaign {int(time.time())}"
            print(f"  → Entering campaign name: {campaign_name}")

            # Wait for campaign name input to be visible and enabled
            campaign_input = page.locator('#campaign_name')
            await campaign_input.wait_for(state='visible', timeout=10000)
            await campaign_input.fill(campaign_name)

            print("  → Selecting first available universe...")
            # Click the visible label instead of hidden radio button
            universe_label = page.locator('.universe-card').first
            await universe_label.click()

            print("  → Clicking Next...")
            await page.click('#next-btn')
            await page.wait_for_timeout(2000)

            # Step 2: World Selection
            print("\n[2/11] STEP 2: World Selection")
            print("  → Waiting for worlds to load...")
            await page.wait_for_selector('.world-card', timeout=10000)

            print("  → Selecting first available world...")
            # Click the visible label instead of hidden radio button
            world_label = page.locator('.world-card').first
            await world_label.click()

            print("  → Clicking Next...")
            await page.click('#next-btn')
            await page.wait_for_timeout(2000)

            # Step 3: Region Selection
            print("\n[3/11] STEP 3: Region Selection")
            print("  → Selecting 'Entire World' option...")
            # Click the visible label instead of hidden radio button
            entire_world_label = page.locator('.region-card').first
            await entire_world_label.click()

            print("  → Clicking Next...")
            await page.click('#next-btn')
            await page.wait_for_timeout(2000)

            # Step 4: Story Idea (Optional)
            print("\n[4/11] STEP 4: Story Idea Input")
            print("  → Adding optional story idea...")
            story_idea = "An epic adventure where heroes must recover ancient artifacts to save the realm from an awakening darkness."
            await page.fill('#user_story_idea', story_idea)

            print("  → Clicking 'Generate Campaign Ideas'...")
            await page.click('#generate-stories-btn')

            # Wait for loading overlay
            print("  → Waiting for story generation...")
            await page.wait_for_selector('#loading-overlay', state='visible', timeout=5000)

            # Step 5: Story Selection
            print("\n[5/11] STEP 5: Story Selection (waiting for AI generation - up to 5 min)...")
            # Wait for stories to be generated (overlay disappears)
            await page.wait_for_selector('#loading-overlay', state='hidden', timeout=300000)  # 5 minutes
            print("  → Stories generated!")

            # Wait for story cards to appear
            await page.wait_for_selector('.story-idea-card', timeout=10000)

            print("  → Selecting first story idea...")
            # Click the visible label instead of hidden radio button
            story_label = page.locator('.story-idea-card').first
            await story_label.click()

            print("  → Clicking Next...")
            await page.click('#next-btn')
            await page.wait_for_timeout(2000)

            # Wait for campaign core generation
            print("  → Waiting for campaign core generation...")
            await page.wait_for_selector('#loading-overlay', state='visible', timeout=5000)

            # Step 6: Campaign Core Review
            print("\n[6/11] STEP 6: Campaign Core Review (waiting for AI generation - up to 5 min)...")
            await page.wait_for_selector('#loading-overlay', state='hidden', timeout=300000)  # 5 minutes
            print("  → Campaign core generated!")

            print("  → Reviewing campaign core...")
            await page.wait_for_timeout(2000)

            print("  → Clicking Next to approve core...")
            await page.click('#next-btn')
            await page.wait_for_timeout(2000)

            # Step 7: Quest Settings
            print("\n[7/11] STEP 7: Quest Configuration")
            print("  → Setting number of quests to 2...")
            quest_slider = page.locator('#num_quests')
            await quest_slider.evaluate('el => el.value = 2')
            await quest_slider.dispatch_event('input')

            print("  → Setting difficulty to Medium (already default)...")
            # Difficulty is already set to Medium by default, skip it

            print("  → Setting playtime to 60 minutes...")
            await page.fill('#quest_playtime_minutes', '60')

            print("  → Disabling image generation (faster)...")
            # Uncheck the checkbox using JavaScript to avoid label interception
            await page.evaluate('document.getElementById("generate_images_quests").checked = false')

            print("  → Clicking Next to generate quests...")
            await page.click('#next-btn')
            await page.wait_for_timeout(2000)

            # Wait for quest generation
            print("  → Waiting for quest generation...")
            await page.wait_for_selector('#loading-overlay', state='visible', timeout=5000)

            # Step 8: Quest Review
            print("\n[8/11] STEP 8: Quest Review (waiting for AI generation - up to 10 min)...")
            await page.wait_for_selector('#loading-overlay', state='hidden', timeout=600000)  # 10 minutes
            print("  → Quests generated!")

            print("  → Reviewing quests...")
            await page.wait_for_timeout(2000)

            print("  → Clicking Next to approve quests...")
            await page.click('#next-btn')
            await page.wait_for_timeout(2000)

            # Step 9: Place Review
            print("\n[9/11] STEP 9: Place Review (waiting for AI generation - up to 10 min)...")
            # Wait for place generation (overlay might already be hidden if generation is fast)
            try:
                await page.wait_for_selector('#loading-overlay', state='visible', timeout=3000)
            except:
                print("  → Loading overlay not detected (generation may have started immediately)")
            await page.wait_for_selector('#loading-overlay', state='hidden', timeout=600000)  # 10 minutes
            print("  → Places generated!")

            print("  → Reviewing places...")
            await page.wait_for_timeout(2000)

            print("  → Clicking Next to approve places...")
            await page.click('#next-btn')
            await page.wait_for_timeout(2000)

            # Step 10: Scene Review
            print("\n[10/11] STEP 10: Scene Review (waiting for AI generation - up to 15 min)...")
            # Wait for scene generation (overlay might already be hidden if generation is fast)
            try:
                await page.wait_for_selector('#loading-overlay', state='visible', timeout=3000)
            except:
                print("  → Loading overlay not detected (generation may have started immediately)")
            await page.wait_for_selector('#loading-overlay', state='hidden', timeout=900000)  # 15 minutes
            print("  → Scenes generated!")

            print("  → Reviewing scenes...")
            await page.wait_for_timeout(2000)

            print("  → Clicking Next to proceed to final review...")
            await page.click('#next-btn')
            await page.wait_for_timeout(2000)

            # Step 11: Final Review & Finalize
            print("\n[11/11] STEP 11: Final Review & Finalize")
            print("  → Reviewing final campaign summary...")
            await page.wait_for_timeout(2000)

            print("  → Clicking 'Finalize Campaign'...")
            await page.click('#finalize-btn')

            # Wait for finalization
            print("  → Waiting for campaign finalization (up to 5 min)...")
            try:
                await page.wait_for_selector('#loading-overlay', state='visible', timeout=3000)
            except:
                print("  → Loading overlay not detected (finalization may have started immediately)")
            await page.wait_for_selector('#loading-overlay', state='hidden', timeout=300000)  # 5 minutes

            print("\n" + "=" * 80)
            print("✓ CAMPAIGN CREATION COMPLETE!")
            print("=" * 80)

            # Wait for redirect to campaign detail page
            await page.wait_for_timeout(3000)

            # Get final URL
            final_url = page.url
            print(f"\n→ Redirected to: {final_url}")

            # Take screenshot of final campaign
            screenshot_path = f"campaign_wizard_complete_{int(time.time())}.png"
            await page.screenshot(path=screenshot_path)
            print(f"→ Screenshot saved: {screenshot_path}")

            # Keep browser open for review
            print("\n→ Keeping browser open for 60 seconds for review...")
            print("  (You can manually close the browser window to exit sooner)")
            await page.wait_for_timeout(60000)

        except Exception as e:
            print(f"\n✗ ERROR: {str(e)}")
            # Take error screenshot
            error_screenshot = f"campaign_wizard_error_{int(time.time())}.png"
            await page.screenshot(path=error_screenshot)
            print(f"→ Error screenshot saved: {error_screenshot}")
            print("\n→ Keeping browser open for 30 seconds to review error...")
            await page.wait_for_timeout(30000)
            raise

        finally:
            await browser.close()

if __name__ == "__main__":
    print("\nStarting Playwright Campaign Wizard Test...")
    print("Make sure Django server is running on http://localhost:8000\n")
    asyncio.run(run_campaign_wizard())
