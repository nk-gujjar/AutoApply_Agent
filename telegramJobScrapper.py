import argparse
import asyncio

from modules.core.scrapers.telegram_job_scraper import TelegramJobScraper


async def main() -> None:
    parser = argparse.ArgumentParser(description="Telegram job scraper runner")
    parser.add_argument("--channel", required=True, help="Telegram channel username, with or without @")
    parser.add_argument("--limit", type=int, default=10, help="Number of recent posts to parse")
    args = parser.parse_args()

    scraper = TelegramJobScraper()
    jobs = await scraper.run(channel=args.channel, limit=max(1, args.limit))

    print(f"Parsed {len(jobs)} jobs from @{args.channel.lstrip('@')}")
    for job in jobs:
        print("\n" + "=" * 40)
        print(f"Role:       {job.get('role', 'N/A')}")
        print(f"Company:    {job.get('company', 'N/A')}")
        print(f"Apply Link: {job.get('apply_link', 'N/A')}")
        print(f"Summary:    {job.get('summary', 'N/A')}")


if __name__ == "__main__":
    asyncio.run(main())
