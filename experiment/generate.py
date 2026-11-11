"""Ask the LLM to write a parametric cabinet model for each sentence.

usage: python experiment/generate.py [--limit N] [--model MODEL]
Needs ANTHROPIC_API_KEY. Writes generated/<id>.py and generated/<id>.raw.txt.
"""

import argparse
import csv
import os
import re
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_MODEL = os.environ.get("GEN_MODEL", "claude-sonnet-5-5")


def extract_code(text: str) -> str:
    m = re.search(r"```(?:python)?\s*\n(.*?)```", text, re.S)
    return (m.group(1) if m else text).strip() + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--model", default=DEFAULT_MODEL)
    args = ap.parse_args()

    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("ANTHROPIC_API_KEY is not set (add it as a repository secret).")

    import anthropic

    client = anthropic.Anthropic()
    system = open(os.path.join(ROOT, "prompts", "system.md"), encoding="utf-8").read()
    rows = list(csv.DictReader(open(os.path.join(ROOT, "experiment", "sentences.csv"), encoding="utf-8")))
    if args.limit:
        rows = rows[: args.limit]
    out_dir = os.path.join(ROOT, "generated")
    os.makedirs(out_dir, exist_ok=True)

    for row in rows:
        t0 = time.time()
        msg = client.messages.create(
            model=args.model,
            max_tokens=8000,
            system=system,
            messages=[{"role": "user", "content": row["sentence"]}],
        )
        text = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
        open(os.path.join(out_dir, f"{row['id']}.raw.txt"), "w", encoding="utf-8").write(text)
        open(os.path.join(out_dir, f"{row['id']}.py"), "w", encoding="utf-8").write(extract_code(text))
        print(f"{row['id']}: {time.time() - t0:.1f}s, {msg.usage.output_tokens} output tokens")


if __name__ == "__main__":
    main()
