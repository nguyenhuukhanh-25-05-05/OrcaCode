"""Benchmark baseline — startup time, import time, memory, and line counts.

Usage:
    python scripts/bench_baseline.py
"""

import time
import tracemalloc
import sys
from pathlib import Path


def measure_import_time():
    """Measure how long it takes to import core.agent (and all deps)."""
    # Clear any cached modules (only for core.*)
    for mod in list(sys.modules.keys()):
        if mod.startswith("core.") or mod == "core":
            del sys.modules[mod]

    tracemalloc.start()
    t0 = time.perf_counter()
    from core.agent import AgentController, AppCallbacks
    t1 = time.perf_counter()
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    return t1 - t0, current, peak


def measure_constructor():
    """Measure AgentController construction (lazy services)."""
    from config.settings import AppConfig, ModelConfig
    from core.agent import AgentController

    cfg = AppConfig(
        model=ModelConfig(provider="openai", model="gpt-4o", api_key="sk-test-bench"),
        project_root=".",
    )

    tracemalloc.start()
    t0 = time.perf_counter()
    agent = AgentController(cfg)
    t1 = time.perf_counter()
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    return t1 - t0, current, peak, agent


def measure_service_access(agent):
    """Measure time to access all 17 services (lazy resolution)."""
    service_names = [
        "context_svc", "checkpoint_svc", "blueprint_svc", "patch_svc",
        "anchor_patcher", "section_parser", "smart_context", "security_svc",
        "session_vm", "patch_vm", "memory", "long_memory", "plugin_svc",
        "debug_svc", "error_pipeline", "file_backup", "structural_validator",
    ]
    times = {}
    for name in service_names:
        t0 = time.perf_counter_ns()
        svc = getattr(agent, name)
        dt = time.perf_counter_ns() - t0
        times[name] = dt
    return times


def count_lines():
    """Count lines per module in the core package."""
    core_dir = Path("core")
    counts = {}
    total = 0
    for pyfile in sorted(core_dir.rglob("*.py")):
        if "__pycache__" in str(pyfile):
            continue
        lines = len(pyfile.read_text(encoding="utf-8").splitlines())
        rel = str(pyfile.relative_to(core_dir))
        counts[rel] = lines
        total += lines
    return counts, total


def main():
    print("=" * 60)
    print("OrcaCode Performance Baseline")
    print("=" * 60)

    # ── 1. Import time ──
    print("\n[1] Import time (core.agent + all deps)")
    dt, mem_current, mem_peak = measure_import_time()
    print(f"    Import duration: {dt*1000:.1f} ms")
    print(f"    Memory (current): {mem_current / 1024:.1f} KB")
    print(f"    Memory (peak):    {mem_peak / 1024:.1f} KB")

    # ── 2. Construction time ──
    print("\n[2] AgentController construction")
    dt, mem_current, mem_peak, agent = measure_constructor()
    print(f"    Construction: {dt*1000:.1f} ms")
    print(f"    Memory (current): {mem_current / 1024:.1f} KB")
    print(f"    Memory (peak):    {mem_peak / 1024:.1f} KB")

    # ── 3. Lazy service access times ──
    print("\n[3] Lazy service access times (first access)")
    times = measure_service_access(agent)
    for name, ns in sorted(times.items()):
        print(f"    {name:25s} {ns/1000:>8.1f} µs")
    print(f"\n    Total lazy time: {sum(times.values())/1000:.1f} µs")

    # ── 4. Line counts ──
    print("\n[4] Line counts by module")
    counts, total = count_lines()
    for path, lines in sorted(counts.items(), key=lambda x: -x[1]):
        print(f"    {path:40s} {lines:>5} lines")
    print(f"    {'-'*48}")
    print(f"    {'TOTAL':40s} {total:>5} lines")

    # ── 5. Async method count ──
    print("\n[5] Async methods in AgentController")
    import inspect
    async_count = 0
    sync_count = 0
    for name, method in inspect.getmembers(agent, inspect.iscoroutinefunction):
        async_count += 1
    for name, method in inspect.getmembers(agent, inspect.ismethod):
        if not inspect.iscoroutinefunction(method):
            sync_count += 1
    print(f"    Async methods: {async_count}")
    print(f"    Sync methods:  {sync_count}")

    # ── 6. Service import status ──
    print("\n[6] Eager vs lazy services")
    eager = [k for k in agent.__dict__ if not k.startswith("_")]
    print(f"    Eagerly resolved (in __dict__): {len(eager)}")
    print(f"    Lazily resolved (via __getattr__): {len(times)}")

    print("\n" + "=" * 60)
    print("Baseline complete. Save this output for comparison.")
    print("=" * 60)


if __name__ == "__main__":
    main()
