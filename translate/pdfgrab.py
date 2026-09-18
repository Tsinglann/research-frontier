#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pdfgrab —— 从 PDF 中精准截取插图（用于翻译论文插图重建）

三种能力：
  detect  自动探测每页的图候选区域（bbox），可输出 JSON 与可视化标注图
  crop    按给定 bbox 精确裁切，输出矢量 PDF（首选）/ 高分辨率 PNG
  auto    detect + crop 一条龙，按候选自动裁切

设计要点：
  * 矢量保真：用 PyMuPDF 的 show_pdf_page(clip=...) 重排到新页，矢量零损失
  * 混合图：RevTeX/AIP 的图常是「矢量坐标轴 + 位图子图」，不能只提位图
  * bbox 来源：图注(caption)锚定 + 同栏可见元素(drawings/images)并集
  * 文本边界：图的上下界由同栏最近文本块夹住，避免吞掉页眉/相邻图
  * overlay 带像素自检，杜绝「框没画上却以为画上了」的假验证
"""
import argparse
import json
import os
import re
import sys

import pymupdf as fitz

CAPTION_RE = re.compile(r'^\s*(FIG(?:URE)?|TABLE|Tab\.?)\s*\.?\s*([0-9IVX]+)', re.I)

BANNER_W_FRAC = 0.88     # 全宽
BANNER_TOP_FRAC = 0.15   # 贴页顶
BANNER_H_FRAC = 0.18     # 矮


# ---------------------------------------------------------------- 元素收集

def text_blocks(page):
    """纯文本块 [(Rect, text)]，用于图注匹配与边界约束"""
    out = []
    for b in page.get_text("blocks"):
        if len(b) >= 7 and int(b[6]) != 0:
            continue
        txt = (b[4] or "").strip()
        if not txt:
            continue
        out.append((fitz.Rect(b[0], b[1], b[2], b[3]), txt))
    return out


def find_captions(tbs):
    """[(caption_rect, label, kind)]，kind in {FIG, TABLE}"""
    res = []
    for r, txt in tbs:
        m = CAPTION_RE.match(txt)
        if not m:
            continue
        kind = m.group(1).upper()
        kind = "TABLE" if kind.startswith("TAB") else "FIG"
        res.append((r, f"{kind} {m.group(2)}", kind))
    return res


def page_elements(page, min_area=6.0):
    """页面上的内容元素 [(kind, Rect, area)]；kind in {vec, img, scan}"""
    pr = page.rect
    page_area = pr.get_area()
    out = []

    for d in page.get_drawings():
        r = d.get("rect")
        if r is None:
            continue
        r = fitz.Rect(r)
        if r.is_empty or r.is_infinite:
            continue
        if r.width < 0.8 or r.height < 0.8:
            continue
        if r.get_area() > 0.90 * page_area:          # 整页背景
            continue
        if r.height < 2.5 and r.width > 0.85 * pr.width:  # 页眉页脚分隔线
            continue
        out.append(("vec", r, r.get_area()))

    for im in page.get_image_info():
        r = fitz.Rect(im["bbox"])
        if r.is_empty:
            continue
        if r.get_area() > 0.90 * page_area:          # 扫描件整页图
            out.append(("scan", r, r.get_area()))
            continue
        out.append(("img", r, r.get_area()))

    return [e for e in out if e[2] >= min_area or e[0] == "scan"]


# ---------------------------------------------------------------- 几何工具

def _hov(a, b):
    return min(a.x1, b.x1) - max(a.x0, b.x0)


def _union(rects):
    it = iter(rects)
    box = fitz.Rect(next(it))
    for r in it:
        box = box | r
    return box


def _overlaps_axis(a, b, axis, frac=0.10):
    if axis == "x":
        ov = min(a.x1, b.x1) - max(a.x0, b.x0)
        base = min(a.width, b.width)
    else:
        ov = min(a.y1, b.y1) - max(a.y0, b.y0)
        base = min(a.height, b.height)
    return ov > frac * max(base, 1e-6)


def cluster_rects(rects, gap=20.0):
    """贪心聚类：一个方向有重叠、另一方向间距小于 gap 即合并"""
    boxes = [fitz.Rect(r) for r in rects]
    changed = True
    while changed:
        changed = False
        i = 0
        while i < len(boxes):
            j = i + 1
            while j < len(boxes):
                a, b = boxes[i], boxes[j]
                hgap = max(a.x0, b.x0) - min(a.x1, b.x1)
                vgap = max(a.y0, b.y0) - min(a.y1, b.y1)
                join = False
                if vgap < gap and _overlaps_axis(a, b, "x"):
                    join = True
                elif hgap < gap and _overlaps_axis(a, b, "y"):
                    join = True
                elif vgap < gap * 0.5 and hgap < gap * 0.5:
                    join = True
                if join:
                    boxes[i] = a | b
                    boxes.pop(j)
                    changed = True
                else:
                    j += 1
            i += 1
    return boxes


def _is_banner(box, pr):
    return (box.width > BANNER_W_FRAC * pr.width
            and box.y0 < BANNER_TOP_FRAC * pr.height
            and box.height < BANNER_H_FRAC * pr.height)


def trim_running_heads(page, box, tbs):
    """图不应包含页眉/页脚跑动标题，命中则把该区域从 bbox 剔除"""
    pr = page.rect
    for tr, _t in tbs:
        if tr.width < 0.45 * pr.width:
            continue
        if tr.y0 < 0.07 * pr.height and tr.y1 < 0.12 * pr.height:      # 页眉
            if box.y0 < tr.y1 and _hov(box, tr) > 0.3 * tr.width:
                box = fitz.Rect(box.x0, tr.y1, box.x1, box.y1)
        elif tr.y1 > 0.93 * pr.height and tr.y0 > 0.88 * pr.height:     # 页脚
            if box.y1 > tr.y0 and _hov(box, tr) > 0.3 * tr.width:
                box = fitz.Rect(box.x0, box.y0, box.x1, tr.y0)
    return box


def absorb_neighbors(box, rects, max_gap=30.0, min_vover=0.6, min_wh=30.0):
    """把与 box 垂直对齐、水平紧邻的元素簇并进来。

    解决双栏排版：跨栏图注被 PDF 拆成左右两个文本块时，只会锚定到一栏，
    另一半面板需要靠几何邻接补回来。
    只吸收够大的簇——正文里的矢量碎片（公式符号、下划线）必须排除，
    否则会越吸越大（雪球效应）。
    """
    pool = [fitz.Rect(r) for r in rects
            if r.width >= min_wh and r.height >= min_wh]
    while pool:
        merged = False
        for g in cluster_rects(pool, gap=20.0):
            vov = min(box.y1, g.y1) - max(box.y0, g.y0)
            if vov < min_vover * min(box.height, g.height):
                continue
            hgap = max(box.x0, g.x0) - min(box.x1, g.x1)
            if hgap <= max_gap:
                box = box | g
                pool = [r for r in pool
                        if (r & g).get_area() < 0.5 * r.get_area()]
                merged = True
                break
        if not merged:
            break
    return box, pool


def _dedup(cands):
    """按面积降序处理：被更大候选几乎包含的丢弃；部分重叠的视为重复丢小的"""
    out = []
    for c in sorted(cands, key=lambda c: -(c["w_pt"] * c["h_pt"])):
        rc = fitz.Rect(c["bbox"])
        drop = False
        for f in out:
            rf = fitz.Rect(f["bbox"])
            inter = (rc & rf).get_area()
            if inter <= 0:
                continue
            small = min(rc.get_area(), rf.get_area())
            if inter > 0.50 * small:
                drop = True
                break
        if not drop:
            out.append(c)
    return out


# ---------------------------------------------------------------- 检测

def detect_page(page, pno, gap=20.0, min_area=6.0, pad=3.0,
                min_w=36.0, min_h=24.0):
    """单页候选图区域。返回 list of dict"""
    pr = page.rect
    els = page_elements(page, min_area=min_area)
    tbs = text_blocks(page)
    caps = find_captions(tbs)
    cands = []
    used = set()

    # ---- 策略 A：图注锚定 ----
    # 图题(FIG)在图的**下方**，表题(TABLE)在表的**上方**（学术排版惯例）
    for crect, label, kind in caps:
        up = (kind == "FIG")
        wide = crect.width > 0.62 * pr.width
        members = []
        for idx, (k, r, _a) in enumerate(els):
            if k == "scan":
                continue
            if up and r.y1 > crect.y0 + 4:            # 必须在图注之上
                continue
            if (not up) and r.y0 < crect.y1 - 4:      # 必须在表注之下
                continue
            if not wide:
                if _hov(r, crect) <= 0:               # 同栏：水平须重叠
                    continue
            else:
                if _hov(r, crect) <= 0.15 * min(r.width, crect.width):
                    continue
            members.append((idx, r))
        if not members:
            continue

        box_raw = _union([r for _i, r in members]) & pr

        # 文本边界：同栏最近文本块把图夹住，防止吞掉页眉或相邻的图。
        # 关键：只认「位于元素并集**之外**」的文本块——图内部的标签文字
        # （坐标轴、A/B 面板名）必须排除，否则会把图从中间切断。
        if up:
            ref, bound = box_raw.y0, pr.y0
            for tr, _t in tbs:
                if tr == crect or _hov(tr, crect) <= 0:
                    continue
                if tr.y1 > crect.y0 or tr.y1 > ref + 6:
                    continue
                bound = max(bound, tr.y1)
            box = fitz.Rect(box_raw.x0, max(box_raw.y0, bound),
                            box_raw.x1, box_raw.y1)
        else:
            ref, bound = box_raw.y1, pr.y1
            for tr, _t in tbs:
                if tr == crect or _hov(tr, crect) <= 0:
                    continue
                if tr.y0 < crect.y1 or tr.y0 < ref - 6:
                    continue
                bound = min(bound, tr.y0)
            box = fitz.Rect(box_raw.x0, box_raw.y0,
                            box_raw.x1, min(box_raw.y1, bound))

        for idx, _r in members:
            used.add(idx)

        # 页眉/页脚跑动标题剔除（图不该含期刊页眉）
        box = trim_running_heads(page, box, tbs)
        # 双栏图的另一半：靠几何邻接把它补回来
        leftover = [r for i, (_k, r, _a) in enumerate(els)
                    if i not in used and _k != "scan"]
        box, _rest = absorb_neighbors(box, leftover)
        for i, (_k, r, _a) in enumerate(els):          # 吸收进来的标为已用
            if i not in used and _k != "scan" \
                    and (r & box).get_area() > 0.85 * r.get_area():
                used.add(i)

        clipped = not pr.contains(box)
        box = (box & pr)
        box = fitz.Rect(box.x0 - pad, box.y0 - pad,
                        box.x1 + pad, box.y1 + pad) & pr
        if box.width < min_w or box.height < min_h:
            continue

        n_img = sum(1 for i, _r in members if els[i][0] == "img")
        suspect = None
        if _is_banner(box, pr):
            suspect = "banner"
        elif n_img == 0 and len(members) < 4:
            suspect = "weak"

        cands.append({
            "page": pno + 1, "label": label, "source": "caption",
            "bbox": [round(v, 2) for v in box],
            "w_pt": round(box.width, 2), "h_pt": round(box.height, 2),
            "n_vec": len(members) - n_img, "n_img": n_img,
            "clipped": clipped, "suspect": suspect,
        })

    # ---- 策略 B：无图注的图，靠元素聚类兜底 ----
    rest = [(i, r) for i, (k, r, _a) in enumerate(els)
            if i not in used and k != "scan"
            and r.width >= min_w * 0.6 and r.height >= min_h * 0.6]
    for box in cluster_rects([r for _i, r in rest], gap=gap):
        if box.width < min_w or box.height < min_h:
            continue
        inside = [(i, r) for i, r in rest
                  if (r & box).get_area() > 0.5 * r.get_area()]
        if len(inside) < 2:
            continue
        n_img = sum(1 for i, _r in inside if els[i][0] == "img")
        clipped = not pr.contains(box)
        box = fitz.Rect(box.x0 - pad, box.y0 - pad,
                        box.x1 + pad, box.y1 + pad) & pr
        suspect = None
        if _is_banner(box, pr):
            suspect = "banner"
        elif n_img == 0 and len(inside) < 4:
            suspect = "weak"
        cands.append({
            "page": pno + 1, "label": f"p{pno+1}-cand", "source": "cluster",
            "bbox": [round(v, 2) for v in box],
            "w_pt": round(box.width, 2), "h_pt": round(box.height, 2),
            "n_vec": len(inside) - n_img, "n_img": n_img,
            "clipped": clipped, "suspect": suspect,
        })

    # ---- 扫描件整页 ----
    for k, r, _a in els:
        if k == "scan":
            cands.append({
                "page": pno + 1, "label": f"p{pno+1}-scan", "source": "scan",
                "bbox": [round(v, 2) for v in r],
                "w_pt": round(r.width, 2), "h_pt": round(r.height, 2),
                "n_vec": 0, "n_img": 1, "clipped": False, "suspect": None,
            })

    # 去重：按面积降序，被更大候选包含的丢弃（大框才完整）
    final = _dedup(cands)
    final.sort(key=lambda c: (c["page"], c["bbox"][1], c["bbox"][0]))
    return final


# ---------------------------------------------------------------- 裁切

def crop(page, bbox, out_base, dpi=600, formats=("pdf", "png"),
         pdf_doc=None, pno=0):
    """按 bbox 裁切，返回生成的文件列表"""
    r = fitz.Rect(bbox) & page.rect
    made = []
    d = os.path.dirname(out_base)
    if d:
        os.makedirs(d, exist_ok=True)

    if "pdf" in formats:
        src = pdf_doc if pdf_doc is not None else page.parent
        newdoc = fitz.open()
        np = newdoc.new_page(width=r.width, height=r.height)
        np.show_pdf_page(np.rect, src, pno, clip=r)   # 矢量保留
        p = out_base + ".pdf"
        newdoc.save(p, garbage=4, deflate=True)
        newdoc.close()
        made.append(p)

    if "png" in formats:
        pm = page.get_pixmap(clip=r, dpi=dpi)
        p = out_base + ".png"
        pm.save(p)
        made.append(p)

    return made


def overlay_page(page, cands, out_png, dpi=110, verify=True):
    """在页面副本上画红框做目视质检（会修改 page 内容，必须用独立 doc）。

    绘制后做像素自检：红色像素不足即抛错，避免「静默失败 → 看图幻觉」。
    """
    shape = page.new_shape()
    for i, c in enumerate(cands):
        r = fitz.Rect(c["bbox"])
        shape.draw_rect(r)
        shape.finish(color=(1, 0, 0), width=1.2, fill=None)
        tag = f"{i}:{c.get('label', '')}"
        if c.get("suspect"):
            tag += f"?{c['suspect']}"
        shape.insert_text((r.x0 + 2, max(r.y0 - 2, 8)), tag,
                          fontsize=8, color=(1, 0, 0))
    shape.commit()

    pm = page.get_pixmap(dpi=dpi)
    pm.save(out_png)

    if verify:
        n = pm.n
        s = pm.samples
        red = sum(1 for off in range(0, len(s), n)
                  if s[off] > 200 and s[off + 1] < 80 and s[off + 2] < 80)
        if red < 50:
            raise RuntimeError(
                f"overlay 自检失败：{out_png} 红色像素仅 {red}，"
                f"框未真正画出（不要据此判断 bbox！）")
        print(f"[overlay-ok] {out_png}  红像素={red}  候选={len(cands)}",
              file=sys.stderr)
    return out_png


# ---------------------------------------------------------------- CLI

def parse_pages(spec, n):
    if not spec:
        return list(range(n))
    out = []
    for part in spec.split(","):
        part = part.strip()
        if "-" in part:
            a, b = part.split("-")
            out += list(range(int(a) - 1, int(b)))
        else:
            out.append(int(part) - 1)
    return sorted({p for p in out if 0 <= p < n})


def fmt_line(c):
    flag = f"  <{c['suspect'].upper()}>" if c.get("suspect") else ""
    clip = "  <CLIPPED>" if c.get("clipped") else ""
    return (f"p{c['page']:<3} {c['label']:<10} {c['source']:<8} "
            f"bbox={c['bbox']}  {c['w_pt']}x{c['h_pt']}pt  "
            f"vec={c['n_vec']} img={c['n_img']}{flag}{clip}")


def main():
    ap = argparse.ArgumentParser(description="PDF 精准截图工具")
    sub = ap.add_subparsers(dest="cmd", required=True)

    d = sub.add_parser("detect", help="探测候选图区域")
    d.add_argument("pdf")
    d.add_argument("--pages", default="")
    d.add_argument("--json", default="")
    d.add_argument("--overlay", default="", help="输出标注图的目录")
    d.add_argument("--gap", type=float, default=20.0)

    c = sub.add_parser("crop", help="按 bbox 裁切")
    c.add_argument("pdf")
    c.add_argument("--page", type=int, required=True, help="1-based")
    c.add_argument("--bbox", required=True, help="x0,y0,x1,y1 (pt)")
    c.add_argument("--out", required=True, help="输出前缀（不含扩展名）")
    c.add_argument("--dpi", type=int, default=600)
    c.add_argument("--formats", default="pdf,png")

    a = sub.add_parser("auto", help="探测并自动裁切")
    a.add_argument("pdf")
    a.add_argument("--pages", default="")
    a.add_argument("--out", default="figures")
    a.add_argument("--dpi", type=int, default=600)
    a.add_argument("--formats", default="pdf")
    a.add_argument("--prefix", default="fig")
    a.add_argument("--overlay", default="")
    a.add_argument("--keep-suspect", action="store_true",
                   help="连可疑候选（banner/weak）也裁")

    args = ap.parse_args()
    doc = fitz.open(args.pdf)

    if args.cmd == "detect":
        pages = parse_pages(args.pages, doc.page_count)
        allc = []
        for pno in pages:
            cs = detect_page(doc[pno], pno, gap=args.gap)
            allc += cs
            if args.overlay:
                os.makedirs(args.overlay, exist_ok=True)
                od = fitz.open(args.pdf)             # 独立副本，避免污染
                op = os.path.join(args.overlay, f"ovl-p{pno+1:03d}.png")
                overlay_page(od[pno], cs, op)
                od.close()
                print(f"[overlay] {op}", file=sys.stderr)
        for c_ in allc:
            print(fmt_line(c_))
        if args.json:
            d_ = os.path.dirname(args.json)
            if d_:
                os.makedirs(d_, exist_ok=True)
            with open(args.json, "w", encoding="utf-8") as f:
                json.dump(allc, f, ensure_ascii=False, indent=2)
            print(f"[json] {args.json}", file=sys.stderr)

    elif args.cmd == "crop":
        pno = args.page - 1
        bbox = [float(v) for v in args.bbox.split(",")]
        fmts = tuple(s.strip() for s in args.formats.split(",") if s.strip())
        for p in crop(doc[pno], bbox, args.out, dpi=args.dpi,
                      formats=fmts, pdf_doc=doc, pno=pno):
            print(p)

    elif args.cmd == "auto":
        pages = parse_pages(args.pages, doc.page_count)
        os.makedirs(args.out, exist_ok=True)
        n = skipped = 0
        fmts = tuple(s.strip() for s in args.formats.split(",") if s.strip())
        for pno in pages:
            cs = detect_page(doc[pno], pno)
            if args.overlay:
                os.makedirs(args.overlay, exist_ok=True)
                od = fitz.open(args.pdf)
                overlay_page(od[pno], cs,
                             os.path.join(args.overlay, f"ovl-p{pno+1:03d}.png"))
                od.close()
            for c_ in cs:
                if c_["source"] == "scan":
                    continue
                if c_.get("suspect") and not args.keep_suspect:
                    print(f"[skip:{c_['suspect']}] {fmt_line(c_)}", file=sys.stderr)
                    skipped += 1
                    continue
                lbl = c_["label"].replace(".", "").replace(" ", "_").lower()
                base = os.path.join(args.out, f"{args.prefix}_{lbl}")
                for p in crop(doc[pno], c_["bbox"], base, dpi=args.dpi,
                              formats=fmts, pdf_doc=doc, pno=pno):
                    print(p)
                n += 1
        print(f"[done] {n} figure(s) -> {args.out}  (skipped suspect: {skipped})",
              file=sys.stderr)


if __name__ == "__main__":
    main()
