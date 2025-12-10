import asyncio
import csv
import re
from crawlee.crawlers import (
    PlaywrightCrawler,
    PlaywrightCrawlingContext,
    PlaywrightPreNavCrawlingContext,
)

# Global variables to hold the crawler instance and file state (if needed)
global_crawler = None

async def extract_end_of_over_data(end_of_over_div):
    over_stats = {"batsmen": "", "bowler_stats": ""}
    try:
        batsmen_stats = end_of_over_div.locator(
            "xpath=.//div[contains(@class, 'ds-w-1/2') and contains(@class, 'ds-pl-')]//div[contains(@class, 'ds-flex') and contains(@class, 'ds-justify-between')]"
        )
        batsmen_info = []
        batsmen_count = await batsmen_stats.count()
        for j in range(batsmen_count):
            batsman_name = (await batsmen_stats.nth(j)
                .locator("span:nth-child(1)")
                .inner_text()).strip()
            batsman_stat = (await batsmen_stats.nth(j)
                .locator("span:nth-child(2)")
                .inner_text()).strip()
            batsmen_info.append(f"{batsman_name}: {batsman_stat}")
        over_stats["batsmen"] = ", ".join(batsmen_info)

        bowler_stats = end_of_over_div.locator(
            "xpath=.//div[contains(@class, 'ds-border-l')]//div[contains(@class, 'ds-flex') and contains(@class, 'ds-justify-between')]"
        )
        bowler_info = []
        bowler_count = await bowler_stats.count()
        for k in range(bowler_count):
            bowler_name = (await bowler_stats.nth(k)
                .locator("xpath=.//span[contains(@class, 'ds-mt-px')]")
                .inner_text()).strip()
            bowler_performance = (await bowler_stats.nth(k)
                .locator("span:nth-child(2)")
                .inner_text()).strip()
            bowler_info.append(f"{bowler_name}: {bowler_performance}")
        over_stats["bowler_stats"] = ", ".join(bowler_info)
    except Exception as e:
        print("Error in extract_end_of_over_data:", e)
    
    return over_stats

async def scrape_innings(page, innings_label):
    print(f"Scraping commentary for {innings_label} innings...")
    
    # Introduce a maximum scroll iteration limit.
    max_scroll_iterations = 50
    scroll_iterations = 0
    retry_scroll_up = 0
    while scroll_iterations < max_scroll_iterations:
        commentary_locator = page.locator(
            "xpath=//div[contains(@class, 'lg:hover:ds-bg-ui-fill-translucent ds-hover-parent ds-relative')]"
        )
        previous_div_count = await commentary_locator.count()
        await page.mouse.wheel(0, 5000)
        await asyncio.sleep(1)
        new_div_count = await commentary_locator.count()
        if new_div_count == previous_div_count:
            retry_scroll_up += 1
            for _ in range(3):
                await page.mouse.wheel(0, -1000)
                await asyncio.sleep(1)
            await page.mouse.wheel(0, 1000)
            await asyncio.sleep(1)
            if retry_scroll_up >= 10:
                print("No more new commentary divs found.")
                break
        else:
            retry_scroll_up = 0
        scroll_iterations += 1

    # Initialize variables for over-level metrics.
    over_data = []
    current_over = None
    current_over_metrics = {
        "over_number": None,
        "total_runs": 0,
        "boundaries": 0,
        "dot_balls": 0,
        "wickets": 0,
        "extras": 0,
        "batsmen": "",
        "bowler_stats": ""
    }
    commentary_divs = page.locator(
        "xpath=//div[contains(@class, 'lg:hover:ds-bg-ui-fill-translucent ds-hover-parent ds-relative')]"
    )
    end_of_over_divs = page.locator(
        "xpath=//div[contains(@class, 'ds-text-tight-s ds-font-regular')]"
    )
    end_over_index = 0
    num_commentary = await commentary_divs.count()

    for i in range(num_commentary):
        try:
            div = commentary_divs.nth(i)
            ball_number = (await div.locator(
                "xpath=//span[contains(@class, 'ds-text-tight-s') and contains(@class, 'ds-font-regular') and contains(@class, 'ds-text-typo-mid1')]"
            ).inner_text()).strip()
            runs_or_event = (await div.locator(
                "xpath=.//div[contains(@class, 'ds-text-tight-m') and contains(@class, 'ds-font-bold')]/span"
            ).inner_text()).strip()
            short_commentary = await div.locator(
                "xpath=.//div[contains(@class, 'ds-leading-')]"
            ).evaluate_all("nodes => nodes.map(node => node.textContent.trim()).join(' ')")
            _ = (await div.locator("xpath=.//p[contains(@class, 'ci-html-content')]").inner_text()).strip()

            ball_over = int(float(ball_number))
            if current_over is not None and ball_over != current_over:
                try:
                    if await end_of_over_divs.count() > end_over_index:
                        end_of_over_div = end_of_over_divs.nth(end_over_index)
                        end_over_index += 1
                        extra_stats = await extract_end_of_over_data(end_of_over_div)
                        current_over_metrics.update(extra_stats)
                    else:
                        print(f"No end-of-over div found for over {current_over}")
                except Exception as e:
                    print(f"Error processing end-of-over stats for over {current_over}: {e}")
                over_data.append(current_over_metrics)
                current_over_metrics = {
                    "over_number": ball_over,
                    "total_runs": 0,
                    "boundaries": 0,
                    "dot_balls": 0,
                    "wickets": 0,
                    "extras": 0,
                    "batsmen": "",
                    "bowler_stats": ""
                }
            current_over = ball_over
            current_over_metrics["over_number"] = current_over

            if runs_or_event.isdigit():
                runs = int(runs_or_event)
                current_over_metrics["total_runs"] += runs
                if runs in [4, 6]:
                    current_over_metrics["boundaries"] += 1
            elif runs_or_event == "W":
                current_over_metrics["wickets"] += 1
            if runs_or_event == "•":
                current_over_metrics["dot_balls"] += 1
            if "wide" in short_commentary or "no ball" in short_commentary or "leg bye" in short_commentary:
                current_over_metrics["extras"] += 1
                match = re.match(r'(\d+)', runs_or_event)
                runs = int(match.group(1)) if match else 0
                current_over_metrics["total_runs"] += runs

        except Exception as e:
            print(f"Error processing ball data at index {i}: {e}")

    if current_over is not None:
        try:
            if await end_of_over_divs.count() > end_over_index:
                end_of_over_div = end_of_over_divs.nth(end_over_index)
                extra_stats = await extract_end_of_over_data(end_of_over_div)
                current_over_metrics.update(extra_stats)
            else:
                print(f"No end-of-over div found for over {current_over_metrics['over_number']}")
        except Exception as e:
            print(f"Error processing end-of-over stats for final over {current_over_metrics['over_number']}: {e}")
        over_data.append(current_over_metrics)

    filename = f"{innings_label}_innings_summary.csv"
    with open(filename, "w", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "over_number", "total_runs", "boundaries", 
                "dot_balls", "wickets", "extras", "batsmen", "bowler_stats"
            ]
        )
        writer.writeheader()
        writer.writerows(over_data)
    print(f"Data saved successfully to {filename}.")

