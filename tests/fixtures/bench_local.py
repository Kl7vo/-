import sys, time, unicodedata
sys.path.insert(0, "/app/backend")
import pymupdf, extraction as E, ocr
def lev(a, b):
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]
norm = lambda t: " ".join(t.split())
sd = lambda t: "".join(c for c in t if not unicodedata.combining(c))
path = sys.argv[1]; pages = [int(x) for x in sys.argv[2].split(",")]
data = open(path, "rb").read(); doc = pymupdf.open(path)
ext = {i + 1: E.extract_page(doc, i, True) for i in range(doc.page_count)}
use_vocab = "--vocab" in sys.argv
tot = {"raw": [0, 0], "nodiac": [0, 0]}
for p in pages:
    truth = norm(E.page_text(ext[p]["blocks"], include_excluded=True))
    vocab = ocr.build_doc_vocab([v for k, v in ext.items() if k != p]) if use_vocab else set()
    t0 = time.time(); r = ocr.ocr_page_blocks(data, p - 1, vocab); dt = time.time() - t0
    out = norm(E.page_text(r["blocks"], include_excluded=True))
    e1 = lev(truth, out); e2 = lev(sd(truth), sd(out))
    tot["raw"][0] += e1; tot["raw"][1] += len(truth); tot["nodiac"][0] += e2; tot["nodiac"][1] += len(sd(truth))
    if not truth: continue
    print(f"p{p} cer={e1/len(truth):.3f} nodiac={e2/len(sd(truth)):.3f} conf={r['mean_conf']} fixes={r['corrections']} t={dt:.1f}s")
    if "-v" in sys.argv: print(out[:400])
print({k: round(v[0] / v[1], 4) for k, v in tot.items()})
