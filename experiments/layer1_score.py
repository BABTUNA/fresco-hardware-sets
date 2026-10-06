# layer 1 comparison: which pages hold hardware sets?
# truth = pages where the end-to-end pipeline placed a set or a component. negatives = every other page.
# methods: our regex finder (row shapes + hardware words), tf-idf similarity to hint phrases, embedding similarity to the same hints
import json, re, time, sys, collections
import numpy as np
import pypdfium2 as pdfium
from sklearn.feature_extraction.text import TfidfVectorizer
from sentence_transformers import SentenceTransformer
sys.path.insert(0, ".")
from finder import page_scores, runs
E = "./"
D = "../data/"
plan = json.load(open(E + "eval/e2e_plan.json"))
HINTS = ["hardware set group schedule", "hinge closer lockset exit device cylinder threshold kick plate",
         "quantity description catalog number finish manufacturer", "EA hinge 5BB1 4.5 x 4.5 626 IVE",
         "provide each door with the following"]
model = SentenceTransformer("all-MiniLM-L6-v2")
hint_vec = model.encode(HINTS, normalize_embeddings=True).mean(axis=0)
hint_vec /= np.linalg.norm(hint_vec)
results = {}
for book, p in plan.items():
    t0 = time.time()
    import os
    r1 = E + f"out_e2e/{book}.r1.json"
    d = json.load(open(r1 if os.path.exists(r1) else E + f"out_e2e/{book}.json"))
    truth = {l["page"] for s in d["sets"] for l in s["location"]} | {c["page"] for s in d["sets"] for c in s["components"]}
    pdf = pdfium.PdfDocument(D + p["file"])
    texts = [pdf[i].get_textpage().get_text_range()[:3000] for i in range(len(pdf))]
    n = len(texts)
    scores, vocab = page_scores(D + p["file"])
    finder_pages = {i for a, b in runs(scores, vocab) for i in range(a, b + 1)}
    tf = TfidfVectorizer(stop_words="english", min_df=1).fit(texts + HINTS)
    X = tf.transform(texts); H = tf.transform([" ".join(HINTS)])
    tfidf_score = (X @ H.T).toarray().ravel()
    emb = model.encode(texts, normalize_embeddings=True, batch_size=64)
    emb_score = emb @ hint_vec
    results[book] = {"n": n, "truth": sorted(truth), "finder": sorted(finder_pages),
                     "tfidf": tfidf_score.tolist(), "emb": emb_score.tolist()}
    print(book, n, "pages", len(truth), "truth", f"{time.time()-t0:.0f}s", flush=True)
json.dump(results, open(sys.argv[1], "w"))
print("DONE")
