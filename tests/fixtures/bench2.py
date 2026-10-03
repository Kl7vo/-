import sys, io, re, unicodedata
sys.path.insert(0, "/app/backend")
import pymupdf, tesserocr, extraction as E
from PIL import Image
from bench_ocr import lev, norm
