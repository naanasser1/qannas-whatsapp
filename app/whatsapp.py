"""عميل WhatsApp Cloud API — إرسال نص، رفع ملف، إرسال مستند."""

from __future__ import annotations

import logging
import mimetypes
from pathlib import Path

import httpx

from . import config

log = logging.getLogger(__name__)

_TIMEOUT = httpx.Timeout(connect=10.0, read=120.0, write=120.0, pool=10.0)


def _headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {config.ACCESS_TOKEN}"}


def split_message(text: str, limit: int = config.MAX_BODY_CHARS) -> list[str]:
    """
    يقسّم نصاً طويلاً إلى رسائل بحجم يقبله واتساب.

    يقطع عند فاصل فقرة إن وُجد، ثم عند سطر، ثم عند مسافة — حتى لا تنقطع
    الرسالة في منتصف كلمة عربية.
    """
    text = text.strip()
    if not text:
        return []
    if len(text) <= limit:
        return [text]

    parts: list[str] = []
    while text:
        if len(text) <= limit:
            parts.append(text)
            break

        window = text[:limit]
        cut = -1
        for sep in ("\n\n", "\n", " "):
            found = window.rfind(sep)
            # نتجنب قطعاً مبكراً جداً ينتج رسائل قصيرة متناثرة
            if found > limit * 0.5:
                cut = found
                break
        if cut == -1:
            cut = limit

        parts.append(text[:cut].strip())
        text = text[cut:].strip()

    return [p for p in parts if p]


async def send_text(to: str, body: str) -> None:
    """يرسل رسالة نصية، ويقسّمها تلقائياً إن كانت طويلة."""
    chunks = split_message(body)
    if not chunks:
        return

    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        for index, chunk in enumerate(chunks):
            # ترقيم الأجزاء حتى يعرف القارئ أن الرسالة متسلسلة
            text = chunk if len(chunks) == 1 else f"({index + 1}/{len(chunks)})\n{chunk}"
            payload = {
                "messaging_product": "whatsapp",
                "recipient_type": "individual",
                "to": to,
                "type": "text",
                "text": {"preview_url": True, "body": text},
            }
            response = await client.post(
                f"{config.GRAPH_URL}/{config.PHONE_NUMBER_ID}/messages",
                headers=_headers(),
                json=payload,
            )
            if response.status_code >= 400:
                log.error("فشل إرسال نص إلى %s: %s %s", to, response.status_code, response.text)
                response.raise_for_status()


async def mark_read(message_id: str) -> None:
    """يعلّم الرسالة كمقروءة — يعطي إشارة بصرية أن قناص استلم الطلب."""
    payload = {
        "messaging_product": "whatsapp",
        "status": "read",
        "message_id": message_id,
    }
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            await client.post(
                f"{config.GRAPH_URL}/{config.PHONE_NUMBER_ID}/messages",
                headers=_headers(),
                json=payload,
            )
    except Exception as exc:  # لا نُفشل المهمة بسبب إشعار قراءة
        log.warning("تعذّر تعليم الرسالة كمقروءة: %s", exc)


async def upload_media(path: Path) -> str | None:
    """يرفع ملفاً إلى واتساب ويرجع معرّفه (media id) الصالح ٣٠ يوماً."""
    if not path.is_file():
        log.warning("ملف غير موجود للرفع: %s", path)
        return None

    size_mb = path.stat().st_size / (1024 * 1024)
    if size_mb > config.MAX_UPLOAD_MB:
        log.warning("الملف %s حجمه %.1fMB — أكبر من حد واتساب", path.name, size_mb)
        return None

    mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"

    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        response = await client.post(
            f"{config.GRAPH_URL}/{config.PHONE_NUMBER_ID}/media",
            headers=_headers(),
            data={"messaging_product": "whatsapp", "type": mime},
            files={"file": (path.name, path.read_bytes(), mime)},
        )
    if response.status_code >= 400:
        log.error("فشل رفع %s: %s %s", path.name, response.status_code, response.text)
        return None
    return response.json().get("id")


async def send_document(to: str, path: Path, caption: str = "") -> bool:
    """يرفع ملفاً ثم يرسله كمستند. يرجع True عند النجاح."""
    media_id = await upload_media(path)
    if not media_id:
        return False

    document: dict[str, str] = {"id": media_id, "filename": path.name}
    if caption:
        document["caption"] = caption[:1020]

    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to,
        "type": "document",
        "document": document,
    }
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        response = await client.post(
            f"{config.GRAPH_URL}/{config.PHONE_NUMBER_ID}/messages",
            headers=_headers(),
            json=payload,
        )
    if response.status_code >= 400:
        log.error("فشل إرسال مستند %s: %s %s", path.name, response.status_code, response.text)
        return False
    return True
