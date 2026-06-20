import ast
from pathlib import Path

files = [
    "orca.py", "config/settings.py",
    "core/__init__.py", "core/models.py", "core/agent.py",
    "core/ui.py", "core/git_repo.py", "core/summarizer.py",
    "core/services/__init__.py", "core/services/context_service.py",
    "core/services/patch_service.py", "core/services/security_service.py",
    "core/viewmodels/__init__.py", "core/viewmodels/session_vm.py",
    "core/viewmodels/patch_vm.py",
    "utils/__init__.py", "utils/diff.py", "utils/normalize.py", "utils/tokenizer.py",
]

errors = []
for f in files:
    path = Path(f)
    if not path.exists():
        errors.append(f)
        print(f"  MISSING: {f}")
    else:
        try:
            ast.parse(path.read_text(encoding="utf-8"))
            print(f"  OK: {f}")
        except SyntaxError as e:
            errors.append(f)
            print(f"  FAIL: {f} - {e}")

if errors:
    print(f"\nERRORS: {len(errors)}")
    exit(1)
print(f"\nAll {len(files)} files OK")
