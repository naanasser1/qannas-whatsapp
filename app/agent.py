"""تشغيل أجينت قناص عبر Claude Agent SDK، مع بث تقدّم مختصر إلى واتساب."""

from __future__ import annotations

import asyncio
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Awaitable, Callable

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    SystemMessage,
    TextBlock,
    ToolUseBlock,
    query,
)

from . import config, store

log = logging.getLogger(__name__)

# ما يظهر للمستخدم عند كل أداة — بلغة يفهمها بدل أسماء الأدوات الإنجليزية
TOOL_LABELS = {
    "WebSearch": "أبحث عن متاجر ومشاريع",
    "WebFetch": "أفتح موقع متجر وأفحص محتواه",
    "Read": "أقرأ مراجع المهارة",
    "Write": "أكتب بيانات الدفعة",
    "Edit": "أعدّل بيانات الدفعة",
    "Bash": "أبني ملف الإكسل وصفحة الويب",
    "Glob": "أرتّب ملفات المخرجات",
    "Grep": "أراجع الملاحظات",
    "Skill": "أشغّل مهارة قناص",
    "Task": "أوزّع البحث على مساعدين",
}

# امتدادات المخرجات التي تستحق أن تُرسل كملف على واتساب
DELIVERABLE_SUFFIXES = {".xlsx", ".xls", ".csv", ".html", ".pdf", ".docx", ".pptx"}

APPEND_PROMPT = """
أنت تعمل الآن كأجينت قناص عبر واتساب. التزم بالتالي:

مجلد العمل لهذه الدفعة هو: {run_dir}
اكتب كل الملفات — leads.json وملف الإكسل وصفحة الويب — داخل هذا المجلد بالضبط.
لا تكتب أي ملف خارجه.

مجلد المهارة (فيه references و scripts و assets) هو: {skill_dir}
استخدم مسارات كاملة عند تشغيل السكربتات، مثال:
  python {skill_dir}/scripts/build_workbook.py {run_dir}/leads.json --out {run_dir}/leads.xlsx
  python {skill_dir}/scripts/build_board.py    {run_dir}/leads.json --out {run_dir}/board.html

أدوات SendUserFile و Artifact غير متاحة هنا. لا تحاول استدعاءها.
الملفات التي تنشئها داخل مجلد الدفعة تُرسل تلقائياً إلى واتساب بعد انتهائك.

القناة واتساب، لذلك اجعل ردك النهائي نصاً عربياً صرفاً:
- بدون جداول ماركداون وبدون عناوين بعلامة #، فواتساب لا يعرضها.
- استخدم أسطراً قصيرة، والتشكيل المسموح فقط: *عريض* و_مائل_.
- الرد النهائي هو ما سيقرأه ناصر على جواله: ابدأ بخلاصة من سطرين،
  ثم أهم النقاط، ثم توصيتك بأي متجرين يبدأ، ثم القيود بصراحة.
- تاريخ اليوم: {today}
"""


@dataclass
class AgentResult:
    """نتيجة تشغيل واحد لقناص."""

    text: str = ""
    files: list[Path] = field(default_factory=list)
    session_id: str | None = None
    cost_usd: float = 0.0
    turns: int = 0
    is_error: bool = False
    error_note: str = ""


def _new_run_dir(wa_id: str) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    path = config.RUNS_DIR / wa_id / stamp
    path.mkdir(parents=True, exist_ok=True)
    return path


def _collect_deliverables(run_dir: Path) -> list[Path]:
    """يجمع الملفات القابلة للإرسال من مجلد الدفعة، الأحدث أولاً."""
    found = [
        p
        for p in run_dir.rglob("*")
        if p.is_file() and p.suffix.lower() in DELIVERABLE_SUFFIXES
    ]
    found.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return found


