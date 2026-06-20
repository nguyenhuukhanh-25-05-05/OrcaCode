"""Iteration Quality Scoring — ghi điểm mỗi iteration, phát hiện xu hướng giảm.

Khi AI đi sai hướng (score giảm 5+ iteration liên tiếp), cảnh báo sớm
thay vì để AI lãng phí 50+ vòng.
"""
from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass, field
from typing import Optional

from core.services.signal import Signal, Priority

logger = logging.getLogger("orca.score")


@dataclass
class IterationScore:
    """Điểm chất lượng cho một iteration."""
    iteration: int
    build_pass: bool                # Evidence checks pass?
    severity: int = 0               # 0=pass, 1=warn, 2=fail
    semantic_damage_count: int = 0
    semantic_blocked: bool = False
    runtime_error_count: int = 0
    rollback_count: int = 0
    export_removed_count: int = 0
    test_fail_count: int = 0        # Số test failures
    test_total_count: int = 0       # Tổng số test chạy
    perf_regression_count: int = 0  # Số tool bị performance regression
    quality_score: int = 0          # 0-100 từ CodeQualityChecker + DesignReviewer
    # Derived
    score: int = 0                  # 0-100

    def compute(self) -> int:
        """Compute composite score 0-100.

        Base: 100
        - Build fail: -40
        - Per semantic deletion: -15 (max -45)
        - Semantic blocked: -30 (stacked)
        - Per runtime error: -10 (max -30)
        - Per rollback: -50 (major regression)
        - Per export removed: -100 (contract break → 0)
        - Per test failure: -20 (max -60)
        - Per perf regression: -15 (max -30)
        - Quality score (từ code_quality + design_review): blended 50%

        Final = max(0, build_safety_score * 0.5 + quality_score * 0.5)
        """
        s = 100
        if not self.build_pass:
            s -= 40
        s -= min(45, self.semantic_damage_count * 15)
        if self.semantic_blocked:
            s -= 30
        s -= min(30, self.runtime_error_count * 10)
        s -= self.rollback_count * 50
        s -= self.export_removed_count * 100
        s -= min(60, self.test_fail_count * 20)
        s -= min(30, self.perf_regression_count * 15)

        build_safety_score = max(0, s)

        # Quality score (0-100) blended 50/50 with build safety score
        qs = max(0, min(100, self.quality_score))
        self.score = max(0, int(build_safety_score * 0.5 + qs * 0.5))
        return self.score


