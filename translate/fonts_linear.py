#!/usr/bin/env python3
"""把 pdftohtml -xml 输出转成按页的线性字体标注文本，用于公式字体校对。"""
import re
import sys
import os
import html


def main(xml_path, outdir):
    os.makedirs(outdir, exist_ok=True)
    with open(xml_path, encoding='utf-8', errors='replace') as f:
        xml = f.read()
    fonts = {}
    for m in re.finditer(r'<fontspec id="(\d+)"[^>]*family="([^"]+)"', xml):
        fonts[m.group(1)] = html.unescape(m.group(2))
    pages = re.findall(r'<page number="(\d+)"[^>]*>(.*?)</page>', xml, re.S)
    count = 0
    for num, body in pages:
        lines = []
        for m in re.finditer(r'<text[^>]*font="(\d+)"[^>]*>(.*?)</text>', body):
            fid = m.group(1)
            txt = m.group(2)
            fam = fonts.get(fid, '?').split('+')[-1]
            txt = re.sub(r'<[^>]*>', '', txt)
            txt = html.unescape(txt)
            if txt.strip():
                lines.append(f"{txt}[{fam}]")
        out = os.path.join(outdir, f"fonts_p{int(num):03d}.txt")
        with open(out, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))
        count += 1
    print(f"{xml_path}: {count} pages -> {outdir}")


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
