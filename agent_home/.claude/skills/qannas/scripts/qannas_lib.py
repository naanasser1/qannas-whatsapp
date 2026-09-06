#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""منطق مشترك بين بناء ملف Excel وبناء صفحة الويب.

يحمّل `leads.json`، ويتحقق من صحته، ويحسب درجة كل فرصة وتصنيفها، ويرتّب
الفرص تنازلياً بالدرجة.

الدرجة تُحسب هنا ولا تُكتب يدوياً في الملف: مجموع مكتوب بخط اليد ينحرف عن
مكوّناته بعد أول تعديل، وناصر يقرر من الترتيب بمن يبدأ — فمجموع خاطئ يعني
أنه يبدأ بالفرصة الخطأ.
"""
import json
import sys

# المعيار -> (الحد الأقصى، الاسم المعروض)
CRITERIA = [
    ("ux_ui",      20, "Website UX/UI Opportunity"),
    ("video",      20, "Video / Advertising Opportunity"),
    ("brand",      15, "Brand / Logo Opportunity"),
    ("likelihood", 15, "Likelihood of Buying Digital Services"),
    ("visuals",    10, "Product Image / Visual Opportunity"),
    ("ecom",       10, "E-commerce Potential"),
    ("quality",    10, "Brand / Business Quality"),
]
MAXES = {key: cap for key, cap, _ in CRITERIA}

MIN_SCORE = 70  # أقل من هذا لا يُدرج — المواصفة، القسم ٥

TIERS = [
    (90, "🔥 HOT LEAD"),
    (80, "🟢 HIGH PRIORITY"),
    (70, "🟡 MEDIUM"),
]

PROJECT_TIERS = [
    (85, "🔥 عالية"),
    (70, "🟢 مرتفعة"),
    (55, "🟡 متوسطة"),
]

AUDIT_FIELDS = ["ux", "ui", "brand", "images", "ads"]

UNVERIFIED = "Unable to verify"


def fail(msg):
    sys.exit(f"خطأ في leads.json: {msg}")


def tier_for(total, table=TIERS, below="⚪️ دون الحد"):
    for floor, label in table:
        if total >= floor:
            return label
    return below


def score_lead(lead, where):
    """يجمع مكوّنات الدرجة ويتحقق من حدودها. يعيد (المجموع، التصنيف)."""
    raw = lead.get("score")
    if not isinstance(raw, dict):
        fail(f"{where}: مفتاح score ناقص أو ليس كائناً. "
             f"المطلوب: {', '.join(k for k, _, _ in CRITERIA)}")

    unknown = set(raw) - set(MAXES)
    if unknown:
        fail(f"{where}: مفاتيح غير معروفة في score: {', '.join(sorted(unknown))}")

    total = 0
    for key, cap, label in CRITERIA:
        value = raw.get(key, 0)
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            fail(f"{where}: score.{key} يجب أن يكون رقماً (المعيار: {label})")
        if value < 0 or value > cap:
            fail(f"{where}: score.{key} = {value} خارج المدى المسموح 0–{cap} "
                 f"({label})")
        total += value

    total = int(round(total))
    if total < MIN_SCORE:
        fail(f"{where}: المجموع {total} أقل من {MIN_SCORE} — "
             f"المواصفة تمنع إدراجه. استبدل الشركة أو راجع التقييم.")
    return total, tier_for(total)


def _bullets(items):
    """يحوّل قائمة ملاحظات إلى نص بسطر لكل ملاحظة."""
    clean = [str(x).strip() for x in (items or []) if str(x).strip()]
    if not clean:
        return UNVERIFIED
    return "\n".join(f"• {x}" for x in clean)


def normalize(data):
    """يتحقق من الملف ويكمل الحقول المشتقة ويرتّب. يعدّل `data` في مكانه."""
    if not isinstance(data, dict):
        fail("الملف يجب أن يحتوي كائن JSON في جذره")

    data.setdefault("meta", {})
    leads = data.get("leads")
    if not leads:
        fail("لا توجد أي فرصة في مفتاح leads")
    if not isinstance(leads, list):
        fail("مفتاح leads يجب أن يكون قائمة")

    for i, lead in enumerate(leads, start=1):
        name = lead.get("company") or f"الفرصة رقم {i}"
        where = f"leads[{i}] ({name})"

        for field in ("company", "country", "industry", "website",
                      "primary_opportunity", "recommended_service", "message"):
            if not str(lead.get(field, "")).strip():
                fail(f"{where}: الحقل المطلوب '{field}' فارغ")

        audit = lead.get("audit")
        if not isinstance(audit, dict):
            fail(f"{where}: مفتاح audit ناقص أو ليس كائناً "
                 f"(المطلوب: {', '.join(AUDIT_FIELDS)})")
        for field in AUDIT_FIELDS:
            audit.setdefault(field, [])
            if not isinstance(audit[field], list):
                fail(f"{where}: audit.{field} يجب أن يكون قائمة نصوص")
        lead["audit"] = audit

        lead["total"], lead["tier"] = score_lead(lead, where)

        lead.setdefault("contact", "")
        lead.setdefault("source", UNVERIFIED)
        lead.setdefault("free_sample", "")
        lead.setdefault("website_status", UNVERIFIED)
        lead.setdefault("freshness", UNVERIFIED)
        lead.setdefault("opportunities", [])

        dm = lead.get("decision_maker") or {}
        if not isinstance(dm, dict):
            fail(f"{where}: decision_maker يجب أن يكون كائناً")
        for field in ("name", "position", "email", "linkedin", "instagram"):
            dm.setdefault(field, "")
        lead["decision_maker"] = dm

        # نصوص جاهزة للجدول وللصفحة
        ux_ui = (audit["ux"] or []) + (audit["ui"] or [])
        lead["ux_ui_text"] = _bullets(ux_ui)
        lead["brand_text"] = _bullets(audit["brand"])
        lead["images_text"] = _bullets(audit["images"])
        lead["ads_text"] = _bullets(audit["ads"])
        lead["dm_text"] = " — ".join(x for x in (dm["name"], dm["position"]) if x) \
            or UNVERIFIED

    leads.sort(key=lambda x: -x["total"])
    for i, lead in enumerate(leads, start=1):
        lead["id"] = i

    for key in ("upwork", "mostaql"):
        items = data.get(key) or []
        if not isinstance(items, list):
            fail(f"مفتاح {key} يجب أن يكون قائمة")
        for j, p in enumerate(items, start=1):
            if not str(p.get("title", "")).strip():
                fail(f"{key}[{j}]: الحقل 'title' فارغ")
            if not str(p.get("url", "")).strip():
                fail(f"{key}[{j}]: الحقل 'url' فارغ")
            for field in ("client", "budget", "posted", "skills", "summary",
                          "why_fits", "proposal_angle", "competition"):
                p.setdefault(field, UNVERIFIED)
            raw = p.get("score", 0)
            if not isinstance(raw, (int, float)) or isinstance(raw, bool):
                fail(f"{key}[{j}]: score يجب أن يكون رقماً من ١٠٠")
            p["score"] = int(round(raw))
            p["tier"] = tier_for(p["score"], PROJECT_TIERS)
            p["platform"] = "Upwork" if key == "upwork" else "مستقل"
        items.sort(key=lambda x: -x["score"])
        data[key] = items

    return data


def load(path):
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except FileNotFoundError:
        sys.exit(f"لم يُعثر على الملف: {path}")
    except json.JSONDecodeError as e:
        sys.exit(f"خطأ في صياغة JSON بالملف {path} — السطر {e.lineno}: {e.msg}")
    return normalize(data)
