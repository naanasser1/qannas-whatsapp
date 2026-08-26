"""
اختبار محلي بدون واتساب وبدون Anthropic — يتحقق من الأساسيات:
التوقيع، التحقق من الويبهوك، الأرقام المسموحة، تقسيم الرسائل، وأوامر التحكم.

    python test_local.py
"""

import hashlib
import hmac
import json
import os
import sys
import tempfile

# نضبط بيئة وهمية قبل استيراد التطبيق
os.environ.setdefault("WHATSAPP_PHONE_NUMBER_ID", "111111111")
os.environ.setdefault("WHATSAPP_ACCESS_TOKEN", "test-token")
os.environ.setdefault("WHATSAPP_VERIFY_TOKEN", "my-verify-token")
os.environ.setdefault("WHATSAPP_APP_SECRET", "my-app-secret")
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-test")
os.environ.setdefault("ALLOWED_NUMBERS", "966500000001, +966-50-000-0002")
os.environ.setdefault("DB_PATH", os.path.join(tempfile.mkdtemp(), "test.db"))

from starlette.testclient import TestClient  # noqa: E402

from app import config, main, security, store, whatsapp  # noqa: E402

client = TestClient(main.app)
sent: list[tuple[str, str]] = []
passed = failed = 0


def check(name: str, condition: bool) -> None:
    global passed, failed
    if condition:
        passed += 1
        print(f"  ✓ {name}")
    else:
        failed += 1
        print(f"  ✗ {name}")


async def fake_send_text(to: str, body: str) -> None:
    sent.append((to, body))


async def fake_mark_read(_: str) -> None:
    return None


# نعترض النداءات الشبكية حتى لا يخرج الاختبار للإنترنت
main.whatsapp.send_text = fake_send_text
main.whatsapp.mark_read = fake_mark_read


