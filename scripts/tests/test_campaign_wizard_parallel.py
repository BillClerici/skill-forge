"""
Playwright automation script for Campaign Design Wizard - Parallel Version
Creates campaigns with configurable parameters
"""

import asyncio
from playwright.async_api import async_playwright
import time
import sys
import argparse

# Fix encoding for Windows console
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

async def run_campaign_wizard(campaign_num, num_quests, difficulty, playtime, story_seed):
    async with async_playwright() as p:
        # Launch browser
        browser = await p.chromium.launch(headless=False, slow_mo=300)
        context = await browser.new_context()
        page = await context.new_page()

        print(f"\n[Campaign {campaign_num}] ====================================")
        print(f"[Campaign {campaign_num}] Starting with: {num_quests} quests, {difficulty} difficulty, {playtime}min playtime")
        print(f"[Campaign {campaign_num}] ====================================\n")

        try:
            # Navigate to campaigns page
            print(f"[Campaign {campaign_num}] Navigating to Campaigns page...")
            await page.goto('http://localhost:8000/campaigns/', wait_until='domcontentloaded')
            await page.wait_for_timeout(2000)

            # Click Campaign Design Wizard button
            print(f"[Campaign {campaign_num}] Clicking 'Campaign Design Wizard' button...")
            wizard_button = page.get_by_text('Campaign Design Wizard', exact=False).first
            await wizard_button.click()
            await page.wait_for_timeout(3000)

            # Wait for wizard form
            await page.wait_for_selector('#wizard-form', timeout=10000)

            # Step 1: Campaign Name & Universe
            print(f"[Campaign {campaign_num}] STEP 1: Entering campaign details...")
            campaign_name = f"Campaign {campaign_num} - {difficulty} {num_quests}Q - {int(time.time())}"
            campaign_input = page.locator('#campaign_name')
            await campaign_input.wait_for(state='visible', timeout=10000)
            await campaign_input.fill(campaign_name)

            # Select universe
            universe_label = page.locator('.universe-card').first
            await universe_label.click()
            await page.click('#next-btn')
            await page.wait_for_timeout(2000)

            # Step 2: World Selection
            print(f"[Campaign {campaign_num}] STEP 2: Selecting world...")
            await page.wait_for_selector('.world-card', timeout=10000)
            world_label = page.locator('.world-card').first
            await world_label.click()
            await page.click('#next-btn')
            await page.wait_for_timeout(2000)

            # Step 3: Region Selection
            print(f"[Campaign {campaign_num}] STEP 3: Selecting region...")
            entire_world_label = page.locator('.region-card').first
            await entire_world_label.click()
            await page.click('#next-btn')
            await page.wait_for_timeout(2000)

            # Step 4: Story Idea
            print(f"[Campaign {campaign_num}] STEP 4: Adding story idea...")
            story_idea = f"{story_seed} - Variant {campaign_num}"
            await page.fill('#user_story_idea', story_idea)
            await page.click('#generate-stories-btn')
            await page.wait_for_selector('#loading-overlay', state='visible', timeout=5000)

            # Step 5: Story Selection
            print(f"[Campaign {campaign_num}] STEP 5: Waiting for story generation (up to 5 min)...")
            await page.wait_for_selector('#loading-overlay', state='hidden', timeout=300000)  # 5 minutes
            await page.wait_for_selector('.story-idea-card', timeout=10000)

            story_label = page.locator('.story-idea-card').first
            await story_label.click()
            await page.click('#next-btn')
            await page.wait_for_timeout(2000)

            # Wait for campaign core
            print(f"[Campaign {campaign_num}] STEP 6: Waiting for campaign core (up to 5 min)...")
            await page.wait_for_selector('#loading-overlay', state='visible', timeout=5000)
            await page.wait_for_selector('#loading-overlay', state='hidden', timeout=300000)  # 5 minutes
            await page.wait_for_timeout(2000)
            await page.click('#next-btn')
            await page.wait_for_timeout(2000)

            # Step 7: Quest Settings
            print(f"[Campaign {campaign_num}] STEP 7: Configuring quests...")
            quest_slider = page.locator('#num_quests')
            await quest_slider.evaluate(f'el => el.value = {num_quests}')
            await quest_slider.dispatch_event('input')

            await page.fill('#quest_playtime_minutes', str(playtime))
            await page.evaluate('document.getElementById("generate_images_quests").checked = false')

            await page.click('#next-btn')
            await page.wait_for_timeout(2000)

            # Step 8: Quest Generation
            print(f"[Campaign {campaign_num}] STEP 8: Waiting for quest generation (up to 10 min)...")
            await page.wait_for_selector('#loading-overlay', state='visible', timeout=5000)
            await page.wait_for_selector('#loading-overlay', state='hidden', timeout=600000)  # 10 minutes
            await page.wait_for_timeout(2000)
            await page.click('#next-btn')
            await page.wait_for_timeout(2000)

            # Step 9: Place Generation
            print(f"[Campaign {campaign_num}] STEP 9: Waiting for place generation (up to 10 min)...")
            await page.wait_for_selector('#loading-overlay', state='visible', timeout=5000)
            await page.wait_for_selector('#loading-overlay', state='hidden', timeout=600000)  # 10 minutes
            await page.wait_for_timeout(2000)
            await page.click('#next-btn')
            await page.wait_for_timeout(2000)

            # Step 10: Scene Generation
            print(f"[Campaign {campaign_num}] STEP 10: Waiting for scene generation (up to 15 min)...")
            await page.wait_for_selector('#loading-overlay', state='visible', timeout=5000)
            await page.wait_for_selector('#loading-overlay', state='hidden', timeout=900000)  # 15 minutes
            await page.wait_for_timeout(2000)
            await page.click('#next-btn')
            await page.wait_for_timeout(2000)

            # Step 11: Finalization
            print(f"[Campaign {campaign_num}] STEP 11: Finalizing campaign...")
            await page.click('#finalize-btn')
            await page.wait_for_selector('#loading-overlay', state='visible', timeout=5000)
            await page.wait_for_selector('#loading-overlay', state='hidden', timeout=300000)  # 5 minutes

            print(f"[Campaign {campaign_num}] ✓✓✓ CAMPAIGN CREATED SUCCESSFULLY! ✓✓✓")

            # Wait for redirect to campaign detail page
            await page.wait_for_timeout(5000)

        except Exception as e:
            print(f"[Campaign {campaign_num}] ✗ ERROR: {str(e)}")
            error_screenshot = f"campaign_{campaign_num}_error_{int(time.time())}.png"
            await page.screenshot(path=error_screenshot)
            print(f"[Campaign {campaign_num}] Error screenshot: {error_screenshot}")

        finally:
            # Keep browser open briefly
            print(f"[Campaign {campaign_num}] Closing browser in 5 seconds...")
            await page.wait_for_timeout(5000)
            await browser.close()

async def run_parallel_campaigns():
    # Define 3 different campaign configurations
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

    # Run all 3 campaigns in parallel
    tasks = [
        run_campaign_wizard(
            c['num'],
            c['quests'],
            c['difficulty'],
            c['playtime'],
            c['story']
        )
        for c in campaigns
    ]

    await asyncio.gather(*tasks)

if __name__ == "__main__":
    print("\n" + "="*80)
    print("PARALLEL CAMPAIGN GENERATION TEST")
    print("Creating 3 campaigns simultaneously with different parameters")
    print("="*80 + "\n")

    asyncio.run(run_parallel_campaigns())

    print("\n" + "="*80)
    print("ALL CAMPAIGNS SUBMITTED!")
    print("Campaigns are generating in the background via the campaign-factory service")
    print("="*80 + "\n")
