"""سيرفر الويبهوك: يستقبل رسائل واتساب، يشغّل قناص، يرجّع النتائج والملفات."""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Any

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse, Response
from starlette.routing import Route

from . import agent, config, security, store, whatsapp

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
log = logging.getLogger("qannas")

# طابور مستقل لكل رقم، وعامل واحد يخدمه — يمنع تشغيل دفعتين متوازيتين
_queues: dict[str, asyncio.Queue[str]] = {}
_workers: dict[str, asyncio.Task[None]] = {}
_running: dict[str, asyncio.Task[Any]] = {}

HELP_TEXT = """*قناص* — جاهز.

أرسل مثلاً:
• *دفعة اليوم* — الدورة الكاملة: ٥ متاجر + مشاريع مفتوحة + ملف إكسل وصفحة ويب
• *حلل لي هذا المتجر: <رابط>* — فحص متجر واحد فقط
• *اكتب رسالة لهذا المتجر: <رابط>*
• *شوف المشاريع المفتوحة*

أوامر التحكم:
• *جديد* — يبدأ محادثة من الصفر وينسى السياق السابق
• *إلغاء* — يوقف المهمة الشغالة الآن
• *الحالة* — يخبرك إن كان فيه شي شغال
• *مساعدة* — يعرض هذي القائمة"""


@asynccontextmanager
async def lifespan(_: Starlette):
    missing = config.missing_settings()
    if missing:
        log.error("إعدادات ناقصة، السيرفر لن يعمل صح: %s", ", ".join(missing))
    else:
        log.info("قناص جاهز — %d رقم مصرّح له", len(config.ALLOWED_NUMBERS))
    config.RUNS_DIR.mkdir(parents=True, exist_ok=True)
    yield
    for task in list(_workers.values()) + list(_running.values()):
        task.cancel()


async def health(_: Request) -> JSONResponse:
    missing = config.missing_settings()
    return JSONResponse({
        "ok": not missing,
        "missing_settings": missing,
        "graph_version": config.GRAPH_VERSION,
        "busy_numbers": sorted(_running.keys()),
    })


async def verify(request: Request) -> Response:
    """تحقق Meta من ملكية الويبهوك — يُستدعى مرة واحدة عند الإعداد."""
    params = request.query_params
    if (
        config.VERIFY_TOKEN
        and params.get("hub.mode") == "subscribe"
        and params.get("hub.verify_token") == config.VERIFY_TOKEN
    ):
        return PlainTextResponse(params.get("hub.challenge", ""))
    log.warning("فشل تحقق الويبهوك — تأكد من تطابق VERIFY_TOKEN")
    return PlainTextResponse("forbidden", status_code=403)


async def receive(request: Request) -> Response:
    """
    يستقبل الرسائل الواردة.

    Meta تتوقع رد 200 خلال ثوانٍ قليلة وإلا أعادت الإرسال، وقناص يحتاج
    دقائق — لذلك نضع الرسالة في الطابور ونرد فوراً.
    """
    raw = await request.body()

    if not security.verify_signature(raw, request.headers.get("x-hub-signature-256")):
        log.warning("توقيع غير صالح — طلب مرفوض")
        return PlainTextResponse("invalid signature", status_code=403)

    try:
        payload = await request.json()
    except Exception:
        return PlainTextResponse("ok")

    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            for message in value.get("messages", []):
                try:
                    await _handle_incoming(message)
                except Exception:
                    # خطأ في رسالة واحدة يجب ألا يمنع الرد بـ 200
                    log.exception("فشل معالجة رسالة واردة")

    return PlainTextResponse("ok")