def sign(body: bytes) -> str:
    digest = hmac.new(config.APP_SECRET.encode(), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def webhook_payload(text: str, sender: str = "966500000001", msg_id: str = "wamid.1") -> dict:
    return {
        "object": "whatsapp_business_account",
        "entry": [{
            "id": "0",
            "changes": [{
                "field": "messages",
                "value": {
                    "messaging_product": "whatsapp",
                    "messages": [{
                        "from": sender,
                        "id": msg_id,
                        "type": "text",
                        "text": {"body": text},
                    }],
                },
            }],
        }],
    }


def post(payload: dict, *, valid_signature: bool = True):
    body = json.dumps(payload).encode()
    header = sign(body) if valid_signature else "sha256=deadbeef"
    return client.post(
        "/webhook",
        content=body,
        headers={"x-hub-signature-256": header, "content-type": "application/json"},
    )


print("\n▸ تحقق الويبهوك (GET)")
ok = client.get("/webhook", params={
    "hub.mode": "subscribe", "hub.verify_token": "my-verify-token", "hub.challenge": "12345",
})
check("التوكن الصحيح يرجع التحدي", ok.status_code == 200 and ok.text == "12345")
bad = client.get("/webhook", params={
    "hub.mode": "subscribe", "hub.verify_token": "wrong", "hub.challenge": "12345",
})
check("التوكن الخاطئ يُرفض بـ 403", bad.status_code == 403)

print("\n▸ التحقق من التوقيع")
body = b'{"test":1}'
check("التوقيع الصحيح يمر", security.verify_signature(body, sign(body)))
check("التوقيع الخاطئ يُرفض", not security.verify_signature(body, "sha256=abc"))
check("غياب الترويسة يُرفض", not security.verify_signature(body, None))
check("طلب بتوقيع خاطئ يرجع 403", post(webhook_payload("مساعدة"), valid_signature=False).status_code == 403)

print("\n▸ الأرقام المسموحة")
check("الرقم المسجّل مسموح", security.is_allowed("966500000001"))
check("الرقم بصيغة +966-50 يُطبّع ويُقبل", security.is_allowed("+966-50-000-0002"))
check("رقم غريب مرفوض", not security.is_allowed("14155550000"))

print("\n▸ تقسيم الرسائل الطويلة")
long_text = ("سطر عربي طويل نسبياً لاختبار التقسيم. " * 400).strip()
parts = whatsapp.split_message(long_text)
check("النص الطويل انقسم لأكثر من رسالة", len(parts) > 1)
check("كل جزء ضمن الحد", all(len(p) <= config.MAX_BODY_CHARS for p in parts))
check("ما ضاع نص", sum(len(p.replace(" ", "")) for p in parts) == len(long_text.replace(" ", "")))
check("النص القصير يبقى رسالة واحدة", whatsapp.split_message("مرحبا") == ["مرحبا"])
check("النص الفارغ يرجع لا شيء", whatsapp.split_message("   ") == [])

print("\n▸ الأوامر ومنع التكرار")
sent.clear()
check("أمر مساعدة يرد", post(webhook_payload("مساعدة", msg_id="wamid.help")).status_code == 200 and any("قناص" in b for _, b in sent))

sent.clear()
post(webhook_payload("مساعدة", msg_id="wamid.dup"))
first = len(sent)
post(webhook_payload("مساعدة", msg_id="wamid.dup"))
check("الرسالة المكررة تُتجاهل", len(sent) == first)

sent.clear()
post(webhook_payload("الحالة", msg_id="wamid.status"))
check("أمر الحالة يرد", any("شغال" in b for _, b in sent))

sent.clear()
post(webhook_payload("إلغاء", msg_id="wamid.cancel"))
check("أمر الإلغاء يرد بلا مهمة شغالة", any("ما فيه شي شغال" in b for _, b in sent))

sent.clear()
post(webhook_payload("دفعة اليوم", sender="14155550000", msg_id="wamid.intruder"))
check("رقم غير مصرّح لا يستقبل أي رد", sent == [])

print("\n▸ الفحص الصحي")
health = client.get("/health").json()
check("لا توجد إعدادات ناقصة", health["missing_settings"] == [])

print("\n▸ المسار الكامل (بأجينت وهمي)")
import asyncio  # noqa: E402
from pathlib import Path  # noqa: E402

from app import agent as agent_mod  # noqa: E402

docs_sent: list[Path] = []


async def fake_run_qannas(wa_id, prompt, on_progress):
    await on_progress("أبحث عن متاجر")
    tmp = Path(tempfile.mkdtemp())
    xlsx = tmp / "leads.xlsx"
    xlsx.write_bytes(b"PK\x03\x04fake")
    return agent_mod.AgentResult(
        text="خلصت الدفعة. أنصحك تبدأ بمتجرين.",
        files=[xlsx],
        session_id="sess-123",
        cost_usd=0.42,
        turns=7,
    )


async def fake_send_document(to, path, caption=""):
    docs_sent.append(path)
    return True


main.agent.run_qannas = fake_run_qannas
main.whatsapp.send_document = fake_send_document


async def full_flow():
    sent.clear()
    docs_sent.clear()
    wa = "966500000001"
    main._queues[wa] = asyncio.Queue()
    await main._queues[wa].put("دفعة اليوم")
    worker = asyncio.create_task(main._worker(wa))
    await main._queues[wa].join()
    worker.cancel()
    bodies = [b for _, b in sent]
    check("وصل تحديث تقدّم", any("أبحث عن متاجر" in b for b in bodies))
    check("وصل النص النهائي", any("خلصت الدفعة" in b for b in bodies))
    check("أُرسل ملف الإكسل", len(docs_sent) == 1 and docs_sent[0].name == "leads.xlsx")
    check("انتهى الطابور فاضياً", main._queues[wa].empty())
    check("تحرّر قفل التشغيل", wa not in main._running)


asyncio.run(full_flow())

print("\n▸ حفظ واسترجاع الجلسة")
store.save_session("966500000001", "sess-abc")
check("الجلسة تُحفظ وتُسترجع", store.get_session("966500000001") == "sess-abc")
store.clear_session("966500000001")
check("أمر «جديد» يمسح الجلسة", store.get_session("966500000001") is None)

print(f"\n{'─' * 44}\nنجح: {passed}   فشل: {failed}\n")
sys.exit(1 if failed else 0)
