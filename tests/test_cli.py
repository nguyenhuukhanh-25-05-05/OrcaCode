"""Test CLI commands."""
import subprocess
import sys
import os

env = os.environ.copy()
env["PYTHONUTF8"] = "1"

tests = [
    ["--help"],
    ["--version"],
    ["version"],
    ["model"],
    ["ls"],
    ["diff"],
]

passed = 0
total = len(tests)
for cmd in tests:
    try:
        result = subprocess.run(
            [sys.executable, "orca.py"] + cmd,
            capture_output=True, encoding="utf-8", errors="replace", timeout=10,
            cwd=os.getcwd(), env=env,
        )
        ok = result.returncode == 0
        status = "OK" if ok else "FAIL"
        output = (result.stdout or "").strip()[:80]
        print(f"  {status} orca.py {' '.join(cmd)}: {output}")
        if ok:
            passed += 1
        else:
            print(f"    err: {(result.stderr or '').strip()[:150]}")
    except subprocess.TimeoutExpired:
        print(f"  TIMEOUT orca.py {' '.join(cmd)}")
    except Exception as e:
        print(f"  ERROR orca.py {' '.join(cmd)}: {e}")

print(f"\nResults: {passed}/{total} passed")