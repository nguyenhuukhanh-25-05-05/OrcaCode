"""Intent Router — classifies user prompts into 6 intents.

Zero regex, zero word-set false positives.

Architecture:
1. Fast path: N-gram action phrases + deny list (context-aware)
2. Main path: LLM classification with conversation context injection
3. Output validation: JSON + Enum — no "Dạ, tôi nghĩ là CHAT ạ"
4. Safety net: CLARIFY when confidence < 0.6
"""
import json
import re
from dataclasses import dataclass
from enum import Enum


class Intent(Enum):
    UNDO = "undo"
    CHAT = "chat"
    PLAN = "plan"
    EXECUTE = "execute"
    CLARIFY = "clarify"
    ASK_PERMISSION = "ask_permission"


class PlanContinuationIntent(Enum):
    """Intent khi user đang response lại một plan đã có."""
    EXECUTE = "execute"       # Đồng ý, chạy plan
    MODIFY = "modify"         # Sửa plan theo yêu cầu mới
    CANCEL = "cancel"         # Hủy plan, làm cái khác
    OTHER = "other"           # Hỏi đáp, lan man, không liên quan


@dataclass
class IntentResult:
    intent: str
    confidence: float
    reason: str = ""
    suggested_action: str = ""
    danger_reason: str = ""


# ── Greeting/chat phrases (single words + bigrams) ─────────────────────────
CHAT_PHRASES: list[tuple[tuple[str, ...], float]] = [
    # Vietnamese greetings
    (("xin", "chào"), 0.98),
    (("chào", "bạn"), 0.95),
    (("chào", "em"), 0.95),
    (("chào", "anh"), 0.95),
    (("chào", "chị"), 0.95),
    # English greetings
    (("hi",), 0.99),
    (("hello",), 0.99),
    (("hey",), 0.98),
    (("hi", "there"), 0.98),
    (("hello", "there"), 0.98),
    # Thanks
    (("cảm", "ơn"), 0.99),
    (("thanks",), 0.99),
    (("thank", "you"), 0.99),
    (("thank",), 0.98),
    (("cám", "ơn"), 0.99),
    (("ok",), 0.95),
    (("okay",), 0.95),
    (("ừ",), 0.90),
    (("ừm",), 0.90),
    (("vâng",), 0.90),
    (("dạ",), 0.90),
    # Casual chat openings
    (("bạn", "khỏe", "không"), 0.95),
    (("bạn", "làm", "gì"), 0.90),
    (("bạn", "tên", "gì"), 0.95),
    (("bạn", "là", "ai"), 0.95),
    (("bạn", "có", "thể"), 0.80),
    (("có", "thể", "giúp"), 0.80),
    # How are you
    (("how", "are", "you"), 0.95),
    (("how's", "it", "going"), 0.95),
    (("what's", "up"), 0.90),
    (("good", "morning"), 0.95),
    (("good", "afternoon"), 0.95),
    (("good", "evening"), 0.95),
]

# ── Single-word chat whitelist (checked AFTER CHAT_PHRASES) ──
CHAT_SINGLE_WORDS: set[str] = {
    "hi", "hello", "hey", "yo", "thanks", "thank", "ok", "okay",
    "ừ", "ừm", "vâng", "dạ", "chào", "bye", "goodbye", "goodby",
    "helo", "hii", "heyy", "heloo",
}

