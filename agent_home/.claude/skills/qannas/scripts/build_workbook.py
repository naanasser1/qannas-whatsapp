#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""يبني ملف Excel لدفعة قنص من leads.json — ثلاثة تبويبات بخط Arial واتجاه RTL.

    python build_workbook.py leads.json --out lead-gen-ksa-2026-08-26.xlsx

شكل leads.json موصوف في scripts/README.md
"""
import argparse
import json
import sys

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

INK = "1B1C1E"
ACCENT = "1F4E46"
HEAD_FILL = PatternFill("solid", fgColor=ACCENT)
ALT_FILL = PatternFill("solid", fgColor="F2F1ED")
MSG_FILL = PatternFill("solid", fgColor="FFF8E7")
_thin = Side(style="thin", color="D6D2C8")
BORDER = Border(left=_thin, right=_thin, top=_thin, bottom=_thin)

STORE_HEADERS = ["#", "المتجر", "المجال", "رابط الموقع", "قناة التواصل",
                 "العيب 1", "العيب 2", "العيب 3", "الحل المقترح",
                 "الرسالة الجاهزة للإرسال", "الحالة", "ملاحظات"]
STORE_WIDTHS = [5, 22, 30, 26, 28, 40, 40, 40, 40, 62, 15, 24]
PROJECT_HEADERS = ["المنصة", "عنوان المشروع", "الرابط", "ملاحظة", "الحالة"]
PROJECT_WIDTHS = [12, 46, 58, 46, 16]


def _style_header(ws, count, height=32):
    for c in range(1, count + 1):
        cell = ws.cell(row=1, column=c)
        cell.font = Font(name="Arial", size=11, bold=True, color="FFFFFF")
        cell.fill = HEAD_FILL
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = BORDER
    ws.row_dimensions[1].height = height


def _style_body(ws, rows, cols, height, skip_fill=(), widths=None):
    for r in range(2, 2 + rows):
        if widths:
            texts = [ws.cell(row=r, column=c).value for c in range(1, cols + 1)]
            ws.row_dimensions[r].height = _auto_height(texts, widths, height)
        else:
            ws.row_dimensions[r].height = height
        for c in range(1, cols + 1):
            cell = ws.cell(row=r, column=c)
            cell.font = Font(name="Arial", size=10, color=INK)
            cell.alignment = Alignment(horizontal="right", vertical="top", wrap_text=True)
            cell.border = BORDER
            if r % 2 == 0 and c not in skip_fill:
                cell.fill = ALT_FILL


def _auto_height(texts, widths, min_height, line_pt=13.5, max_height=409):
    """ارتفاع صف يتسع فعلاً للنص.

    Excel لا يحسب الارتفاع تلقائياً مع wrap_text عند ضبطه من openpyxl، فالنص
    الطويل يُقتطع بصرياً. نقدّر عدد الأسطر من عدد الحروف مقسوماً على عرض العمود،
    ونأخذ أطول خلية في الصف. هذا مهم تحديداً لتبويب المنهجية: نص حدود التحقق هو
    أهم ما في الدفعة، وقصّه يعني أن ناصر لن يقرأ ما لم يُتحقق منه.
    """
    lines = 1
    for text, width in zip(texts, widths):
        chars_per_line = max(int(width * 1.05), 10)
        needed = sum(max(1, -(-len(p) // chars_per_line))
                     for p in str(text or "").split("\n"))
        lines = max(lines, needed)
    return min(max(min_height, lines * line_pt + 8), max_height)


def _link(cell):
    if cell.value:
        cell.hyperlink = cell.value
        cell.font = Font(name="Arial", size=9, color=ACCENT, underline="single")


def build(data, out_path):
    meta = data.get("meta", {})
    stores = data.get("stores", [])
    projects = data.get("projects", [])
    if not stores:
        sys.exit("leads.json لا يحتوي على أي متجر في مفتاح stores")

    wb = Workbook()

    # ---- تبويب الرسائل ----
    ws = wb.active
    ws.title = "رسائل التواصل"
    ws.sheet_view.rightToLeft = True
    ws.append(STORE_HEADERS)
    _style_header(ws, len(STORE_HEADERS), 34)

    for i, s in enumerate(stores, start=1):
        flaws = list(s.get("flaws", []))[:3] + [""] * 3
        ws.append([s.get("id", i), s.get("name", ""), s.get("niche", ""),
                   s.get("site", ""), s.get("contact", ""),
                   flaws[0], flaws[1], flaws[2],
                   s.get("solution", ""), s.get("message", ""),
                   "جاهزة للإرسال", ""])

    _style_body(ws, len(stores), len(STORE_HEADERS), 120,
                skip_fill=(10,), widths=STORE_WIDTHS)
    for r in range(2, 2 + len(stores)):
        ws.cell(row=r, column=1).alignment = Alignment(horizontal="center", vertical="top")
        ws.cell(row=r, column=2).font = Font(name="Arial", size=10, bold=True, color=INK)
        ws.cell(row=r, column=10).fill = MSG_FILL
        _link(ws.cell(row=r, column=4))
        ws.cell(row=r, column=11).alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

    for i, w in enumerate(STORE_WIDTHS, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w

    dv = DataValidation(type="list",
                        formula1='"جاهزة للإرسال,تم الإرسال,رد إيجابي,لا يوجد رد,مغلق"',
                        allow_blank=True)
    ws.add_data_validation(dv)
    dv.add(f"K2:K{1 + len(stores)}")
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:L{1 + len(stores)}"

    # ---- تبويب المشاريع ----
    ws2 = wb.create_sheet("مشاريع مفتوحة")
    ws2.sheet_view.rightToLeft = True
    ws2.append(PROJECT_HEADERS)
    _style_header(ws2, len(PROJECT_HEADERS), 28)
    for p in projects:
        ws2.append([p.get("platform", ""), p.get("title", ""), p.get("url", ""),
                    p.get("note", ""), "لم يُقدَّم بعد"])
    _style_body(ws2, len(projects), len(PROJECT_HEADERS), 40, widths=PROJECT_WIDTHS)
    for r in range(2, 2 + len(projects)):
        _link(ws2.cell(row=r, column=3))
    for i, w in enumerate(PROJECT_WIDTHS, start=1):
        ws2.column_dimensions[get_column_letter(i)].width = w
    if projects:
        dv2 = DataValidation(type="list",
                             formula1='"لم يُقدَّم بعد,تم التقديم,مغلق,غير مناسب"',
                             allow_blank=True)
        ws2.add_data_validation(dv2)
        dv2.add(f"E2:E{1 + len(projects)}")
    ws2.freeze_panes = "A2"

    # ---- تبويب المنهجية ----
    ws3 = wb.create_sheet("المنهجية والمصادر")
    ws3.sheet_view.rightToLeft = True
    rows = [
        ("المنهجية والمصادر", ""),
        ("تاريخ التجهيز", meta.get("date_ar", meta.get("date", ""))),
        ("السوق المستهدف", meta.get("market", "السعودية")),
        ("مجال اليوم", meta.get("niche", "")),
        ("لغة الرسائل", meta.get("dialect", "لهجة خليجية خفيفة")),
        ("", ""),
        ("كيف اُستخرجت العيوب", meta.get("method", "")),
        ("حدود التحقق", meta.get("limits", "")),
        ("حالة المشاريع", meta.get("projects_note", "")),
        ("", ""),
        ("الخطوة التالية المقترحة", meta.get("next_step", "")),
    ]
    for row in rows:
        ws3.append(list(row))
    ws3.column_dimensions["A"].width = 26
    ws3.column_dimensions["B"].width = 95
    for r in range(1, len(rows) + 1):
        a, b = ws3.cell(row=r, column=1), ws3.cell(row=r, column=2)
        a.font = Font(name="Arial", size=10, bold=True, color=INK)
        a.alignment = Alignment(horizontal="right", vertical="top")
        b.font = Font(name="Arial", size=10, color=INK)
        b.alignment = Alignment(horizontal="right", vertical="top", wrap_text=True)
        ws3.row_dimensions[r].height = _auto_height([b.value], [95], 24)
    ws3["A1"].font = Font(name="Arial", size=13, bold=True, color=ACCENT)
    ws3.row_dimensions[1].height = 24

    wb.save(out_path)
    return out_path


def main():
    ap = argparse.ArgumentParser(description="بناء ملف Excel لدفعة قنص")
    ap.add_argument("leads", help="مسار ملف leads.json")
    ap.add_argument("--out", required=True, help="مسار ملف xlsx الناتج")
    args = ap.parse_args()
    with open(args.leads, encoding="utf-8") as fh:
        data = json.load(fh)
    print(build(data, args.out))


if __name__ == "__main__":
    main()