def _build_options(run_dir: Path, resume_id: str | None) -> ClaudeAgentOptions:
    skill_dir = config.SKILLS_DIR / "qannas"
    append = APPEND_PROMPT.format(
        run_dir=run_dir,
        skill_dir=skill_dir,
        today=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
    )

    return ClaudeAgentOptions(
        cwd=str(config.AGENT_HOME),
        # "project" ضرورية كي يكتشف الـ SDK مجلد .claude/skills داخل cwd
        setting_sources=["project"],
        skills="all",
        system_prompt={"type": "preset", "preset": "claude_code", "append": append},
        allowed_tools=[
            "Skill", "Read", "Write", "Edit", "Bash",
            "Glob", "Grep", "WebSearch", "WebFetch", "TodoWrite",
        ],
        permission_mode=config.PERMISSION_MODE,
        max_turns=config.MAX_TURNS,
        max_budget_usd=config.MAX_BUDGET_USD,
        model=config.AGENT_MODEL,
        resume=resume_id,
        # مفتاح الإعدادات يجب أن يتغلّب على البيئة، لا العكس
        env={**os.environ, "ANTHROPIC_API_KEY": config.ANTHROPIC_API_KEY},
    )


async def run_qannas(
    wa_id: str,
    prompt: str,
    on_progress: Callable[[str], Awaitable[None]],
) -> AgentResult:
    """
    يشغّل قناص على طلب واحد ويرجع النتيجة.

    on_progress: دالة تُستدعى بتحديثات قصيرة أثناء التنفيذ (مقيّدة بالوقت
    داخلياً حتى لا تتحول المحادثة إلى سيل إشعارات).
    """
    run_dir = _new_run_dir(wa_id)
    resume_id = store.get_session(wa_id)
    options = _build_options(run_dir, resume_id)

    result = AgentResult()
    texts: list[str] = []
    last_progress = 0.0
    last_label = ""

    async def maybe_progress(label: str) -> None:
        nonlocal last_progress, last_label
        now = time.monotonic()
        if label == last_label or now - last_progress < config.PROGRESS_INTERVAL_SEC:
            return
        last_progress, last_label = now, label
        try:
            await on_progress(f"⏳ {label}…")
        except Exception as exc:
            log.warning("تعذّر إرسال تحديث التقدّم: %s", exc)

    try:
        async for message in query(prompt=prompt, options=options):
            if isinstance(message, SystemMessage):
                if message.subtype == "init":
                    sid = message.data.get("session_id")
                    if sid:
                        result.session_id = sid

            elif isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock) and block.text.strip():
                        texts.append(block.text)
                    elif isinstance(block, ToolUseBlock):
                        label = TOOL_LABELS.get(block.name)
                        if label:
                            await maybe_progress(label)

            elif isinstance(message, ResultMessage):
                result.session_id = message.session_id or result.session_id
                result.cost_usd = message.total_cost_usd or 0.0
                result.turns = message.num_turns or 0
                result.is_error = message.is_error
                if message.result:
                    texts.append(message.result)
                if message.subtype == "error_max_turns":
                    result.error_note = "توقفت عند سقف عدد الخطوات. أرسل «كمّل» لأتابع."
                elif message.subtype == "error_max_budget_usd":
                    result.error_note = (
                        f"توقفت عند سقف التكلفة ({config.MAX_BUDGET_USD}$). "
                        "ارفع AGENT_MAX_BUDGET_USD أو أرسل «كمّل»."
                    )

    except asyncio.CancelledError:
        raise
    except Exception as exc:
        log.exception("فشل تشغيل قناص لـ %s", wa_id)
        result.is_error = True
        result.error_note = f"خطأ أثناء التشغيل: {type(exc).__name__}: {exc}"

    # الرد النهائي من ResultMessage قد يكرر آخر نص من المساعد — نزيل التكرار
    deduped: list[str] = []
    for chunk in texts:
        cleaned = chunk.strip()
        if cleaned and (not deduped or cleaned != deduped[-1]):
            deduped.append(cleaned)
    # نأخذ آخر مقطعين فقط: الخلاصة النهائية عادةً في آخر الرد
    result.text = "\n\n".join(deduped[-2:]) if deduped else ""

    result.files = _collect_deliverables(run_dir)

    if result.session_id:
        store.save_session(wa_id, result.session_id)

    return result