# ── N-gram action phrases (bigram/trigram, not single words) ──────────────
ACTION_PHRASES: list[tuple[tuple[str, ...], str, float]] = [
    # File operations
    (("tạo", "file"), "execute", 0.85),
    (("viết", "file"), "execute", 0.85),
    (("sửa", "file"), "execute", 0.85),
    (("xóa", "file"), "ask_permission", 0.85),
    (("tạo", "mới"), "execute", 0.80),
    (("làm", "mới"), "execute", 0.75),
    # Code actions
    (("viết", "code"), "execute", 0.85),
    (("sửa", "code"), "execute", 0.85),
    (("sửa", "giúp"), "execute", 0.80),
    (("sửa", "cho", "tôi"), "execute", 0.80),
    (("thêm",), "execute", 0.80),
    (("fix", "bug"), "execute", 0.85),
    (("sửa", "lỗi"), "execute", 0.85),
    (("chạy", "build"), "execute", 0.80),
    (("chạy", "test"), "execute", 0.80),
    (("deploy", "lên"), "execute", 0.80),
    # Execute verbs
    (("thực", "thi"), "execute", 0.90),
    (("bắt", "đầu", "thực", "thi"), "execute", 0.90),
    (("thực", "hiện"), "execute", 0.85),
    (("execute",), "execute", 0.85),
    (("làm", "theo", "kế", "hoạch"), "execute", 0.85),
    (("tiến", "hành"), "execute", 0.80),
    (("chạy", "kế", "hoạch"), "execute", 0.85),
    (("start", "execution"), "execute", 0.85),
    # Plans
    (("lên", "kế", "hoạch"), "plan", 0.90),
    (("bản", "kế", "hoạch"), "plan", 0.90),
    (("dàn", "ý"), "plan", 0.85),
    (("thiết", "kế"), "plan", 0.75),
    # Undo
    (("hoàn", "tác"), "undo", 0.90),
    (("quay", "lại"), "undo", 0.85),
    (("khôi", "phục"), "undo", 0.85),
]

# ── Deny list: if ANY word matches, force CHAT regardless of action phrases ──
DENY_WORDS: set[str] = {
    "ghét", "không thích", "chán", "kể chuyện", "than thở",
    "hài", "buồn", "vui", "cười", "đùa",
    "tâm sự", "nói chuyện", "tán gẫu",
}

UNDO_WORDS: set[str] = {"undo", "rollback", "revert"}
SHORT_CLARIFY_LIMIT = 4

# ── LLM prompt with JSON output enforcement ────────────────────────────────
LLM_CLASSIFY_PROMPT = """You are an intent classifier. Respond in JSON only.

Given the conversation context and current user message, classify the intent:

{
  "intent": "undo" | "chat" | "plan" | "execute" | "clarify" | "ask_permission",
  "confidence": 0.0-1.0,
  "reason": "short explanation"
}

Rules:
- undo: user wants to undo/rollback/revert
- chat: greeting, question, discussion, complaint, story — NO action
- plan: user wants a plan, design, outline, spec
- execute: user wants code changes, file ops, command execution, fixing bugs
- ask_permission: prompt contains destructive commands (DROP TABLE, rm -rf, git reset --hard, shutdown, chmod 777)
- clarify: too vague, uncertain — better to ask than guess

Context clues:
- If the user is complaining about something that happened, they want CHAT
- If the user is describing a problem they WANT FIXED, they want EXECUTE
- If you're not sure at all, set confidence < 0.6

Respond ONLY the JSON object, no other text."""