async def select_other_innings(page):
    print("Switching innings...")
    dropdown_button_selector = 'div.ds-flex.ds-items-center.ds-cursor-pointer'
    await page.wait_for_selector(dropdown_button_selector)
    await page.click(dropdown_button_selector)
    await asyncio.sleep(1)
    li_locator = page.locator("xpath=//ul[contains(@class, 'ds-flex')]/li")
    li_count = await li_locator.count()
    target_option = None
    for i in range(li_count):
        li_element = li_locator.nth(i)
        inner_div = li_element.locator("div.ds-cursor-pointer")
        class_attr = await inner_div.get_attribute("class") or ""
        if "ds-font-bold" not in class_attr:
            target_option = inner_div
            break
    if target_option is not None:
        await target_option.click()
        await asyncio.sleep(2)
        print("Other innings selected.")
    else:
        print("No alternative innings option found.")

async def handle_page(context: PlaywrightCrawlingContext) -> None:
    await asyncio.sleep(3)
    await scrape_innings(context.page, "Default")
    await select_other_innings(context.page)
    await asyncio.sleep(3)
    await scrape_innings(context.page, "Other")
    # After finishing both innings, close the page and stop the crawler.
    await context.page.close()
    await global_crawler.stop("Job complete; stopping crawler.")

async def main():
    global global_crawler
    # Configure the crawler to process only one request.
    crawler = PlaywrightCrawler(
        headless=False,
        browser_type="chromium",
        max_requests_per_crawl=1
    )
    global_crawler = crawler  # store for later use

    @crawler.pre_navigation_hook
    async def set_user_agent(context: PlaywrightPreNavCrawlingContext) -> None:
        await context.page.set_extra_http_headers({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/110.0.0.0 Safari/537.36"
            )
        })

    @crawler.router.default_handler
    async def default_handler(context: PlaywrightCrawlingContext) -> None:
        await handle_page(context)
    
    start_url = (
        "https://www.espncricinfo.com/series/ipl-2020-21-1210595/"
        "mumbai-indians-vs-chennai-super-kings-1st-match-1216492/ball-by-ball-commentary"
    )
    await crawler.run([start_url])

if __name__ == "__main__":
    asyncio.run(main())
