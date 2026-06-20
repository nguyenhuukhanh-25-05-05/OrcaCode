"""Graduated context pruning — soft trim → hard prune → smart compaction.

Learns from MiMo's approach:
- Level 1: Soft-trim long tool outputs (head + "[...trimmed...]" + tail)
- Level 2: Hard-prune old outputs (replace with compacted placeholder)
- Level 3: Full compaction (extract key info from old history, keep recent turns)

Each level is strictly more aggressive than the previous, and each preserves
recent conversation turns intact so long-running tasks don't lose context.
"""

import logging
import re
from typing import Optional

logger = logging.getLogger("orca.pruner")

SOFT_TRIM_THRESHOLD = 4096       # Min chars before considering for trim
SOFT_TRIM_KEEP_HEAD = 1536       # Chars to keep from start
SOFT_TRIM_KEEP_TAIL = 1024       # Chars to keep from end
HARD_PRUNE_KEEP_TURNS = 6        # Full-resolution turns to keep during hard prune
COMPACT_KEEP_TURNS = 4           # Turns to keep after full compaction (long task safety)


def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // 3)


def _is_tool_output(msg: dict) -> bool:
    """Check if message is a long tool output that could benefit from trimming."""
    content = msg.get("content", "")
    return len(content) > SOFT_TRIM_THRESHOLD


def soft_trim_tool_outputs(messages: list[dict],
                           keep_head: int = SOFT_TRIM_KEEP_HEAD,
                           keep_tail: int = SOFT_TRIM_KEEP_TAIL) -> list[dict]:
    """Level 1: Truncate old tool outputs to head+tail with placeholder.
    
    Only affects messages older than the last 2 user-assistant exchanges.
    System messages preserved intact.
    """
    if len(messages) <= 6:
        return messages

    protect_start = _compute_protect_boundary(messages, min_protect=6)
    trimmed = []

    for i, msg in enumerate(messages):
        if i >= protect_start or msg.get("role") == "system":
            trimmed.append(msg)
            continue

        content = msg.get("content", "")
        if not _is_tool_output(msg):
            trimmed.append(msg)
            continue

        head = content[:keep_head]
        body_len = len(content)
        tail = content[-keep_tail:] if keep_tail > 0 else ""
        trimmed.append({
            "role": msg.get("role", "user"),
            "content": f"{head}\n\n[... trimmed ({body_len} → {keep_head + keep_tail} chars) ...]\n\n{tail}"
        })

    logger.info("soft_trim: %d → %d messages (trimmed %d long outputs)",
                len(messages), len(trimmed), len(messages) - len(trimmed))
    return trimmed


def hard_prune_old_outputs(messages: list[dict],
                           keep_turns: int = HARD_PRUNE_KEEP_TURNS) -> list[dict]:
    """Level 2: Replace old long messages with compacted placeholders.
    
    Keeps last N user-assistant exchanges full-resolution.
    Older exchanges with content >200 chars get replaced with first 200 chars.
    """
    if len(messages) <= keep_turns * 2 + 2:
        return messages

    protect_start = _compute_protect_boundary(messages, min_protect=keep_turns * 2 + 2)
    pruned = []

    for i, msg in enumerate(messages):
        if i >= protect_start:
            pruned.append(msg)
            continue

        role = msg.get("role", "")
        content = msg.get("content", "")

        if len(content) > 200 and role != "system" and not content.startswith("[Compacted]"):
            preview = content[:200].strip()
            pruned.append({"role": role, "content": f"[Compacted] {preview}..."})
        else:
            pruned.append(msg)

    logger.info("hard_prune: %d → %d messages (pruned old outputs)", len(messages), len(pruned))
    return pruned


def smart_compact(messages: list[dict],
                  keep_turns: int = COMPACT_KEEP_TURNS) -> list[dict]:
    """Level 3: Full conversation compaction.
    
    Extracts key info (files, errors, decisions) from old messages.
    Keeps only recent turns full-resolution. Inserts a compacted system summary.
    """
    if len(messages) <= keep_turns * 2 + 2:
        return messages

    tail = []
    non_system = 0
    for msg in reversed(messages):
        tail.insert(0, msg)
        if msg.get("role") != "system":
            non_system += 1
            if non_system >= keep_turns * 2:
                break

    head = messages[:len(messages) - len(tail)]

    files_mentioned: set[str] = set()
    errors_seen: list[str] = []
    decisions_made: list[str] = []

    for msg in head:
        content = msg.get("content", "")
        role = msg.get("role", "")
        for m in re.finditer(r'(?:^|\s)([\w./\\-]+\.[a-zA-Z]+)(?:\s|$)', content):
            files_mentioned.add(m.group(1))
        if "error" in content.lower() or "fail" in content.lower() or "lỗi" in content.lower():
            errors_seen.append(content[:200].strip())
        if any(kw in content for kw in ("<DONE", "PLAN_APPROVED", "DONE_TAG", "Decision:", "decided", "chose", "switched to")):
            decisions_made.append(content[:200].strip())

    compact_parts = []
    if files_mentioned:
        compact_parts.append(f"Files: {', '.join(sorted(files_mentioned)[:20])}")
    if errors_seen:
        compact_parts.append(f"Errors: {'; '.join(e[:100] for e in errors_seen[:5])}")
    if decisions_made:
        compact_parts.append(f"Decisions: {'; '.join(d[:100] for d in decisions_made[:3])}")

    compact_text = "; ".join(compact_parts) if compact_parts else "Compacted"
    compacted = [
        {"role": "system", "content": f"[Context compacted — {compact_text}]"},
    ]
    compacted.extend(tail)

    logger.info("smart_compact: %d → %d messages (head:%d files, %d errors)",
                len(messages), len(compacted), len(files_mentioned), len(errors_seen))
    return compacted


def compute_pressure_prune(messages: list[dict], level: int) -> Optional[list[dict]]:
    """Dispatch pruning by pressure level. Returns new message list or None if no change."""
    if level <= 0:
        return None
    if level == 1:
        return soft_trim_tool_outputs(messages)
    if level == 2:
        return hard_prune_old_outputs(messages)
    if level >= 3:
        return smart_compact(messages)
    return None


def _compute_protect_boundary(messages: list[dict], min_protect: int = 6) -> int:
    """Find the index after which messages should be protected from pruning.
    
    Walks backward from the end, counting only non-system messages up to min_protect.
    System messages (scratchpad, exec_log, instructions) are always protected
    and don't consume the protected turn budget.
    """
    protected = 0
    for i in range(len(messages) - 1, -1, -1):
        if protected >= min_protect:
            return i + 1
        if messages[i].get("role") != "system":
            protected += 1
    return 0
