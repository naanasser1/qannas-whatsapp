#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""يبني صفحة الويب العربية لدفعة قنص من leads.json.

    python build_board.py leads.json --out board.html

الناتج ملف واحد مكتفٍ ذاتياً (بلا موارد خارجية عدا خطوط Google) وجاهز للنشر
بأداة Artifact مباشرة: بطاقة لكل متجر بملاحظاتها وحلها ورسالتها مع زر نسخ،
قسم للمشاريع المفتوحة، وقسم للمنهجية وحدود التحقق.
"""
import argparse
import html as html_mod
import json
import os
import sys

TEMPLATE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "board_template.html")

DEFAULTS = {
    "title": "قنص متاجر السعودية",
    "headline": "دفعة اليوم من المتاجر",
    "sub": "كل متجر مع ثلاث ملاحظات موثّقة من موقعه الرسمي، والحل المقترح بـ UGC والموشن ديزاين، ورسالة جاهزة تنتهي بعرض نموذج مجاني.",
    "projects_note": "المنصتان تمنعان القراءة الآلية، فهذه روابط مرشّحة من نتائج البحث ولم يُتحقق من كونها ما زالت مفتوحة. افتح كل رابط قبل التقديم.",
    "method": "زيارة الموقع الرسمي لكل متجر وفحص وسائط المنتج، ووجود الفيديو في الرئيسية وصفحات الأقسام، والقنوات المعلنة، وطريقة عرض نقاط البيع.",
    "limits": "الملاحظات مبنية على المواقع الرسمية فقط. افتح حساب كل متجر على تيك توك وإنستقرام قبل الإرسال لتأكيد الملاحظات المتعلقة بالقنوات.",
    "next_step": "ابدأ بالمتاجر التي لا تملك أي فيديو — الفجوة عندها سهلة الإثبات في سطر واحد.",
}


def _stats_block(stores, projects):
    flaws = sum(len(s.get("flaws", [])) for s in stores)
    tiles = [
        (str(len(stores)), "متاجر في الدفعة"),
        (str(flaws), "ملاحظة على المحتوى المرئي"),
        (str(len(projects)), "مشاريع مرشّحة للتقديم"),
    ]
    inner = "".join(
        f'<div class="stat"><b>{html_mod.escape(v)}</b>'
        f'<span>{html_mod.escape(label)}</span></div>'
        for v, label in tiles
    )
    return f'<div class="stats">{inner}</div>'


def build(data, out_path):
    meta = data.get("meta", {})
    stores = data.get("stores", [])
    projects = data.get("projects", [])
    if not stores:
        sys.exit("leads.json لا يحتوي على أي متجر في مفتاح stores")

    for i, s in enumerate(stores, start=1):
        s.setdefault("id", i)

    with open(TEMPLATE, encoding="utf-8") as fh:
        page = fh.read()

    subs = {
        "__STORES__": json.dumps(stores, ensure_ascii=False),
        "__PROJECTS__": json.dumps(projects, ensure_ascii=False),
        "__STATS__": _stats_block(stores, projects),
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
    ap = argparse.ArgumentParser(description="بناء صفحة الويب لدفعة قنص")
    ap.add_argument("leads", help="مسار ملف leads.json")
    ap.add_argument("--out", required=True, help="مسار ملف html الناتج")
    args = ap.parse_args()
    with open(args.leads, encoding="utf-8") as fh:
        data = json.load(fh)
    print(build(data, args.out))


if __name__ == "__main__":
    main()
