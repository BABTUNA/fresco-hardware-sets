# score the layer 1 methods from layer1.json: page recall and precision over all 20 books
# finder is a fixed decision; tf-idf and embeddings get the global threshold that maximizes their own F1,
# which is generous to them, plus the number of pages they would pass to layer 2 to reach 95% recall
import json, sys
import numpy as np

r = json.load(open(sys.argv[1]))
books = sorted(r)
truth = {b: set(r[b]["truth"]) for b in books}
n_truth = sum(len(t) for t in truth.values())
n_pages = sum(r[b]["n"] for b in books)


def pr(selected):
    tp = sum(len(selected[b] & truth[b]) for b in books)
    sel = sum(len(selected[b]) for b in books)
    return tp / n_truth, tp / max(sel, 1), sel


def by_threshold(key, thr):
    return {b: {i for i, s in enumerate(r[b][key]) if s >= thr} for b in books}


print(f"{n_pages} pages in 20 books, {n_truth} hold sets\n")
print(f"{'method':28s} {'recall':>7s} {'precision':>9s} {'pages passed':>13s}")
rec, prec, sel = pr({b: set(r[b]["finder"]) for b in books})
print(f"{'regex finder (ours)':28s} {rec:7.1%} {prec:9.1%} {sel:13d}")
for key, name in (("tfidf", "tf-idf vs hints"), ("emb", "MiniLM embeddings vs hints")):
    allv = np.array([v for b in books for v in r[b][key]])
    best = None
    for thr in np.quantile(allv, np.linspace(0.5, 0.995, 200)):
        rec, prec, sel = pr(by_threshold(key, thr))
        f1 = 2 * rec * prec / max(rec + prec, 1e-9)
        if best is None or f1 > best[0]:
            best = (f1, rec, prec, sel, thr)
    print(f"{name + ', best F1':28s} {best[1]:7.1%} {best[2]:9.1%} {best[3]:13d}")
    # how many pages to pass to layer 2 to catch 95% of the set pages
    for thr in sorted(set(allv), reverse=True):
        rec, prec, sel = pr(by_threshold(key, thr))
        if rec >= 0.95:
            print(f"{name + ', 95% recall':28s} {rec:7.1%} {prec:9.1%} {sel:13d}")
            break
print("\nper book, pages holding sets missed by each method (recall):")
for b in books:
    f = set(r[b]["finder"])
    emb = np.array(r[b]["emb"]); k = len(truth[b])
    top = set(np.argsort(-emb)[:k].tolist()) if k else set()
    print(f"  {b:11s} truth {len(truth[b]):3d}  finder {len(f & truth[b]) / max(k, 1):5.0%}  embeddings top-k {len(top & truth[b]) / max(k, 1):5.0%}")
