#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""يبني صفحة الويب العربية لدفعة قناص من leads.json.

    python build_board.py leads.json --out board.html

الناتج ملف واحد مكتفٍ ذاتياً (بلا موارد خارجية عدا خطوط Google) وجاهز للنشر
بأداة Artifact مباشرة: التقرير اليومي، بطاقة لكل فرصة بملاحظات الفحص ودرجتها
ورسالتها مع زر نسخ وصانع القرار، وقسم المشاريع المفتوحة، وحدود التحقق.
"""
import argparse
import html as html_mod
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import qannas_lib as lib  # noqa: E402

TEMPLATE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "board_template.html")

DEFAULTS = {
    "title": "قناص — فرص اليوم",
    "headline": "دفعة اليوم من الفرص التجارية",
    "sub": "كل شركة مع ملاحظات موثّقة من موقعها الرسمي، ودرجة من ١٠٠، والفرصة الأساسية، ورسالة جاهزة تنتهي بعرض نموذج مجاني صغير.",
    "projects_note": "المنصتان تمنعان القراءة الآلية، فهذه روابط مرشّحة من نتائج البحث ولم يُتحقق من كونها ما زالت مفتوحة. افتح كل رابط قبل التقديم.",
    "method": "زيارة الموقع الرسمي لكل شركة وفحص تجربة الاستخدام والواجهة والهوية وصور المنتجات وحداثة الموقع، ثم البحث عن المحتوى الإعلاني العام المتاح.",
    "limits": "الملاحظات مبنية على المواقع الرسمية فقط. افتح حسابات كل شركة على تيك توك وإنستقرام قبل الإرسال لتأكيد الملاحظات المتعلقة بالإعلانات.",
    "next_step": "ابدأ بالفرص المصنّفة HOT — الفجوة عندها أوضح وأسهل إثباتاً في سطر واحد.",
}


def _stats_block(leads, projects):
    notes = sum(len(v) for l in leads for v in l["audit"].values())
    hot = sum(1 for l in leads if "HOT" in l["tier"])
    top = max((l["total"] for l in leads), default=0)
    tiles = [
        (str(len(leads)), "فرصة في الدفعة"),
        (str(hot), "فرصة بتصنيف HOT"),
        (str(top), "أعلى درجة"),
        (str(notes), "ملاحظة موثّقة"),
        (str(len(projects)), "مشروع مرشّح"),
    ]
    inner = "".join(
        f'<div class="stat"><b>{html_mod.escape(v)}</b>'
        f'<span>{html_mod.escape(label)}</span></div>'
        for v, label in tiles
    )
    return f'<div class="stats">{inner}</div>'


def _js(value):
    """JSON آمن للإدراج داخل وسم script."""
    return json.dumps(value, ensure_ascii=False).replace("</", "<\\/")


def build(data, out_path):
    meta = data.get("meta", {})
    leads = data["leads"]
    projects = list(data.get("upwork", [])) + list(data.get("mostaql", []))
    projects.sort(key=lambda x: -x["score"])

    with open(TEMPLATE, encoding="utf-8") as fh:
        page = fh.read()

    report = meta.get("report", {}) or {}
    report.setdefault("top3", [])

    subs = {
        "__LEADS__": _js(leads),
        "__PROJECTS__": _js(projects),
        "__REPORT__": _js(report),
        "__STATS__": _stats_block(leads, projects),
        "__DATE_AR__": html_mod.escape(meta.get("date_ar", meta.get("date", ""))),
    }
    for key, default in DEFAULTS.items():
        subs["__" + key.upper() + "__"] = html_mod.escape(meta.get(key, default))

    for token, value in subs.items():
        page = page.replace(token, value)

    leftover = [t for t in subs if t in page]
    if leftover:
        sys.exit(f"بقيت عناصر نائبة لم تُستبدل: {leftover}")

    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(page)
    return out_path


def main():
    ap = argparse.ArgumentParser(description="بناء صفحة الويب لدفعة قناص")
    ap.add_argument("leads", help="مسار ملف leads.json")
    ap.add_argument("--out", required=True, help="مسار ملف html الناتج")
    args = ap.parse_args()
    print(build(lib.load(args.leads), args.out))


if __name__ == "__main__":
    main()
