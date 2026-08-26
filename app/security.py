"""التحقق من أن الطلب قادم من Meta فعلاً وليس من أي جهة أخرى."""

import hashlib
import hmac
import logging

from . import config

log = logging.getLogger(__name__)


def verify_signature(raw_body: bytes, header: str | None) -> bool:
    """
    تتحقق من ترويسة X-Hub-Signature-256.

    Meta توقّع جسم الطلب الخام بـ HMAC-SHA256 باستخدام App Secret.
    بدون هذا التحقق يقدر أي شخص يعرف رابط الويبهوك أن يشغّل قناص على حسابك.
    """
    if not config.APP_SECRET:
        log.error("APP_SECRET غير مضبوط — رفض الطلب")
        return False

    if not header or not header.startswith("sha256="):
        return False

    expected = hmac.new(
        config.APP_SECRET.encode("utf-8"),
        raw_body,
        hashlib.sha256,
    ).hexdigest()

    # مقارنة ثابتة الزمن لمنع هجمات التوقيت
    return hmac.compare_digest(expected, header[len("sha256=") :])


def is_allowed(wa_id: str) -> bool:
    """هل هذا الرقم مصرّح له بتشغيل قناص؟"""
    return "".join(ch for ch in wa_id if ch.isdigit()) in config.ALLOWED_NUMBERS