class IterationScorer:
    """Tracks quality scores across iterations, detects trends.

    Usage:
        scorer = IterationScorer()
        scorer.record(iteration=5, build_pass=True, ...)
        if scorer.trend_warning:
            print(scorer.trend_message)
    """

    def __init__(self, window_size: int = 10):
        self._scores: deque[IterationScore] = deque(maxlen=window_size)
        self._all_scores: list[IterationScore] = []
        self._trend_warning: str = ""
        self._last_trend_notified: str = ""

    # ── Public API ──────────────────────────────────────────────────────

    @property
    def trend_warning(self) -> str:
        return self._trend_warning

    @property
    def last_score(self) -> Optional[IterationScore]:
        if self._all_scores:
            return self._all_scores[-1]
        return None

    @property
    def score_history(self) -> list[int]:
        return [s.score for s in self._all_scores]

    def record(self, score: IterationScore) -> None:
        """Ghi điểm cho một iteration và kiểm tra trend."""
        score.compute()
        self._scores.append(score)
        self._all_scores.append(score)
        self._check_trend()

    def record_simple(self, iteration: int, build_pass: bool,
                      semantic_damage_count: int = 0,
                      semantic_blocked: bool = False,
                      runtime_error_count: int = 0,
                      rollback_count: int = 0,
                      export_removed_count: int = 0,
                      test_fail_count: int = 0,
                      test_total_count: int = 0,
                      perf_regression_count: int = 0,
                      quality_score: int = 0) -> IterationScore:
        """Convenience: record với các metrics đơn giản."""
        s = IterationScore(
            iteration=iteration,
            build_pass=build_pass,
            semantic_damage_count=semantic_damage_count,
            semantic_blocked=semantic_blocked,
            runtime_error_count=runtime_error_count,
            rollback_count=rollback_count,
            export_removed_count=export_removed_count,
            test_fail_count=test_fail_count,
            test_total_count=test_total_count,
            perf_regression_count=perf_regression_count,
            quality_score=quality_score,
        )
        self.record(s)
        return s

    def format_context(self) -> str:
        """Format context string inject vào prompt.

        Ví dụ:
          📊 Iteration quality: 5 gần đây [85, 80, 60, 45, 40] [WARN] DECLINING
        """
        if len(self._all_scores) < 2:
            return ""

        recent = self.score_history[-8:]
        emoji = "[OK]" if recent[-1] >= 80 else "[WARN]" if recent[-1] >= 50 else "🚨"
        parts = [f"{emoji} Iteration quality: {len(self._all_scores)} gần đây {recent}"]

        if self._trend_warning:
            parts.append(f"  {self._trend_warning}")

        last = self.last_score
        if last:
            details = []
            if not last.build_pass:
                details.append("build FAIL")
            if last.semantic_damage_count:
                details.append(f"{last.semantic_damage_count} semantic damage")
            if last.test_fail_count:
                details.append(f"{last.test_fail_count}/{last.test_total_count} tests failed")
            if last.perf_regression_count:
                details.append(f"{last.perf_regression_count}x perf slower")
            if last.rollback_count:
                details.append(f"{last.rollback_count} rollbacks")
            if last.export_removed_count:
                details.append(f"{last.export_removed_count} export removals")
            if last.quality_score and last.quality_score < 80:
                details.append(f"quality={last.quality_score}")
            if details:
                parts.append(f"  Last score={last.score}: {', '.join(details)}")

        return "\n".join(parts)

    # ── Internal ────────────────────────────────────────────────────────

    def to_signals(self) -> list[Signal]:
        """Convert current state → Signal objects.

        Detector chỉ cung cấp category + observation + evidence_level + confidence.
        Priority do SignalRanker gán.
        """
        signals: list[Signal] = []
        if len(self._all_scores) < 2:
            return signals

        recent = list(self._scores)
        scores = [s.score for s in recent]
        last = self.last_score

        # Build failures
        if last and not last.build_pass:
            signals.append(Signal(
                category="build",
                evidence_level=2,
                observation=f"Build failed at iteration {last.iteration}",
                confidence=1.0,
                severity_hint=1.0,
            ))

        # Semantic damage (export removed → critical, regular changes → high)
        if last and last.semantic_damage_count:
            is_export_break = last.export_removed_count > 0
            signals.append(Signal(
                category="semantic",
                evidence_level=1,
                observation=f"Symbols changed/deleted: {last.semantic_damage_count}" +
                    (f" ({last.export_removed_count} export removed)" if is_export_break else ""),
                confidence=0.9,
                severity_hint=1.0 if is_export_break else 0.7,
            ))

        # Test failures
        if last and last.test_fail_count:
            signals.append(Signal(
                category="test",
                evidence_level=2,
                observation=f"Test failures: {last.test_fail_count}/{last.test_total_count}",
                confidence=1.0,
                severity_hint=0.9,
            ))

        # Rollback
        if last and last.rollback_count:
            signals.append(Signal(
                category="rollback",
                evidence_level=2,
                observation=f"Rollback occurred at iteration {last.iteration}",
                confidence=1.0,
                severity_hint=1.0,
            ))

        # Trend DOWN
        if len(scores) >= 5:
            decreases = sum(1 for i in range(len(scores)-4, len(scores)) if scores[i] < scores[i-1])
            drop = scores[-5] - scores[-1]
            if decreases >= 3 and drop >= 20:
                signals.append(Signal(
                    category="iteration",
                    evidence_level=0,
                    observation=f"Scores decreasing: {scores[-5]} → {scores[-1]} in 5 iterations",
                    confidence=0.8,
                    severity_hint=0.6,
                ))

        return signals

    def _check_trend(self) -> None:
        """Check 3 patterns:
        1. DECLINING: trong 5 iteration gần đây, score giảm 3+ lần và giảm >=20 so với đầu
        2. FLATLINE: score dưới 50 trong >=5 iteration, range <=15
        3. RECOVERING: đang hồi phục (tăng 2+ liên tiếp)
        """
        if len(self._scores) < 3:
            return

        recent = list(self._scores)
        scores = [s.score for s in recent]
        decreases = 0

        # 1. Declining: trong 5 gần đây, >=3 decreases và giảm >=20 so với 5 iter trước
        if len(scores) >= 5:
            decreases = sum(1 for i in range(len(scores)-4, len(scores)) if scores[i] < scores[i-1])
            drop = scores[-5] - scores[-1]
            if decreases >= 3 and drop >= 20 and scores[-1] < 80:
                self._set_warning(
                    f"QUALITY DECLINING: score giam {drop} diem trong 5 iteration "
                    f"({scores[-5]} to {scores[-1]}). Can doi huong tiep can!"
                )
                return

        # 2. Flatline (score < 50 for 5+ iterations, no meaningful change)
        if len(scores) >= 5 and all(s < 50 for s in scores[-5:]):
            lowest = min(scores[-5:])
            highest = max(scores[-5:])
            if highest - lowest <= 15:
                self._set_warning(
                    f"QUALITY STUCK: score duoi 50 trong {len(scores[-5:])} iteration "
                    f"(range {lowest}-{highest}). Can thay doi chien luoc!"
                )
                return

        # 3. Recovering: 3+ increases
        if len(scores) >= 3 and scores[-1] > scores[-2] > scores[-3]:
            self._clear_warning()
            return

        # 4. No concerning trend
        if decreases < 2:
            self._clear_warning()

    def _set_warning(self, msg: str) -> None:
        if msg != self._last_trend_notified:
            self._trend_warning = msg
            logger.warning("IterationScorer: %s", msg)

    def _clear_warning(self) -> None:
        self._trend_warning = ""
