"""Loop Detector – phát hiện vòng lặp sửa lỗi vô hạn.

Chiến lược:
  1. Consecutive: error hash giống nhau N lần liên tiếp → STOP
  2. Cycle: error hash xoay vòng giữa 2-3 lỗi trong M lần → STOP
  3. Plateau: số file modified không tăng trong K lần → STOP
"""
from __future__ import annotations

import hashlib
from collections import Counter
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class LoopState:
    """Internal state cho một error hash."""
    hash: str
    category: str
    message: str
    attempt: int
    root_cause: str = ""


@dataclass
class LoopResult:
    """Kết quả kiểm tra loop."""
    is_looping: bool
    reason: str = ""
    consecutive_count: int = 0
    cycle_length: int = 0
    root_cause_count: int = 0

    @property
    def should_stop(self) -> bool:
        return self.is_looping


class LoopDetector:
    """Phát hiện vòng lặp — dùng hash error message + root cause để detect pattern.

    Chiến lược:
      1. Root Cause (window): cùng root_cause xuất hiện K lần trong window → STOP
      2. Root Cause (counter/session): cùng root_cause xuất hiện E lần xuyên suốt session → ESCALATE
      3. Consecutive: error hash giống nhau N lần liên tiếp → STOP
      4. Cycle: error hash xoay vòng giữa 2-3 lỗi trong M lần → STOP
      5. Plateau: số file modified không tăng trong K lần → STOP

    Root cause counter khác với window check ở chỗ:
    - Window check: chỉ nhìn N lần gần nhất (bỏ sót nếu lỗi trải dài)
    - Counter: đếm xuyên suốt, không reset giữa chừng
    """

    def __init__(
        self,
        max_consecutive: int = 3,
        max_cycle: int = 5,
        max_plateau: int = 6,
        max_root_cause_duplicates: int = 4,
        escalate_root_cause_threshold: int = 5,
    ):
        self.max_consecutive = max_consecutive
        self.max_cycle = max_cycle
        self.max_plateau = max_plateau
        self.max_root_cause_duplicates = max_root_cause_duplicates
        self.escalate_threshold = escalate_root_cause_threshold
        self._history: list[LoopState] = []
        self._plateau_count = 0
        self._last_modified_count = 0
        # Persistent root cause counter — không reset giữa các window
        # Dùng để phát hiện root cause trải dài qua nhiều iteration/file khác nhau
        self._root_cause_counter: dict[str, int] = {}

    # ── Public API ──────────────────────────────────────────────────────

    def record(
        self,
        error_text: str,
        category: str = "",
        attempt: int = 0,
        root_cause: str = "",
    ) -> LoopResult:
        """Ghi nhận một lỗi và kiểm tra loop.

        * root_cause != "" → cập nhật session-wide counter
        * Nếu cùng root_cause xuất hiện >= escalate_threshold lần → ESCALATE (STOP ngay)
        """
        h = self._hash(error_text)

        state = LoopState(hash=h, category=category, message=error_text[:100], attempt=attempt, root_cause=root_cause)
        self._history.append(state)

        # Chỉ giữ 20 entry gần nhất
        if len(self._history) > 20:
            self._history = self._history[-20:]

        # ── Session-wide root cause counter ──────────────────────────────
        if root_cause and root_cause not in ("", "unknown", "unrecognized"):
            self._root_cause_counter[root_cause] = self._root_cause_counter.get(root_cause, 0) + 1
            rc_total = self._root_cause_counter[root_cause]
            if rc_total >= self.escalate_threshold:
                return LoopResult(
                    is_looping=True,
                    reason=f"ESCALATION — Root cause '{root_cause}' xuất hiện {rc_total} lần xuyên suốt session. "
                           f"AI đang lặp lại cùng loại lỗi ở các file khác nhau.",
                    root_cause_count=rc_total,
                )

        return self._check()

    def record_modified_count(self, count: int) -> Optional[LoopResult]:
        """Ghi nhận số lượng file đã modified — detect plateau.
        Bắt đầu đếm ngay khi count KHÔNG thay đổi so với lần trước.
        max_plateau=3 → cảnh báo sau 3 lần modified_count không tăng.
        """
        if self._last_modified_count > 0 and count == self._last_modified_count:
            self._plateau_count += 1
        else:
            self._plateau_count = 0
        self._last_modified_count = count

        if self._plateau_count >= self.max_plateau:
            return LoopResult(
                is_looping=True,
                reason=f"File modified count không tăng sau {self._plateau_count} lần — stalled.",
                consecutive_count=self._plateau_count,
            )
        return None

    def reset(self) -> None:
        """Reset toàn bộ state (khi chuyển task)."""
        self._history.clear()
        self._plateau_count = 0
        self._last_modified_count = 0
        self._root_cause_counter.clear()

    @property
    def total_attempts(self) -> int:
        return len(self._history)

    # ── Internal ────────────────────────────────────────────────────────

    def _check(self) -> LoopResult:
        """Kiểm tra 4 điều kiện và trả về kết quả."""
        if len(self._history) < 2:
            return LoopResult(is_looping=False)

        # 1. Root Cause: cùng root_cause xuất hiện quá nhiều lần (kiểm tra trước vì
        #    quan trọng nhất — gom lỗi khác hash nhưng cùng gốc)
        rc_count = self._check_root_cause()
        if rc_count >= self.max_root_cause_duplicates:
            last_rc = self._history[-1].root_cause or self._history[-1].category
            return LoopResult(
                is_looping=True,
                reason=f"Cùng root cause '{last_rc}' xuất hiện {rc_count} lần — AI đang sửa sai hướng.",
                root_cause_count=rc_count,
            )

        # 2. Consecutive: N lần cuối cùng hash giống nhau
        consecutive = self._check_consecutive()
        if consecutive >= self.max_consecutive:
            return LoopResult(
                is_looping=True,
                reason=f"Lỗi lặp lại {consecutive} lần liên tiếp — AI không tự sửa được.",
                consecutive_count=consecutive,
            )

        # 3. Cycle: 2-3 hash xoay vòng trong M lần gần nhất
        cycle_len = self._check_cycle()
        if cycle_len > 0:
            return LoopResult(
                is_looping=True,
                reason=f"Lỗi xoay vòng giữa {cycle_len} lỗi khác nhau trong {self.max_cycle} lần — AI đang sửa lung tung.",
                cycle_length=cycle_len,
            )

        return LoopResult(is_looping=False)

    def _check_consecutive(self) -> int:
        """Đếm số lần hash giống nhau liên tiếp từ cuối."""
        if not self._history:
            return 0
        last_hash = self._history[-1].hash
        count = 0
        for state in reversed(self._history):
            if state.hash == last_hash:
                count += 1
            else:
                break
        return count

    def _check_cycle(self) -> int:
        """Kiểm tra xem M lần gần nhất có xoay vòng giữa 2-3 hash không."""
        recent = self._history[-self.max_cycle:]
        if len(recent) < self.max_cycle:
            return 0

        hashes = [s.hash for s in recent]
        unique = set(hashes)

        # 2-3 hash khác nhau nhưng lặp lại tuần hoàn
        if 2 <= len(unique) <= 3:
            # Kiểm tra: mỗi hash xuất hiện ít nhất 2 lần trong window
            counts = Counter(hashes)
            if all(c >= 2 for c in counts.values()):
                return len(unique)
        return 0

    def _check_root_cause(self) -> int:
        """Đếm số lần cùng root_cause xuất hiện trong history window.
        Gom các lỗi hash khác nhau nhưng cùng gốc (ví dụ: missing package → import A, import B).
        """
        recent = self._history[-self.max_root_cause_duplicates * 3:]
        if len(recent) < 2:
            return 0
        # Dùng root_cause nếu có, fallback về category nếu root_cause rỗng
        keys = [s.root_cause or s.category for s in recent if s.root_cause or s.category]
        if len(keys) < 2:
            return 0
        counts = Counter(keys)
        # Bỏ qua UNKNOWN root cause — không đủ tin cậy để gom
        unknown_keys = {k for k in counts if "unrecognized" in k.lower() or "unknown" in k.lower()}
        for k in unknown_keys:
            del counts[k]
        if not counts:
            return 0
        # Trả về số lần xuất hiện nhiều nhất
        most_common = counts.most_common(1)[0][1]
        return most_common

    @staticmethod
    def _hash(text: str) -> str:
        """Hash error message để so sánh (bỏ qua số dòng, số byte cụ thể)."""
        # Normalize: xoá số, đường dẫn tuyệt đối
        cleaned = re.sub(r'\d+', '0', text)
        cleaned = re.sub(r'[A-Za-z]:\\.+?\\', '', cleaned)
        cleaned = cleaned.strip().lower()[:200]
        return hashlib.md5(cleaned.encode()).hexdigest()[:12]


import re  # noqa: E402 (needed by _hash)
