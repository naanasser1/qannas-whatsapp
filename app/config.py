"""إعدادات التطبيق — كلها تُقرأ من متغيرات البيئة."""

import os
from pathlib import Path


def _clean_number(raw: str) -> str:
    """يحوّل الرقم لصيغة واتساب: أرقام فقط بدون + أو مسافات أو شرطات."""
    return "".join(ch for ch in raw if ch.isdigit())


BASE_DIR = Path(__file__).resolve().parent.parent

# ── واتساب ────────────────────────────────────────────────────────────────
# رقم معرّف المرسل من لوحة Meta ← WhatsApp ← API Setup
PHONE_NUMBER_ID = os.environ.get("WHATSAPP_PHONE_NUMBER_ID", "")
# التوكن الدائم (System User Token) — ليس التوكن المؤقت
ACCESS_TOKEN = os.environ.get("WHATSAPP_ACCESS_TOKEN", "")
# كلمة سر تخترعها أنت وتضعها في نفس الخانة داخل Meta عند إعداد الويبهوك
VERIFY_TOKEN = os.environ.get("WHATSAPP_VERIFY_TOKEN", "")
# App Secret من Meta ← Settings ← Basic — يُستخدم للتحقق من صحة الطلبات
APP_SECRET = os.environ.get("WHATSAPP_APP_SECRET", "")
# انسخ رقم النسخة من مثال curl الظاهر في صفحة API Setup داخل لوحة Meta
GRAPH_VERSION = os.environ.get("GRAPH_API_VERSION", "v23.0")
GRAPH_URL = f"https://graph.facebook.com/{GRAPH_VERSION}"

# ── الأمان ────────────────────────────────────────────────────────────────
# أرقام مسموح لها بتشغيل قناص، مفصولة بفاصلة. مثال: 9665xxxxxxxx,9665yyyyyyyy
ALLOWED_NUMBERS = {
    _clean_number(n) for n in os.environ.get("ALLOWED_NUMBERS", "").split(",") if _clean_number(n)
}

# ── الأجينت ───────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
# اتركه فارغاً ليستخدم الـ SDK نموذجه الافتراضي، أو ضع معرّف نموذج محدد
AGENT_MODEL = os.environ.get("AGENT_MODEL") or None
# bypassPermissions مناسب داخل حاوية معزولة. للتشديد استخدم dontAsk.
PERMISSION_MODE = os.environ.get("PERMISSION_MODE", "bypassPermissions")
MAX_TURNS = int(os.environ.get("AGENT_MAX_TURNS", "120"))
# سقف تكلفة الدفعة الواحدة بالدولار — حماية من مهمة تدور بلا نهاية
MAX_BUDGET_USD = float(os.environ.get("AGENT_MAX_BUDGET_USD", "5"))

AGENT_HOME = Path(os.environ.get("AGENT_HOME", BASE_DIR / "agent_home"))
RUNS_DIR = AGENT_HOME / "runs"
SKILLS_DIR = AGENT_HOME / ".claude" / "skills"

# ── التخزين ───────────────────────────────────────────────────────────────
# على Railway اربط Volume على /data كي تبقى الجلسات بعد إعادة النشر
DB_PATH = Path(os.environ.get("DB_PATH", BASE_DIR / "state.db"))

# ── حدود واتساب ───────────────────────────────────────────────────────────
MAX_BODY_CHARS = 3900          # الحد الفعلي 4096، نترك هامشاً
PROGRESS_INTERVAL_SEC = 90     # لا نرسل تحديث تقدّم أكثر من مرة كل هذه المدة
MAX_UPLOAD_MB = 95             # حد واتساب للمستندات 100MB


def missing_settings() -> list[str]:
    """يرجع أسماء الإعدادات الناقصة — يُستخدم عند الإقلاع وفي /health."""
    required = {
        "WHATSAPP_PHONE_NUMBER_ID": PHONE_NUMBER_ID,
        "WHATSAPP_ACCESS_TOKEN": ACCESS_TOKEN,
        "WHATSAPP_VERIFY_TOKEN": VERIFY_TOKEN,
        "WHATSAPP_APP_SECRET": APP_SECRET,
        "ANTHROPIC_API_KEY": ANTHROPIC_API_KEY,
    }
    missing = [name for name, value in required.items() if not value]
    if not ALLOWED_NUMBERS:
        missing.append("ALLOWED_NUMBERS")
    return missing
