# run the section finder over every PDF in the corpus
import os, json, time
from finder import page_scores, runs

out = {}
root = "../data"
for proj in sorted(os.listdir(root)):
    d = os.path.join(root, proj)
    if not os.path.isdir(d):
        continue
    for f in sorted(os.listdir(d)):
        if not f.lower().endswith(".pdf"):
            continue
        t = time.time()
        s, v = page_scores(os.path.join(d, f))
        r = runs(s, v)
        out[f"{proj}/{f}"] = {"pages": len(s), "runs": r, "rows": [sum(s[a:b + 1]) for a, b in r], "secs": round(time.time() - t, 1)}
        print(f"{proj[:26]:26s} {f[:44]:44s} {len(s):5d}p {time.time()-t:5.1f}s runs={r} rows={out[f'{proj}/{f}']['rows']}", flush=True)
json.dump(out, open("eval/finder.json", "w"), indent=1)
