# شكل ملف leads.json

السكربتان يقرآن نفس الملف. اكتبه بترميز UTF-8 بهذا الشكل:

```json
{
  "meta": {
    "date": "2026-08-30",
    "date_ar": "٣٠ أغسطس ٢٠٢٦",
    "markets": "السعودية · الإمارات",
    "niche": "عناية بالبشرة ومكياج",
    "dialect": "لهجة خليجية خفيفة",
    "title": "قناص — فرص اليوم",
    "headline": "خمس علامات عناية تبيع بصور ثابتة",
    "sub": "سطر أو سطران يلخصان الدفعة.",
    "method": "كيف اُستخرجت الملاحظات — وصف الفحص الفعلي.",
    "limits": "ما لم يُتحقق منه: الإعلانات على تيك توك وميتا لم تُشاهد...",
    "projects_note": "المنصتان تمنعان القراءة الآلية، فهذه روابط مرشّحة...",
    "next_step": "بأي فرصتين يُنصح البدء ولماذا.",
    "report": {
      "top3": ["الأولى — والسبب", "الثانية — والسبب", "الثالثة — والسبب"],
      "best_commercial": "الأقرب للتحوّل إلى عميل، ولماذا.",
      "best_design": "أفضل فرصة UX/UI أو Branding.",
      "best_video": "أفضل فرصة UGC أو موشن أو فيديو إعلاني.",
      "best_upwork": "أفضل مشروع Upwork وسبب اختياره.",
      "best_mostaql": "أفضل مشروع مستقل وسبب اختياره."
    }
  },
  "leads": [
    {
      "company": "اسم الشركة",
      "country": "السعودية",
      "industry": "المجال ووصف مختصر",
      "website": "https://example.sa/",
      "website_status": "يعمل — فُتحت الرئيسية وصفحتا قسم",
      "contact": "واتساب: +9665xxxxxxxx · إنستقرام: @handle",
      "audit": {
        "ux": ["ملاحظة على تجربة الاستخدام"],
        "ui": ["ملاحظة على الواجهة البصرية"],
        "brand": ["ملاحظة على الهوية — بصياغة غير هجومية"],
        "images": ["ملاحظة على صور المنتجات"],
        "ads": ["المشكلة → لماذا هي مشكلة → فرصة التحسين"]
      },
      "freshness": "Dated — بنر لموسم رمضان ٢٠٢٥ ما زال معروضاً",
      "opportunities": ["الفرصة الأولى", "الثانية", "الثالثة"],
      "primary_opportunity": "الفرصة التي تُبنى عليها الرسالة",
      "recommended_service": "UGC / Motion Video Ads",
      "free_sample": "One UGC Video Concept على منتج واحد",
      "score": {
        "ux_ui": 15, "video": 19, "brand": 11,
        "likelihood": 13, "visuals": 8, "ecom": 9, "quality": 9
      },
      "decision_maker": {
        "name": "الاسم أو Unable to verify",
        "position": "Founder",
        "email": "name@example.sa",
        "linkedin": "https://www.linkedin.com/in/...",
        "instagram": "@brand"
      },
      "message": "نص الرسالة كاملاً مع فواصل الأسطر.",
      "source": "بحث سلة — [الصيغة المستخدمة]"
    }
  ],
  "upwork": [
    {
      "title": "عنوان المشروع",
      "client": "اسم العميل أو Unable to verify",
      "url": "https://www.upwork.com/jobs/...",
      "budget": "$500 fixed",
      "posted": "2026-08-28",
      "skills": "UGC · Motion Graphics",
      "summary": "سطران عن المطلوب فعلاً.",
      "why_fits": "لماذا يناسب ناصر تحديداً.",
      "proposal_angle": "الزاوية التي تميّز العرض.",
      "competition": "أقل من ٥ عروض",
      "score": 88
    }
  ],
  "mostaql": [
    {
      "title": "عنوان المشروع",
      "url": "https://mostaql.com/project/000000",
      "budget": "١٥٠٠–٣٠٠٠ ريال",
      "summary": "...",
      "why_fits": "...",
      "proposal_angle": "...",
      "score": 82
    }
  ]
}
```

## التشغيل

```bash
python scripts/build_workbook.py leads.json --out qannas-2026-08-30.xlsx
python scripts/build_board.py    leads.json --out board.html
```

`build_workbook.py` يحتاج `openpyxl` (مثبّت مسبقاً في بيئة Cowork). `build_board.py` بلا اعتماديات. كلاهما يستورد `qannas_lib.py` من نفس المجلد.

## ما يفعله السكربتان تلقائياً — فلا تفعله يدوياً

- **يحسبان الدرجة الإجمالية** من مكوّنات `score` ويرفضان أي مكوّن يتجاوز حده. لا تكتب `total`.
- **يحدّدان التصنيف** (🔥 HOT / 🟢 HIGH / 🟡 MEDIUM) من المجموع.
- **يرفضان أي فرصة مجموعها أقل من ٧٠** — المواصفة تمنع إدراجها.
- **يرتّبان** الفرص والمشاريع تنازلياً بالدرجة، ويرقّمان الفرص بعد الترتيب.
- **يملآن** الحقول الناقصة بـ `Unable to verify` بدل تركها فارغة.

## الحقول المطلوبة

لكل فرصة: `company` · `country` · `industry` · `website` · `primary_opportunity` · `recommended_service` · `message` · `audit` · `score`.
لكل مشروع: `title` · `url` · `score`.

أي حقل مطلوب ناقص يوقف البناء برسالة تسمّي الشركة والحقل — أفضل من ملف يخرج بخانة فارغة تُرسل كما هي.

## أي حقل يظهر أين

| الحقل | Excel | صفحة الويب |
|---|---|---|
| `title` | — | عنوان الصفحة في التبويب والمعرض |
| `headline` · `sub` | — | العنوان الرئيسي والسطر التعريفي |
| `date_ar` · `markets` · `niche` · `dialect` | تبويب المنهجية | التاريخ في الترويسة (`date_ar` فقط) |
| `method` · `limits` · `next_step` | تبويب المنهجية | قسم «كيف اُستخرجت الملاحظات» |
| `projects_note` | تبويب المنهجية | تنبيه أعلى قسم المشاريع |
| `report.*` | تبويب المنهجية | قسم التقرير اليومي |
| `audit.ux` + `audit.ui` | عمود UX/UI Issues | مجموعتان منفصلتان في البطاقة |
| `free_sample` · `opportunities` | — | البطاقة |

كل حقول `meta` اختيارية — السكربتان يستخدمان قيماً افتراضية لما ينقص فلا تتعطل الدفعة. لكن `limits` تحديداً لا تتركه للافتراضي: هو المكان الذي يعرف منه ناصر ما لم يُتحقق منه في هذه الدفعة بالذات.

ارتفاعات الصفوف تُحسب من طول النص، فالفقرات الطويلة تظهر كاملة بلا قص.

## بعد التشغيل

- `SendUserFile` لملف Excel — جاهز للرفع على Google Sheets بأربعة تبويبات.
- `Artifact` لنشر `board.html` — الملف مكتفٍ ذاتياً بلا موارد خارجية عدا خطوط Google.

## اختبار سريع

```bash
python scripts/build_workbook.py examples/sample-leads.json --out /tmp/t.xlsx
python scripts/build_board.py    examples/sample-leads.json --out /tmp/t.html
```

`examples/sample-leads.json` بيانات توضيحية لاختبار السكربتين فقط — أسماء الشركات فيه غير حقيقية ولا تُستخدم في أي دفعة.
