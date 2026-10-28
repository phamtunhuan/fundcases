#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""用 macOS Vision 框架对扫描版处罚决定书 PDF 做中文 OCR。

用法:
    python scripts/ocr_vision.py            # 处理全部未完成 PDF
    python scripts/ocr_vision.py --workers 6
"""
import argparse
import json
import sys
import traceback
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "data" / "raw" / "docs"
OUT = ROOT / "data" / "ocr"
OUT.mkdir(parents=True, exist_ok=True)

SCALE = 2.0


def ocr_pdf(path: Path) -> str:
    import Vision
    from Quartz import (CGBitmapContextCreate, CGBitmapContextCreateImage,
                        CGColorSpaceCreateDeviceRGB, PDFDocument,
                        kCGImageAlphaPremultipliedLast, kCGPDFMediaBox)

    import Foundation
    url = Foundation.NSURL.fileURLWithPath_(str(path))
    doc = PDFDocument.alloc().initWithURL_(url)
    if doc is None:
        return ""
    n = doc.pageCount()
    pages = []
    for i in range(n):
        page = doc.pageAtIndex_(i)
        rect = page.boundsForBox_(kCGPDFMediaBox)
        w = max(1, int(rect.size.width * SCALE))
        h = max(1, int(rect.size.height * SCALE))
        cs = CGColorSpaceCreateDeviceRGB()
        ctx = CGBitmapContextCreate(None, w, h, 8, 0, cs,
                                    kCGImageAlphaPremultipliedLast)
        if ctx is None:
            continue
        page.drawWithBox_toContext_(kCGPDFMediaBox, ctx)
        img = CGBitmapContextCreateImage(ctx)
        if img is None:
            continue
        req = Vision.VNRecognizeTextRequest.alloc().init()
        req.setRecognitionLevel_(0)          # accurate
        req.setUsesLanguageCorrection_(True)
        req.setRecognitionLanguages_(["zh-Hans", "en-US"])
        handler = Vision.VNImageRequestHandler.alloc().initWithCGImage_options_(
            img, None)
        try:
            handler.performRequests_error_([req], None)
        except Exception:
            continue
        lines = []
        for obs in (req.results() or []):
            cands = obs.topCandidates_(1)
            if cands and len(cands):
                lines.append(cands[0].string())
        pages.append("\n".join(lines))
    return "\n\n<<<PAGE>>>\n\n".join(pages)


def work(path_str):
    path = Path(path_str)
    out = OUT / (path.stem + ".txt")
    if out.exists() and out.stat().st_size > 200:
        return "skip"
    try:
        text = ocr_pdf(path)
        out.write_text(text, encoding="utf-8")
        return f"ok:{len(text)}"
    except Exception:
        return "err:" + traceback.format_exc(limit=1).strip().splitlines()[-1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    pdfs = sorted(DOCS.glob("*.pdf"))
    if args.limit:
        pdfs = pdfs[:args.limit]
    print(f"待处理 PDF: {len(pdfs)}", flush=True)
    done = 0
    with Pool(args.workers) as pool:
        for i, res in enumerate(
                pool.imap_unordered(work, [str(p) for p in pdfs]), 1):
            if i % 20 == 0 or res.startswith("err"):
                print(f"  {i}/{len(pdfs)} -> {res}", flush=True)
            if not res.startswith("err"):
                done += 1
    print(f"完成 {done}/{len(pdfs)}; 输出目录 {OUT}")


if __name__ == "__main__":
    sys.exit(main())
