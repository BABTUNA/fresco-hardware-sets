# the one model call per book: sample pages in, layout spec out. plus the repair call when the audit flags
import json, os, re
from pathlib import Path
from .spec import dump, validate_spec

PROMPTS = Path(__file__).parent / "prompts"
MODEL = os.environ.get("HWSETS_MODEL", "claude-sonnet-5-5")


# the n densest schedule pages, the ones with the most row-shaped lines
#   in:  runs [[417, 444]], scores with page 420 at 31 rows and 426 at 29
#   out: [420, 426]
def pick_samples(runs, scores, n=2):
    pages = [p for a, b in runs for p in range(a, b + 1)]
    return sorted(sorted(pages, key=lambda p: scores[p], reverse=True)[:n])


# ANTHROPIC_API_KEY from the environment, or from a .env file in the working directory
def api_key():
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key and os.path.exists(".env"):
        for line in open(".env"):
            if line.startswith("ANTHROPIC_API_KEY="):
                key = line.split("=", 1)[1].strip().strip('"')
    if not key:
        raise SystemExit("ANTHROPIC_API_KEY is not set (environment or .env). Needed only to compile a spec for a new book.")
    return key


# one call, the reply is the spec JSON (with or without a code fence)
def ask_claude(prompt, text):
    import anthropic
    client = anthropic.Anthropic(api_key=api_key())
    msg = client.messages.create(model=MODEL, max_tokens=3000,
                                 messages=[{"role": "user", "content": prompt + "\n\n" + text}])
    reply = msg.content[0].text
    m = re.search(r"\{.*\}", reply, re.S)
    if not m:
        raise ValueError(f"no JSON in the model reply: {reply[:200]}")
    return validate_spec(json.loads(m.group(0)))


# -> (spec, dump), the dump is kept for the repair call
def compile_spec(pdf, runs, scores):
    pages = pick_samples(runs, scores)
    text = dump(pdf, pages)
    prompt = (PROMPTS / "spec.md").read_text()
    return ask_claude(prompt, text), text


# one more call with the spec, what the audit found, and the same sample pages
def repair(spec, flags, text):
    prompt = (PROMPTS / "repair.md").read_text()
    body = "Current spec:\n" + json.dumps(spec, indent=1) + "\n\nAudit flags:\n" + json.dumps(flags, indent=1) + "\n\nSample pages:\n" + text
    return ask_claude(prompt, body)
