"""
Multi-Agent Entry Point for AutoApply Agent

Client agent routes tasks to specialized agents:
- TelegramScraper
- NaukriScraper
- FetchJobs
- ResumeRewrite
- NaukriApplier
- ExternalApplier

Optional MCP mode routes through an in-process MCP server.
"""

import argparse
import asyncio
import json
import sys
from typing import Any, Dict

from modules.core.config.settings import logger
from modules.multi_agent import ClientAgent


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="AutoApply Multi-Agent System")
    parser.add_argument(
        "--mode",
        choices=[
            "pipeline",
            "query",
            "telegram-scraper",
            "naukri-scraper",
            "fetch-jobs",
            "resume-rewrite",
            "naukri-apply",
            "external-apply",
            "mcp-tools",
            "a2a-cards",
        ],
        default="pipeline",
    )
    parser.add_argument("--query", type=str, default="")
    parser.add_argument("--max-jobs", type=int, default=10)
    parser.add_argument("--channel", type=str, default="")
    parser.add_argument("--mcp", action="store_true", help="Route via MCP server tools")
    parser.add_argument("--include-filtered", action="store_true")
    return parser


async def _run_mode(client: ClientAgent, mode: str, args: argparse.Namespace) -> Dict[str, Any]:
    if mode == "mcp-tools":
        tools = await client.mcp_client.list_tools()
        return {"status": "ok", "tools": tools}

    if mode == "a2a-cards":
        cards: Dict[str, Any] = {}
        for agent_name, a2a_client in client.a2a_clients.items():
            cards[agent_name] = await a2a_client.fetch_agent_card()
        return {"status": "ok", "cards": cards}

    if mode == "pipeline":
        return await client.run_pipeline(max_jobs=args.max_jobs, use_mcp=args.mcp)

    if mode == "query":
        return await client.handle_query(args.query)

    if mode == "telegram-scraper":
        return await client.route(
            "telegram_scraper",
            {
                "channel": args.channel,
                "limit": args.max_jobs,
            },
            use_mcp=args.mcp,
        )

    if mode == "naukri-scraper":
        return await client.route(
            "naukri_scraper",
            {"max_jobs": args.max_jobs},
            use_mcp=args.mcp,
        )

    if mode == "fetch-jobs":
        return await client.route(
            "fetch_jobs",
            {
                "max_jobs": args.max_jobs,
                "include_filtered": args.include_filtered,
            },
            use_mcp=args.mcp,
        )

    if mode == "resume-rewrite":
        return await client.route("resume_rewrite", {}, use_mcp=args.mcp)

    if mode == "naukri-apply":
        return await client.route("naukri_applier", {}, use_mcp=args.mcp)

    if mode == "external-apply":
        return await client.route("external_applier", {"dry_run": False}, use_mcp=args.mcp)

    return {"status": "failed", "error": f"Unknown mode: {mode}"}


async def main() -> int:
    args = _build_parser().parse_args()
    client = ClientAgent()

    try:
        result = await _run_mode(client, args.mode, args)
        print(json.dumps(result, indent=2, default=str))
        return 0
    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
        return 1
    except Exception as exc:
        logger.exception("Unhandled failure in multi-agent runner")
        print(json.dumps({"status": "failed", "error": str(exc)}, indent=2))
        return 1


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    raise SystemExit(asyncio.run(main()))
