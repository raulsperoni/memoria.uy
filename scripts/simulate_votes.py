"""
Simulate many unique voters hitting memoria.uy's vote endpoint.

For each simulated user we create a fresh session (new cookies), fetch the
timeline to get a CSRF token, and then post a number of votes to /vote/<id>/.
This is useful to seed clustering with lots of votes quickly.
"""

from __future__ import annotations

import argparse
import random
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Iterable, List

import requests

NEWS_ID_RE = re.compile(r'id="noticia-(\d+)"')


def fetch_noticia_ids(base_url: str) -> List[int]:
    """Grab noticia IDs from the public timeline page."""
    resp = requests.get(f"{base_url}/", timeout=15)
    resp.raise_for_status()
    ids = {int(match) for match in NEWS_ID_RE.findall(resp.text)}
    if not ids:
        raise RuntimeError("No noticia IDs found on the timeline page")
    return sorted(ids)


def simulate_user(
    user_idx: int,
    base_url: str,
    noticia_ids: Iterable[int],
    votes_per_user: int,
    opinion_weights: tuple[float, float, float],
    delay_range: tuple[float, float],
) -> tuple[int, int]:
    """
    Cast votes as a single simulated user.

    Returns (success_count, failure_count).
    """
    session = requests.Session()
    session.headers.update({"User-Agent": f"MemoriaVoteLoadTest/{user_idx}"})

    # Prime session + CSRF cookie
    resp = session.get(f"{base_url}/", timeout=10)
    resp.raise_for_status()
    csrf = session.cookies.get("csrftoken")
    if not csrf:
        raise RuntimeError("CSRF token not found after initial GET")

    success = 0
    failure = 0

    for _ in range(votes_per_user):
        noticia_id = random.choice(list(noticia_ids))
        opinion = random.choices(
            population=["buena", "mala", "neutral"],
            weights=opinion_weights,
        )[0]

        try:
            vote_resp = session.post(
                f"{base_url}/vote/{noticia_id}/",
                data={"opinion": opinion, "on_nuevas_filter": "false"},
                headers={
                    "Referer": f"{base_url}/",
                    "X-CSRFToken": csrf,
                },
                timeout=10,
            )
            if vote_resp.status_code in (200, 201):
                success += 1
            else:
                failure += 1
        except Exception:
            failure += 1

        time.sleep(random.uniform(*delay_range))

    return success, failure


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Blast memoria.uy with synthetic votes to test clustering."
    )
    parser.add_argument("--base-url", default="https://memoria.uy", help="Site root")
    parser.add_argument("--users", type=int, default=50, help="Number of simulated users")
    parser.add_argument(
        "--votes-per-user",
        type=int,
        default=5,
        help="Votes each simulated user will send",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=10,
        help="Max concurrent simulated users",
    )
    parser.add_argument(
        "--good-weight",
        type=float,
        default=0.45,
        help="Weight for 'buena' votes (0-1)",
    )
    parser.add_argument(
        "--bad-weight",
        type=float,
        default=0.35,
        help="Weight for 'mala' votes (0-1)",
    )
    parser.add_argument(
        "--neutral-weight",
        type=float,
        default=0.20,
        help="Weight for 'neutral' votes (0-1)",
    )
    parser.add_argument(
        "--min-delay",
        type=float,
        default=0.1,
        help="Minimum delay (seconds) between votes per user",
    )
    parser.add_argument(
        "--max-delay",
        type=float,
        default=0.5,
        help="Maximum delay (seconds) between votes per user",
    )

    args = parser.parse_args()

    opinion_weights = (args.good_weight, args.bad_weight, args.neutral_weight)
    delay_range = (args.min_delay, args.max_delay)

    print(f"[setup] Fetching noticia IDs from {args.base_url} ...")
    noticia_ids = fetch_noticia_ids(args.base_url)
    print(f"[setup] Found {len(noticia_ids)} noticias: {noticia_ids[:10]}{' ...' if len(noticia_ids) > 10 else ''}")

    print(
        f"[run] Starting load: users={args.users}, votes/user={args.votes_per_user}, "
        f"concurrency={args.concurrency}"
    )

    total_success = 0
    total_failure = 0

    with ThreadPoolExecutor(max_workers=args.concurrency) as executor:
        futures = [
            executor.submit(
                simulate_user,
                idx,
                args.base_url.rstrip("/"),
                noticia_ids,
                args.votes_per_user,
                opinion_weights,
                delay_range,
            )
            for idx in range(args.users)
        ]

        for future in as_completed(futures):
            success, failure = future.result()
            total_success += success
            total_failure += failure

    print(
        f"[done] Votes sent: ok={total_success}, failed={total_failure}, "
        f"total={total_success + total_failure}"
    )


if __name__ == "__main__":
    main()
