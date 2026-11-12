"""Conversation test: talk to the LLM like a customer, over two (or more) turns.

Turn 1 asks for the cabinet (outer or inner sizes, door arrangement, sink, ...). The model answers with
a CadQuery file. Turn 2 asks the SAME conversation for changes; the model answers with the whole
updated file. Every turn's code is saved so each stage can be checked.

usage: python experiment/generate_chat.py [--limit N] [--only c01,c02] [--model MODEL] [--workers 6]
Needs ANTHROPIC_API_KEY. Writes <out-dir>/<id>_t<k>.py, <id>_t<k>.raw.txt and <id>.chat.md.
"""

import argparse
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from generate import DEFAULT_MODEL, ROOT, extract_code  # noqa: E402


def talk(client, model, system, conv, out_dir):
    messages, log = [], [f"# {conv['id']}", ""]
    t_all = time.time()
    for k, turn in enumerate(conv["turns"], start=1):
        messages.append({"role": "user", "content": turn})
        for attempt in range(4):
            try:
                msg = client.messages.create(model=model, max_tokens=12000, system=system, messages=messages)
                break
            except Exception as e:  # noqa: BLE001  (rate limit / overload: wait and retry)
                if attempt == 3:
                    raise
                print(f"{conv['id']} turn {k}: {type(e).__name__}, retrying", flush=True)
                time.sleep(20 * (attempt + 1))
        text = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
        messages.append({"role": "assistant", "content": text})
        stem = os.path.join(out_dir, f"{conv['id']}_t{k}")
        open(stem + ".raw.txt", "w", encoding="utf-8").write(text)
        open(stem + ".py", "w", encoding="utf-8").write(extract_code(text))
        log += [f"## Turn {k}", "", f"**Customer:** {turn}", "",
                f"**Model:** `{os.path.basename(stem)}.py` ({msg.usage.output_tokens} output tokens)", ""]
    open(os.path.join(out_dir, f"{conv['id']}.chat.md"), "w", encoding="utf-8").write("\n".join(log))
    return f"{conv['id']}: {len(conv['turns'])} turns, {time.time() - t_all:.0f}s"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--only", default="")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--conversations", default="experiment/conversations.json")
    ap.add_argument("--out-dir", default="generated_chat")
    ap.add_argument("--workers", type=int, default=6)
    args = ap.parse_args()

    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("ANTHROPIC_API_KEY is not set (add it as a repository secret).")

    import anthropic

    client = anthropic.Anthropic()
    system = open(os.path.join(ROOT, "prompts", "system.md"), encoding="utf-8").read()
    convs = json.load(open(os.path.join(ROOT, args.conversations), encoding="utf-8"))
    if args.only:
        keep = set(args.only.split(","))
        convs = [c for c in convs if c["id"] in keep]
    if args.limit:
        convs = convs[: args.limit]
    out_dir = os.path.join(ROOT, args.out_dir)
    os.makedirs(out_dir, exist_ok=True)

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futs = {pool.submit(talk, client, args.model, system, c, out_dir): c["id"] for c in convs}
        for f in as_completed(futs):
            try:
                print(f.result(), flush=True)
            except Exception as e:  # noqa: BLE001
                print(f"{futs[f]}: FAILED {type(e).__name__}: {e}", flush=True)


if __name__ == "__main__":
    main()
