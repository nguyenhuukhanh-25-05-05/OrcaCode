"""Debug the warning modal interaction."""
import tempfile
from pathlib import Path

# Test 1: PlanReviewModal._on_warning_result logic
print("=== Test 1: Callback logic ===")
from core.tui import AutopilotWarningModal, PlanReviewModal

# Verify the class exists and can be instantiated
print(f"AutopilotWarningModal bases: {AutopilotWarningModal.__bases__}")
print(f"PlanReviewModal bases: {PlanReviewModal.__bases__}")

# Test 2: Check the on_button_pressed method signature
import inspect
src = inspect.getsource(PlanReviewModal.on_button_pressed)
print(f"\nPlanReviewModal.on_button_pressed source:")
# Check for self.app.push_screen
if "self.app.push_screen" in src:
    print("  [OK] Uses self.app.push_screen (correct for ModalScreen)")
elif "self.push_screen" in src:
    print("  [ERROR] Uses self.push_screen (wrong for ModalScreen)")
else:
    print("  [UNEXPECTED] Not found")

if "AutopilotWarningModal" in src:
    print("  [OK] Calls AutopilotWarningModal")
else:
    print("  [ERROR] Does NOT call AutopilotWarningModal")

# Test 3: Check _on_warning_result exists
if hasattr(PlanReviewModal, "_on_warning_result"):
    print("  [OK] _on_warning_result method exists")
    src2 = inspect.getsource(PlanReviewModal._on_warning_result)
    if "self.dismiss" in src2:
        print("  [OK] Calls self.dismiss")
else:
    print("  [ERROR] _on_warning_result NOT FOUND")

# Test 4: Verify AutopilotWarningModal buttons
src3 = inspect.getsource(AutopilotWarningModal.on_button_pressed)
if "btn-warning-agree" in src3 and "btn-warning-back" in src3:
    print("  [OK] Both buttons handled")
if "self.dismiss(True)" in src3 and "self.dismiss(False)" in src3:
    print("  [OK] Both dismiss calls correct")

# Test 5: Check TopBar loop button handler
src4 = inspect.getsource(Path("core/tui.py").read_text())
from core.tui import OrcaTUI
src5 = inspect.getsource(OrcaTUI.on_button_pressed)
if "btn-topbar-loop" in src5:
    print("\n=== TopBar Loop Button ===")
    print("  [OK] btn-topbar-loop handled")
    if "AutopilotWarningModal" in src5:
        print("  [OK] Uses AutopilotWarningModal")
    if "push_screen" in src5:
        print("  [OK] Uses push_screen (correct for App)")

# Test 6: Check the old bug
if "self.app.push_screen(AutopilotWarningModal" in src:
    print("\n=== Fix Status ===")
    print("  [FIXED] Using self.app.push_screen (not self.push_screen)")
if "self.app.push_screen(check_warning" in src5 or "self.push_screen(AutopilotWarningModal" in src5:
    print("  [CONFIRMED] TopBar uses correct App-level push_screen")

print("\n=== ALL CHECKS DONE ===")