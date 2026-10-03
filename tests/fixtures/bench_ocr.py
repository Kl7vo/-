"""Benchmark local Tesseract OCR against the (correct) text layer of the user's book."""
import sys
import time

sys.path.insert(0, "/app/backend")
import pymupdf  # noqa: E402
import tesserocr  # noqa: E402
from PIL import Image  # noqa: E402
import io  # noqa: E402
import extraction as E  # noqa: E402

TESS = "/app/backend/tessdata"


def lev(a, b):
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def norm(t):
    return " ".join(t.split())


if __name__ != "__main__":
    raise SystemExit
doc = pymupdf.open(sys.argv[1])
pages = [int(x) for x in sys.argv[2].split(",")]
dpi = int(sys.argv[3]) if len(sys.argv) > 3 else 300
lang = sys.argv[4] if len(sys.argv) > 4 else "ara"
psm = int(sys.argv[5]) if len(sys.argv) > 5 else 3
with tesserocr.PyTessBaseAPI(path=TESS, lang=lang, psm=psm) as api:
    tot_e = tot_n = 0
    for p in pages:
        truth = norm(E.page_text(E.extract_page(doc, p - 1, True)["blocks"], include_excluded=True))
        pix = doc[p - 1].get_pixmap(dpi=dpi, colorspace=pymupdf.csGRAY)
        img = Image.open(io.BytesIO(pix.tobytes("png")))
        t0 = time.time()
        api.SetImage(img)
        out = norm(api.GetUTF8Text())
        conf = api.MeanTextConf()
        e = lev(truth, out)
        tot_e += e
        tot_n += len(truth)
        print(f"p{p} cer={e / max(1, len(truth)):.3f} conf={conf} t={time.time() - t0:.1f}s")
        if "-v" in sys.argv:
            print("TRUTH:", truth[:300])
            print("OCR  :", out[:300])
    print(f"TOTAL CER={tot_e / max(1, tot_n):.4f}")
