from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parent.parent))

from ai_goods_pipeline.clients.image_client import ImageClient
from ai_goods_pipeline.config import load_settings


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate CLIP rerank scores for Baidu image candidates.",
    )
    parser.add_argument("--title", required=True, help="Target goods title.")
    parser.add_argument("--category-id", type=int, required=True)
    parser.add_argument("--query", default="", help="Optional Baidu query override.")
    parser.add_argument("--count", type=int, default=8, help="How many candidates to inspect.")
    parser.add_argument(
        "--enable-clip-rerank",
        type=int,
        default=1,
        help="Whether to force enable CLIP rerank in this evaluation.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    settings = load_settings()
    client = ImageClient(
        timeout=settings.image_timeout,
        retries=settings.image_retry,
        min_bytes=settings.image_min_bytes,
        allow_gif_as_main=settings.image_allow_gif_as_main,
        enable_bing=False,
        enable_clip_rerank=bool(args.enable_clip_rerank),
        clip_model_name=settings.image_clip_model,
        clip_min_score=settings.image_clip_min_score,
        clip_max_candidates=settings.image_clip_max_candidates,
        clip_category_ids=settings.image_clip_category_ids,
    )
    try:
        query = (args.query or args.title).strip()
        print("=== Runtime Status ===")
        print(json.dumps(client.clip_reranker.runtime_status(), ensure_ascii=False))
        print()

        print("=== Query ===")
        print(query)
        print()

        candidate_urls = client.fetch_baidu_images(query)[: max(1, args.count)]
        print("=== Candidate URLs ===")
        print(f"candidate_count={len(candidate_urls)}")
        for index, url in enumerate(candidate_urls, 1):
            print(f"#{index} {url}")
        print()

        valid_images = client._validate_urls(candidate_urls)  # noqa: SLF001 - evaluation script
        original_urls = [probe.url for probe in valid_images]

        print("=== Original Valid URLs ===")
        if not original_urls:
            print("No valid image URLs found.")
            return 0
        for index, url in enumerate(original_urls, 1):
            print(f"#{index} {url}")
        print()

        rerank_result = client.clip_reranker.rerank_urls(
            title=args.title,
            category_id=args.category_id,
            candidate_urls=original_urls,
        )
        print("=== Rerank Result ===")
        print(json.dumps({"applied": rerank_result.applied, "reason": rerank_result.reason}, ensure_ascii=False))
        print()

        print("=== Ranked URLs ===")
        for index, url in enumerate(rerank_result.ranked_urls, 1):
            score = rerank_result.scores.get(url)
            score_text = f"{score:.4f}" if isinstance(score, float) else "-"
            print(f"#{index} score={score_text} url={url}")
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
