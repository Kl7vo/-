"""Generate an Arabic test PDF: header/footer repeated, mixed English/numbers, diacritics, 2 columns, scanned page."""
import pymupdf
from pathlib import Path

HERE = Path(__file__).parent
FONT = str(HERE / "NotoNaskhArabic.ttf")
CSS = "@font-face {font-family: naskh; src: url(NotoNaskhArabic.ttf);} * {font-family: naskh, sans-serif;}"
arch = pymupdf.Archive(str(HERE))

BODY = [
    "بسم الله الرحمن الرحيم. هذا نص تجريبي لاختبار القارئ السريع، ويحتوي على جمل عربية واضحة.",
    "في عام 2024 أطلقت شركة OpenAI نموذجاً جديداً، وبلغ عدد المستخدمين 150 مليون مستخدم تقريباً.",
    "قال الشاعر: العِلْمُ نُورٌ وَالجَهْلُ ظَلَامٌ؛ فاطلبوا العلم من المهد إلى اللحد!",
    "هل تعلم أن مدينة New York تقع في الولايات المتحدة؟ نعم، وهي من أكبر المدن.",
]


def add_text_page(doc, n, paras, two_cols=False):
    page = doc.new_page(width=595, height=842)
    page.insert_htmlbox(pymupdf.Rect(40, 20, 555, 50), f"<p dir='rtl' style='font-size:10px;text-align:center'>كتاب القراءة السريعة - الفصل الأول</p>", css=CSS, archive=arch)
    if two_cols:
        half = len(paras) // 2
        r = "".join(f"<p dir='rtl' style='font-size:13px'>{p}</p>" for p in paras[:half])
        l_ = "".join(f"<p dir='rtl' style='font-size:13px'>{p}</p>" for p in paras[half:])
        page.insert_htmlbox(pymupdf.Rect(310, 80, 555, 760), r, css=CSS, archive=arch)
        page.insert_htmlbox(pymupdf.Rect(40, 80, 285, 760), l_, css=CSS, archive=arch)
    else:
        html = "".join(f"<p dir='rtl' style='font-size:14px'>{p}</p>" for p in paras)
        page.insert_htmlbox(pymupdf.Rect(50, 80, 545, 760), html, css=CSS, archive=arch)
    page.insert_htmlbox(pymupdf.Rect(250, 800, 345, 830), f"<p style='font-size:10px;text-align:center'>{n}</p>", css=CSS, archive=arch)
    return page


def main():
    doc = pymupdf.open()
    add_text_page(doc, 1, BODY)
    add_text_page(doc, 2, BODY[::-1])
    add_text_page(doc, 3, ["العمود الأيمن: الفقرة الأولى في العمود الأيمن تُقرأ أولاً.", "ثم الفقرة الثانية في العمود الأيمن.",
                           "العمود الأيسر: هذه الفقرة تُقرأ بعد العمود الأيمن.", "وهذه آخر فقرة في الصفحة."], two_cols=True)
    # scanned page: rasterize page 1 into an image-only page
    pix = doc[0].get_pixmap(dpi=120)
    p = doc.new_page(width=595, height=842)
    p.insert_image(p.rect, pixmap=pix)
    add_text_page(doc, 5, BODY[:2])
    out = HERE / "arabic_sample.pdf"
    doc.save(str(out))
    print("saved", out, doc.page_count)


if __name__ == "__main__":
    main()
