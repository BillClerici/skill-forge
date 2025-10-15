"""
Sequential Campaign Creation Script
Creates multiple campaigns one at a time with extended timeouts
"""

import asyncio
from playwright.async_api import async_playwright
import time
import sys

# Fix encoding for Windows console
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

async def create_single_campaign(campaign_config):
    """Create a single campaign with given configuration"""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, slow_mo=300)
        context = await browser.new_context()
        page = await context.new_page()

        campaign_num = campaign_config['num']
        num_quests = campaign_config['quests']
        difficulty = campaign_config['difficulty']
        playtime = campaign_config['playtime']
        story_seed = campaign_config['story']

        print(f"\n{'='*80}")
        print(f"CAMPAIGN #{campaign_num}: {num_quests} quests, {difficulty}, {playtime} min")
        print(f"{'='*80}\n")

        try:
            # Navigate and start wizard
            await page.goto('http://localhost:8000/campaigns/', wait_until='domcontentloaded')
            await page.wait_for_timeout(2000)

            wizard_button = page.get_by_text('Campaign Design Wizard', exact=False).first
            await wizard_button.click()
            await page.wait_for_timeout(3000)
            await page.wait_for_selector('#wizard-form', timeout=10000)

            # Step 1: Campaign Name & Universe
            print(f"[{campaign_num}] Step 1/11: Campaign setup...")
            campaign_name = f"Campaign {campaign_num} - {difficulty} {num_quests}Q - {int(time.time())}"
            campaign_input = page.locator('#campaign_name')
            await campaign_input.wait_for(state='visible', timeout=10000)
            await campaign_input.fill(campaign_name)

            universe_label = page.locator('.universe-card').first
            await universe_label.click()
            await page.click('#next-btn')
            await page.wait_for_timeout(2000)

            # Step 2: World
            print(f"[{campaign_num}] Step 2/11: Selecting world...")
            await page.wait_for_selector('.world-card', timeout=10000)
            world_label = page.locator('.world-card').first
            await world_label.click()
            await page.click('#next-btn')
            await page.wait_for_timeout(2000)

            # Step 3: Region
            print(f"[{campaign_num}] Step 3/11: Selecting region...")
            entire_world_label = page.locator('.region-card').first
            await entire_world_label.click()
            await page.click('#next-btn')
            await page.wait_for_timeout(2000)

            # Step 4: Story Idea
            print(f"[{campaign_num}] Step 4/11: Adding story idea...")
            await page.fill('#user_story_idea', story_seed)
            await page.click('#generate-stories-btn')
            await page.wait_for_selector('#loading-overlay', state='visible', timeout=5000)

            # Step 5: Story Generation (5 min timeout)
            print(f"[{campaign_num}] Step 5/11: Waiting for AI story generation (up to 5 min)...")
            await page.wait_for_selector('#loading-overlay', state='hidden', timeout=300000)
            print(f"[{campaign_num}]   ✓ Stories generated!")

            await page.wait_for_selector('.story-idea-card', timeout=10000)
            story_label = page.locator('.story-idea-card').first
            await story_label.click()
            await page.click('#next-btn')
            await page.wait_for_timeout(2000)

            # Step 6: Campaign Core (5 min timeout)
            print(f"[{campaign_num}] Step 6/11: Waiting for campaign core (up to 5 min)...")
            await page.wait_for_selector('#loading-overlay', state='visible', timeout=5000)
            await page.wait_for_selector('#loading-overlay', state='hidden', timeout=300000)
            print(f"[{campaign_num}]   ✓ Campaign core generated!")

            await page.wait_for_timeout(2000)
            await page.click('#next-btn')
            await page.wait_for_timeout(2000)

            # Step 7: Quest Settings
            print(f"[{campaign_num}] Step 7/11: Configuring quests ({num_quests})...")
            quest_slider = page.locator('#num_quests')
            await quest_slider.evaluate(f'el => el.value = {num_quests}')
            await quest_slider.dispatch_event('input')

            await page.fill('#quest_playtime_minutes', str(playtime))
            await page.evaluate('document.getElementById("generate_images_quests").checked = false')

            await page.click('#next-btn')
            await page.wait_for_timeout(2000)

            # Step 8: Quest Generation (10 min timeout)
            print(f"[{campaign_num}] Step 8/11: Generating quests (up to 10 min)...")
            try:
                await page.wait_for_selector('#loading-overlay', state='visible', timeout=3000)
            except:
                pass
            await page.wait_for_selector('#loading-overlay', state='hidden', timeout=600000)
            print(f"[{campaign_num}]   ✓ Quests generated!")

            await page.wait_for_timeout(2000)
            await page.click('#next-btn')
            await page.wait_for_timeout(2000)

            # Step 9: Place Generation (10 min timeout)
            print(f"[{campaign_num}] Step 9/11: Generating places (up to 10 min)...")
            try:
                await page.wait_for_selector('#loading-overlay', state='visible', timeout=3000)
            except:
                pass
            await page.wait_for_selector('#loading-overlay', state='hidden', timeout=600000)
            print(f"[{campaign_num}]   ✓ Places generated!")

            await page.wait_for_timeout(2000)
            await page.click('#next-btn')
            await page.wait_for_timeout(2000)

            # Step 10: Scene Generation (15 min timeout)
            print(f"[{campaign_num}] Step 10/11: Generating scenes (up to 15 min)...")
            try:
                await page.wait_for_selector('#loading-overlay', state='visible', timeout=3000)
            except:
                pass
            await page.wait_for_selector('#loading-overlay', state='hidden', timeout=900000)
            print(f"[{campaign_num}]   ✓ Scenes generated!")

            await page.wait_for_timeout(2000)
            await page.click('#next-btn')
            await page.wait_for_timeout(2000)

            # Step 11: Finalization (5 min timeout)
            print(f"[{campaign_num}] Step 11/11: Finalizing campaign (up to 5 min)...")
            await page.click('#finalize-btn')
            try:
                await page.wait_for_selector('#loading-overlay', state='visible', timeout=3000)
            except:
                pass
            await page.wait_for_selector('#loading-overlay', state='hidden', timeout=300000)

            print(f"\n{'='*80}")
            print(f"✓✓✓ CAMPAIGN #{campaign_num} CREATED SUCCESSFULLY!")
            print(f"{'='*80}\n")

            # Get final URL
            final_url = page.url
            print(f"[{campaign_num}] Campaign URL: {final_url}")

            # Take screenshot
            screenshot_path = f"campaign_{campaign_num}_success_{int(time.time())}.png"
            await page.screenshot(path=screenshot_path)
            print(f"[{campaign_num}] Screenshot: {screenshot_path}")

            await page.wait_for_timeout(5000)
            return True

        except Exception as e:
            print(f"\n{'='*80}")
            print(f"✗✗✗ CAMPAIGN #{campaign_num} FAILED!")
            print(f"Error: {str(e)}")
            print(f"{'='*80}\n")

            error_screenshot = f"campaign_{campaign_num}_error_{int(time.time())}.png"
            await page.screenshot(path=error_screenshot)
            print(f"[{campaign_num}] Error screenshot: {error_screenshot}")

            await page.wait_for_timeout(5000)
            return False

        finally:
            await browser.close()

