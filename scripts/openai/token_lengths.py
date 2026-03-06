#!/usr/bin/env python3
"""Compute token length for each entry in a questions JSON file.

Input format:
- A JSON array of strings, e.g. questions/my_questions.json

Examples:
- HF tokenizer (recommended for model-accurate counts):
  python3 scripts/openai/token_lengths.py \
    --questions-file questions/mistral_large3_256t.json \
    --model-id mistralai/Mistral-Large-3-675B-Instruct-2512 \
    --fix-mistral-regex

- Simple local tokenizer:
  python3 scripts/openai/token_lengths.py \
    --questions-file questions/cloudcix.json \
    --tokenizer whitespace
"""

from __future__ import annotations

import argparse
import importlib
import json
import os
import re
import statistics
import sys
from pathlib import Path
from typing import Callable

# Suppress PyTorch warning — tokenizers work fine without it
os.environ["TOKENIZERS_PARALLELISM"] = "false"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Report token length of each question in a JSON dataset")
    parser.add_argument("--questions-file", required=True, help="Path to JSON array of question strings")
    parser.add_argument(
        "--tokenizer",
        choices=["whitespace", "wordpunct", "hf"],
        default="hf",
        help="Tokenizer mode: hf (default), whitespace, or wordpunct",
    )
    parser.add_argument("--model-id", help="Hugging Face tokenizer/model id (required when --tokenizer=hf)")
    parser.add_argument(
        "--fix-mistral-regex",
        action="store_true",
        help="Set fix_mistral_regex=True when loading HF tokenizer",
    )
    parser.add_argument(
        "--show-text",
        action="store_true",
        help="Print question text along with token lengths",
    )
    parser.add_argument(
        "--json-output",
        help="Optional output path for machine-readable results (JSON)",
    )
    return parser.parse_args()


def build_counter(args: argparse.Namespace) -> tuple[str, Callable[[str], int]]:
    if args.tokenizer == "whitespace":
        return "whitespace", lambda text: len(text.strip().split()) if text.strip() else 0

    if args.tokenizer == "wordpunct":
        pattern = re.compile(r"[A-Za-z0-9_]+|[^\sA-Za-z0-9_]")
        return "wordpunct", lambda text: len(pattern.findall(text or ""))

    # HF mode
    if not args.model_id:
        raise ValueError("--model-id is required when --tokenizer=hf")

    try:
        transformers = importlib.import_module("transformers")
        AutoTokenizer = getattr(transformers, "AutoTokenizer")
    except ImportError as exc:
        if "protobuf" in str(exc).lower():
            print(
                "Missing dependency: protobuf.\n"
                "Install with: pip install protobuf transformers sentencepiece",
                file=sys.stderr,
            )
        else:
            print(
                "Missing dependency: transformers (and likely tokenizers/sentencepiece).\n"
                "Install with: pip install transformers sentencepiece",
                file=sys.stderr,
            )
        raise SystemExit(1) from exc
    except Exception as exc:
        print(
            "Error loading transformers: " + str(exc),
            file=sys.stderr,
        )
        raise SystemExit(1) from exc

    load_kwargs = {"use_fast": True}
    if args.fix_mistral_regex or args.model_id.startswith("mistralai/"):
        load_kwargs["trust_remote_code"] = True

    try:
        tokenizer = AutoTokenizer.from_pretrained(args.model_id, **load_kwargs)
    except Exception as e:
        error_msg = str(e)
        if "fix_mistral_regex" in error_msg or "got multiple values" in error_msg:
            print(
                "Warning: conflict with Mistral regex handling; retrying without trust_remote_code.",
                file=sys.stderr,
            )
            load_kwargs.pop("trust_remote_code", None)
            tokenizer = AutoTokenizer.from_pretrained(args.model_id, **load_kwargs)
        else:
            raise

    label = f"hf:{args.model_id}"
    return label, lambda text: len(tokenizer.encode(text, add_special_tokens=False))


def main() -> int:
    args = parse_args()

    questions_path = Path(args.questions_file)
    if not questions_path.exists():
        raise FileNotFoundError(f"Questions file not found: {questions_path}")

    raw = json.loads(questions_path.read_text(encoding="utf-8"))
    if not isinstance(raw, list) or not raw:
        raise ValueError("Questions file must be a non-empty JSON array")

    for i, item in enumerate(raw):
        if not isinstance(item, str):
            raise ValueError(f"All entries must be strings. Entry {i} has type {type(item).__name__}")

    tokenizer_label, count_tokens = build_counter(args)

    rows: list[dict] = []
    for idx, text in enumerate(raw):
        rows.append(
            {
                "index": idx,
                "chars": len(text),
                "tokens": count_tokens(text),
                "text": text,
            }
        )

    token_values = [row["tokens"] for row in rows]
    count = len(token_values)
    avg = sum(token_values) / count
    p50 = statistics.median(token_values)
    min_tokens = min(token_values)
    max_tokens = max(token_values)

    print(f"Questions file: {questions_path}")
    print(f"Tokenizer: {tokenizer_label}")
    print(f"Entries: {count}")
    print(f"min={min_tokens}  p50={p50}  avg={avg:.2f}  max={max_tokens}")
    print()

    for row in rows:
        if args.show_text:
            print(f"[{row['index']:>4}] tokens={row['tokens']:>6} chars={row['chars']:>6} text={row['text']}")
        else:
            print(f"[{row['index']:>4}] tokens={row['tokens']:>6} chars={row['chars']:>6}")

    if args.json_output:
        out_path = Path(args.json_output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_payload = {
            "questions_file": str(questions_path),
            "tokenizer": tokenizer_label,
            "summary": {
                "count": count,
                "min": min_tokens,
                "p50": p50,
                "avg": avg,
                "max": max_tokens,
            },
            "entries": rows,
        }
        out_path.write_text(json.dumps(out_payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print()
        print(f"Saved JSON report: {out_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