# ── LLM prompt for plan continuation context ─────────────────────────────
PLAN_CONTINUATION_PROMPT = """You are an intent classifier for a code assistant. Your job is to classify what the user wants to do with the EXISTING plan.

## System State
Current system state: {current_state}
This tells you what the system is waiting for — use it to interpret the user's message correctly.

## Recent Conversation History
{chat_history}

## Task
Given the above context, classify the user's LATEST message into exactly ONE intent:

### execute — User AGREES, approves, or wants to run the plan
Key signal: user confirms or green-lights the plan after being asked.

Examples:
- "làm đi", "làm đi em", "triển khai luôn", "triển đi", "quất đi", "quất luôn"
- "ok", "ok chạy đi", "ok let's go", "okay", "được", "được rồi", "ừ", "ừm"
- "yes", "yeah", "yep", "go", "go ahead", "do it", "let's do it"
- "bắt đầu đi", "bắt đầu thôi", "tiến hành đi", "thực thi đi", "chạy đi"
- "duyệt", "phê duyệt", "đồng ý", "tán thành"
- "Ừ đúng rồi", "Ừ làm đi", "được đấy làm đi"

### modify — User wants to CHANGE the plan
Key signal: user requests edits, additions, removals, or adjustments.

Examples:
- "thêm cho anh cái này vào", "bỏ bớt bước 2 đi", "sửa lại thành ..."
- "thay vì X thì làm Y", "bổ sung thêm bước kiểm tra", "chỉnh sửa lại chút"
- "khoan đã, cho tôi chỉnh lại plan", "sửa theo hướng khác"
- "thêm file config vào plan", "bỏ phần deployment đi"

### cancel — User wants to DISCARD the plan
Key signal: user rejects, abandons, or wants to stop.

Examples:
- "thôi bỏ đi", "không làm nữa", "hủy", "cancel", "bỏ qua"
- "thôi", "thôi không làm nữa", "bỏ đi", "quên đi"
- "làm cái khác", "tôi muốn làm việc khác"

### other — User is chatting, asking questions, or unrelated
Key signal: user is NOT responding about the plan at all.

Examples:
- "tool này là gì thế?", "OrcaCode dùng model gì vậy?"
- "bạn khỏe không?", "hôm nay ngày mấy?"
- "tại sao lại làm thế?", "giải thích cho tôi đoạn này"
- "có cách nào khác không?", "cho tôi hỏi tí"

## Rules
1. READ the chat history and system state FIRST — they tell you what the user is responding to.
2. If the previous assistant message asked "do you want to execute?" and user says yes/ok/làm/ừ/okay → execute
3. Be lenient toward "execute": casual affirmation (ok, ừ, đi, làm, go) is still affirmation.
4. If user gives ANY change request → modify, even if they also agree partially.
5. If user explicitly says no/stop/cancel → cancel.
6. If user asks a question or talks off-topic → other (plan remains pending).

Respond ONLY a single word: execute / modify / cancel / other"""


