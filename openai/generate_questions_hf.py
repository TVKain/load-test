#!/usr/bin/env python3
"""Generate random prompts with an exact token count using a Hugging Face tokenizer.

Example:
    python3 scripts/openai/generate_questions_hf.py \
      --model-id mistralai/Mistral-Large-3-675B-Instruct-2512 \
      --output-file questions/mistral_large3_256t.json \
      --dataset-size 200 \
      --tokens-per-prompt 256 \
      --seed 1337
"""

from __future__ import annotations

import argparse
import importlib
import json
import os
import random
import sys
from multiprocessing import Pool
from pathlib import Path

try:
    from tqdm import tqdm
except ImportError:
    # Fallback if tqdm not installed
    def tqdm(iterable, *args, **kwargs):
        return iterable

# Suppress PyTorch warning — tokenizers work fine without it
os.environ["TOKENIZERS_PARALLELISM"] = "false"


BASE_WORDS = [
    "cloud", "invoice", "billing", "security", "network", "tenant", "cluster", "gateway",
    "region", "latency", "throughput", "request", "response", "payload", "stream", "token",
    "session", "thread", "database", "storage", "compute", "monitor", "metrics", "alert",
    "policy", "runtime", "instance", "service", "deployment", "container", "scheduler", "cache",
    "vector", "search", "rank", "model", "prompt", "context", "dataset", "benchmark",
    "customer", "order", "payment", "receipt", "balance", "report", "account", "access",
    "audit", "trace", "log", "retry", "timeout", "queue", "event", "pipeline",
    "workflow", "plan", "support", "ticket", "portal", "dashboard", "insight", "analysis",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate exact-token random prompts with a HF tokenizer")
    parser.add_argument("--model-id", required=True, help="Hugging Face tokenizer/model id")
    parser.add_argument("--output-file", required=True, help="Output JSON file path")
    parser.add_argument("--dataset-size", type=int, default=100, help="Number of prompts to generate")
    parser.add_argument("--tokens-per-prompt", type=int, default=128, help="Exact token count per prompt")
    parser.add_argument("--seed", type=int, default=1337, help="Random seed")
    parser.add_argument(
        "--fix-mistral-regex",
        action="store_true",
        help="Set fix_mistral_regex=True when loading the tokenizer (recommended for mistralai/*)",
    )
    return parser.parse_args()


def make_snippets(words: list[str]) -> list[str]:
    snippets: list[str] = []

    for w in words:
        snippets.append(w)
        snippets.append(f" {w}")

    snippets.extend([
        ".",
        ",",
        "?",
        "!",
        ":",
        ";",
        " and",
        " or",
        " with",
        " from",
        " for",
        " in",
        " on",
        " by",
        " to",
        " the",
        " a",
        " an",
        " data",
        " system",
        " api",
        " user",
    ])

    # Preserve order while removing duplicates
    deduped: list[str] = []
    seen = set()
    for s in snippets:
        if s not in seen:
            deduped.append(s)
            seen.add(s)
    return deduped


def generate_prompt_exact_tokens(token_len, snippets: list[str], target_tokens: int, rng: random.Random) -> str:
    if target_tokens <= 0:
        raise ValueError("tokens-per-prompt must be > 0")

    max_restarts = 300

    for _ in range(max_restarts):
        text = ""
        current = 0

        while current < target_tokens:
            candidates = snippets[:]
            rng.shuffle(candidates)

            advanced = False
            for piece in candidates:
                candidate = text + piece
                new_len = token_len(candidate)
                delta = new_len - current
                if delta == 1:
                    text = candidate
                    current = new_len
                    advanced = True
                    break

            if not advanced:
                break

        final_text = text.strip()
        if final_text and token_len(final_text) == target_tokens:
            return final_text

    raise RuntimeError(
        f"Failed to generate a prompt with exactly {target_tokens} tokens after {max_restarts} restarts"
    )


# Global tokenizer for worker processes
_global_tokenizer = None
_global_snippets = None


def _init_worker(tokenizer_model_id, load_kwargs):
    """Initialize tokenizer in worker process."""
    global _global_tokenizer
    transformers = importlib.import_module("transformers")
    AutoTokenizer = getattr(transformers, "AutoTokenizer")
    _global_tokenizer = AutoTokenizer.from_pretrained(tokenizer_model_id, **load_kwargs)


def _worker_generate_prompt(args_tuple):
    """Worker function for parallel prompt generation."""
    target_tokens, seed_offset = args_tuple
    
    def token_len(text: str) -> int:
        return len(_global_tokenizer.encode(text, add_special_tokens=False))
    
    rng = random.Random(seed_offset)
    return generate_prompt_exact_tokens(token_len, _global_snippets, target_tokens, rng)


def main() -> int:
    args = parse_args()

    if args.dataset_size <= 0:
        raise ValueError("dataset-size must be > 0")
    if args.tokens_per_prompt <= 0:
        raise ValueError("tokens-per-prompt must be > 0")

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
                "Install with: pip install protobuf transformers sentencepiece",
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

    try:
        transformers = importlib.import_module("transformers")
        AutoTokenizer = getattr(transformers, "AutoTokenizer")
        tokenizer = AutoTokenizer.from_pretrained(args.model_id, **load_kwargs)
    except Exception as e:
        error_msg = str(e)
        if "protobuf" in error_msg.lower():
            print(
                "Error: protobuf library is required but not found.\n"
                "Install with: pip install protobuf",
                file=sys.stderr,
            )
            raise SystemExit(1) from e
        else:
            raise

    def token_len(text: str) -> int:
        return len(tokenizer.encode(text, add_special_tokens=False))

    global _global_snippets
    _global_snippets = make_snippets(BASE_WORDS)

    # Prepare work items for parallel processing
    work_items = [
        (args.tokens_per_prompt, args.seed + i)
        for i in range(args.dataset_size)
    ]

    # Generate prompts in parallel using all available CPU cores
    prompts: list[str] = []
    num_workers = os.cpu_count() or 4
    
    with Pool(
        processes=num_workers,
        initializer=_init_worker,
        initargs=(args.model_id, load_kwargs)
    ) as pool:
        for prompt in tqdm(
            pool.imap_unordered(_worker_generate_prompt, work_items),
            total=args.dataset_size,
            desc="Generating prompts",
            unit="prompt"
        ):
            prompts.append(prompt)

    output_path = Path(args.output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(prompts, ensure_ascii=False, indent=2), encoding="utf-8")

    sample_tokens = token_len(prompts[0]) if prompts else 0
    print(f"Saved: {output_path}")
    print(f"Model tokenizer: {args.model_id}")
    print(f"Mistral regex fix: {'enabled' if args.fix_mistral_regex or args.model_id.startswith('mistralai/') else 'disabled'}")
    print(f"Prompts: {len(prompts)}")
    print(f"Tokens per prompt: {args.tokens_per_prompt}")
    print(f"Sample prompt token count: {sample_tokens}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