async def _handle_incoming(message: dict[str, Any]) -> None:
    wa_id = message.get("from", "")
    message_id = message.get("id", "")

    if not wa_id or not message_id:
        return

    # Meta تعيد إرسال نفس الرسالة عند أي تأخر — نتجاهل المكرر
    if not store.mark_seen(message_id):
        log.info("تجاهل رسالة مكررة %s", message_id)
        return

    if not security.is_allowed(wa_id):
        log.warning("رقم غير مصرّح له حاول التشغيل: %s", wa_id)
        return

    if message.get("type") != "text":
        await whatsapp.send_text(
            wa_id, "أستقبل رسائل نصية فقط حالياً. أرسل *مساعدة* لتشوف الأوامر."
        )
        return

    text = (message.get("text", {}).get("body") or "").strip()
    if not text:
        return

    await whatsapp.mark_read(message_id)

    if await _handle_command(wa_id, text):
        return

    queue = _queues.setdefault(wa_id, asyncio.Queue())
    await queue.put(text)

    worker = _workers.get(wa_id)
    if worker is None or worker.done():
        _workers[wa_id] = asyncio.create_task(_worker(wa_id))

    if wa_id in _running:
        await whatsapp.send_text(
            wa_id, f"استلمت طلبك، بس فيه مهمة شغالة الحين. بالطابور ({queue.qsize()})."
        )
    else:
        await whatsapp.send_text(wa_id, "تمام، بديت. أرسل لك التقدّم أول بأول.")


async def _handle_command(wa_id: str, text: str) -> bool:
    """يعالج أوامر التحكم. يرجع True إذا كان النص أمراً وتم تنفيذه."""
    command = text.strip().lstrip("/").casefold()

    if command in {"مساعدة", "help", "؟", "?"}:
        await whatsapp.send_text(wa_id, HELP_TEXT)
        return True

    if command in {"جديد", "new", "reset", "ابدأ من جديد"}:
        store.clear_session(wa_id)
        await whatsapp.send_text(wa_id, "مسحت السياق. المحادثة الجاية تبدأ من الصفر.")
        return True

    if command in {"إلغاء", "الغاء", "الغِ", "stop", "cancel"}:
        task = _running.get(wa_id)
        if task and not task.done():
            task.cancel()
            await whatsapp.send_text(wa_id, "أوقفت المهمة الشغالة.")
        else:
            await whatsapp.send_text(wa_id, "ما فيه شي شغال حالياً.")
        return True

    if command in {"الحالة", "status"}:
        queue = _queues.get(wa_id)
        pending = queue.qsize() if queue else 0
        busy = wa_id in _running and not _running[wa_id].done()
        await whatsapp.send_text(
            wa_id, f"شغال الآن: {'نعم' if busy else 'لا'}\nبالطابور: {pending}"
        )
        return True

    return False


async def _worker(wa_id: str) -> None:
    """عامل واحد لكل رقم — يسحب من الطابور ويشغّل قناص بالتسلسل."""
    queue = _queues[wa_id]
    while True:
        try:
            prompt = await asyncio.wait_for(queue.get(), timeout=300)
        except asyncio.TimeoutError:
            return  # لا رسائل جديدة، ننهي العامل ونعيد إنشاءه عند الحاجة
        except asyncio.CancelledError:
            return

        task = asyncio.create_task(_run_one(wa_id, prompt))
        _running[wa_id] = task
        try:
            await task
        except asyncio.CancelledError:
            log.info("أُلغيت مهمة %s", wa_id)
        except Exception:
            log.exception("خطأ غير متوقع في مهمة %s", wa_id)
        finally:
            _running.pop(wa_id, None)
            queue.task_done()


async def _run_one(wa_id: str, prompt: str) -> None:
    async def on_progress(note: str) -> None:
        await whatsapp.send_text(wa_id, note)

    result = await agent.run_qannas(wa_id, prompt, on_progress)

    if result.text:
        await whatsapp.send_text(wa_id, result.text)
    elif not result.error_note:
        await whatsapp.send_text(wa_id, "خلصت بس ما طلع نص نهائي. جرّب تعيد الطلب بصيغة أوضح.")

    for path in result.files:
        if not await whatsapp.send_document(wa_id, path):
            await whatsapp.send_text(
                wa_id, f"تعذّر إرسال الملف {path.name} — موجود على السيرفر في {path.parent}."
            )

    if result.error_note:
        await whatsapp.send_text(wa_id, f"⚠️ {result.error_note}")

    log.info(
        "انتهت مهمة %s — %d ملف، %d خطوة، %.3f$",
        wa_id, len(result.files), result.turns, result.cost_usd,
    )


app = Starlette(
    lifespan=lifespan,
    routes=[
        Route("/health", health, methods=["GET"]),
        Route("/webhook", verify, methods=["GET"]),
        Route("/webhook", receive, methods=["POST"]),
    ],
)
