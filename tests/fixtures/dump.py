import sys
sys.path.insert(0, '/app/backend')
import pymupdf, extraction as E
doc = pymupdf.open(sys.argv[1])
pages = []
for i in range(doc.page_count):
    r = E.extract_page(doc, i); r['page_number'] = i + 1; pages.append(r)
E.detect_furniture(pages)
for p in pages:
    E.mark_footnotes(p); print('--- page', p['page_number'], E.assess_page(p), p['stats'], p['two_columns'])
    for b in p['blocks']:
        for ln in b['lines']: print(ln['role'], ln['excluded'], '|', ln['text'])