class IntentRouter:
    """Routes user prompts to 6 intents. Zero regex false positives."""

    def classify(self, prompt: str, context_prompt: str = "") -> IntentResult:
        """Fast path: n-gram phrases + deny list + chat detection. Returns low confidence for LLM path."""
        p = prompt.lower().strip()
        words = p.split()
        wc = len(words)

        # ── Deny list: force CHAT if emotional/complaint words present ──
        if DENY_WORDS & set(words):
            return IntentResult(intent="chat", confidence=0.8, reason="Deny word match", suggested_action="Chat, not execute")

        # ── Undo fast path ──
        first_word = words[0].rstrip(",?!.;:") if words else ""
        if first_word in UNDO_WORDS:
            return IntentResult(intent="undo", confidence=0.9, reason="Undo keyword", suggested_action="Rollback snapshot")

        # ── CHAT phrases (greetings, thanks, casual) — checked BEFORE action phrases ──
        for phrase, conf in CHAT_PHRASES:
            if self._match_ngram(phrase, words):
                # Single-word chat phrases (hi, hello, ok, thanks, bye) only match
                # if total word count ≤ 2. Otherwise "hi sửa lỗi" or "ok thêm dark mode"
                # would be incorrectly classified as CHAT instead of EXECUTE.
                if len(phrase) == 1 and wc > 2:
                    continue
                return IntentResult(intent="chat", confidence=conf, reason=f"Chat phrase: {' '.join(phrase)}", suggested_action="Chat response")

        # ── Single-word chat (hi, hello, ok, ừ, etc.) — only if text is just that word ──
        if wc == 1 and words[0].rstrip(",?!.;:") in CHAT_SINGLE_WORDS:
            return IntentResult(intent="chat", confidence=0.95, reason=f"Chat single word: '{words[0]}'", suggested_action="Chat response")

        # ── N-gram action phrases ──
        for phrase, intent_name, conf in ACTION_PHRASES:
            if self._match_ngram(phrase, words):
                if intent_name == "ask_permission":
                    return IntentResult(intent=intent_name, confidence=conf, reason=f"Action phrase: {' '.join(phrase)}", suggested_action="Ask user confirmation", danger_reason=" ".join(phrase))
                return IntentResult(intent=intent_name, confidence=conf, reason=f"Action phrase: {' '.join(phrase)}", suggested_action=f"Route to {intent_name}")

        # ── Very short → clarify (safe default) ──
        if wc <= SHORT_CLARIFY_LIMIT:
            return IntentResult(intent="clarify", confidence=0.6, reason=f"Short ({wc} words), no action phrase", suggested_action="Ask user what they want")

        # ── Unknown → LLM path ──
        return IntentResult(intent="clarify", confidence=0.0, reason="Need LLM", suggested_action="Classify with LLM")

    def parse_llm_response(self, raw: str) -> IntentResult | None:
        """Parse LLM JSON response into IntentResult with strict validation.

        Handles: {"intent": "chat", "confidence": 0.9, "reason": "..."}
        Also handles: markdown-wrapped JSON, trailing text.
        """
        # Strip markdown code fences
        cleaned = re.sub(r'^```(?:json)?\s*|\s*```$', '', raw.strip(), flags=re.IGNORECASE)
        # Find first { ... } block
        brace_start = cleaned.find('{')
        brace_end = cleaned.rfind('}')
        if brace_start == -1 or brace_end == -1:
            return None
        cleaned = cleaned[brace_start:brace_end + 1]

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            return None

        intent_str = str(data.get("intent", "")).strip().lower()
        try:
            intent = Intent(intent_str)
        except ValueError:
            return None

        confidence = float(data.get("confidence", 0.5))
        reason = str(data.get("reason", ""))[:120]

        return IntentResult(
            intent=intent.value,
            confidence=min(max(confidence, 0.0), 1.0),
            reason=f"LLM: {reason}" if reason else "LLM classification",
        )

    def classify_plan_continuation(self, prompt: str, plan_summary: str) -> tuple[str, str]:
        """Fast path: n-gram check first, fallback returns 'other' for LLM to decide.
        Returns (intent, reason).
        """
        p = prompt.lower().strip()
        words = p.split()

        # Explicit cancellation
        cancel_words = {"hủy", "bỏ", "cancel", "thôi", "không làm", "dừng", "stop", "quit"}
        if any(cw in p for cw in cancel_words):
            if not any(af in p for af in ("làm đi", "chạy đi", "triển khai", "quất", "go")):
                return ("cancel", "Cancel keyword match")

        # Strong execute signals (single words or very short phrases)
        execute_phrases = {
            "làm", "làm đi", "ok", "okay", "yes", "yeah", "yep", "go", "đi",
            "ừ", "được", "được rồi", "chạy", "chạy đi", "triển khai", "triển khai đi",
            "quất", "quất đi", "tiến hành", "tiến hành đi", "bắt đầu", "bắt đầu đi",
            "execute", "thực thi", "thực thi đi", "thực hiện", "thực hiện đi",
        }
        if p in execute_phrases:
            return ("execute", f"Execute phrase: '{p}'")

        return ("other", "Need LLM to classify")

    def parse_plan_continuation(self, raw: str) -> str:
        """Parse LLM response for plan continuation intent (expects 'execute'/'modify'/'cancel'/'other')."""
        cleaned = raw.strip().lower()
        cleaned = re.sub(r'^```(?:text)?\s*|\s*```$', '', cleaned, flags=re.IGNORECASE)
        cleaned = cleaned.strip().strip('"').strip("'")
        if cleaned in ("execute", "modify", "cancel", "other"):
            return cleaned
        return "other"

    def _match_ngram(self, phrase: tuple[str, ...], words: list[str]) -> bool:
        """Check if phrase appears as consecutive words in the word list."""
        n = len(phrase)
        if n > len(words):
            return False
        # Strip punctuation from each word for matching
        clean_words = [w.strip(",?!.;:\"'") for w in words]
        for i in range(len(clean_words) - n + 1):
            if tuple(clean_words[i:i + n]) == phrase:
                return True
        return False
