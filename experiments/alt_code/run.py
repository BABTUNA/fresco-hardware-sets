# run each book's llm-written parser over its schedule pages and write scorer-format results
import json, os, sys, importlib.util, traceback, multiprocessing as mp
import pdfplumber
from lines import page_lines

D = "../data/"


def load_pages(book, plan):
    pdf = pdfplumber.open(D + plan[book]["file"])
    keep = set()
    for a, b in plan[book]["runs"]:
        keep.update(range(max(0, a - 2), min(len(pdf.pages), b + 3)))
    pages = []
    for p in sorted(keep):
        ls = page_lines(pdf.pages[p])
        pages.append({"page": p, "lines": [{k: l[k] for k in ("text", "x0", "x1", "top", "bottom")} |
                                           {"words": [{k: w[k] for k in ("text", "x0", "x1", "top", "bottom")} for w in l["words"]]} for l in ls]})
    return pages


def worker(book, pages, q):
    try:
        spec = importlib.util.spec_from_file_location(book, f"alt_code/parsers/{book}.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        q.put(("ok", mod.parse(pages)))
    except Exception:
        q.put(("error", traceback.format_exc()[-1500:]))


def main(books):
    plan = json.load(open("eval/e2e_plan.json"))
    os.makedirs("out_code", exist_ok=True)
    for book in books or plan:
        if not os.path.exists(f"alt_code/parsers/{book}.py"):
            print(f"{book}: no parser"); continue
        pages = load_pages(book, plan)
        q = mp.Queue()
        pr = mp.Process(target=worker, args=(book, pages, q))
        pr.start()
        # read before join: a large result blocks the child until the parent drains the queue
        try:
            status, res = q.get(timeout=300)
        except Exception:
            status, res = "error", "timeout after 300s"
        pr.join(5)
        if pr.is_alive():
            pr.kill()
        if status == "error":
            print(f"{book}: ERROR {res.splitlines()[-1] if res else ''}")
            open(f"alt_code/parsers/{book}.error.txt", "w").write(res)
            json.dump({"sets": []}, open(f"out_code/{book}.json", "w"))
            continue
        sets = []
        for s in res:
            comps = [dict(c) for c in s.get("components", [])]
            pages_of = sorted({c.get("page") for c in comps if c.get("page") is not None} | {s.get("first_page")} - {None})
            for c in comps:
                if not isinstance(c.get("qty"), int):
                    c["qty"] = None
            sets.append({"set_number": str(s.get("set_number")), "status": s.get("status") or "active",
                         "location": [{"page": p} for p in pages_of], "components": comps})
        json.dump({"sets": sets}, open(f"out_code/{book}.json", "w"))
        print(f"{book}: {len(sets)} sets, {sum(len(s['components']) for s in sets)} components", flush=True)


if __name__ == "__main__":
    main(sys.argv[1:])