async def main():
    # Define campaigns to create sequentially
    campaigns = [
        {
            'num': 1,
            'quests': 2,
            'difficulty': 'Medium',
            'playtime': 60,
            'story': 'A mysterious plague threatens the kingdom and heroes must find the cure'
        },
        {
            'num': 2,
            'quests': 2,
            'difficulty': 'Hard',
            'playtime': 90,
            'story': 'Ancient ruins hold secrets to a forgotten civilization with powerful artifacts'
        },
        {
            'num': 3,
            'quests': 2,
            'difficulty': 'Easy',
            'playtime': 45,
            'story': 'A dragon has been spotted near the village and the locals need brave adventurers'
        }
    ]

    print("\n" + "="*80)
    print("SEQUENTIAL CAMPAIGN GENERATION")
    print("Creating 3 campaigns ONE AT A TIME")
    print("="*80 + "\n")

    results = []
    for i, campaign in enumerate(campaigns, 1):
        print(f"\n>>> Starting campaign {i} of {len(campaigns)}...\n")
        success = await create_single_campaign(campaign)
        results.append({'num': campaign['num'], 'success': success})

        if i < len(campaigns):
            print(f"\n>>> Waiting 10 seconds before starting next campaign...\n")
            await asyncio.sleep(10)

    # Print summary
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    for result in results:
        status = "✓ SUCCESS" if result['success'] else "✗ FAILED"
        print(f"Campaign {result['num']}: {status}")
    print("="*80 + "\n")

if __name__ == "__main__":
    asyncio.run(main())
