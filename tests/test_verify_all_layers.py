"""Verify all 5 layers of the error handling pipeline work together."""
from core.services.error_parser import ErrorParser
from core.services.rule_engine import RuleEngine, ActionType
from core.services.error_pipeline import ErrorPipeline, BuildConfig

# Layer 1+2: Parser detects errors from compiler output
parser = ErrorParser('tsc')
errors = parser.parse(
    'src/login.ts(42,5): error TS2339: Property token does not exist\n'
    'src/utils.ts(10,1): warning TS6133: unused variable\n'
)
assert len(errors) == 2, f"Expected 2 errors, got {len(errors)}"
print(f'Layer 1+2: Parsed {len(errors)} errors')
for e in errors:
    print(f'  {e.file}:{e.line} [{e.severity}] {e.error} (source={e.source})')

# Layer 3+4: Rule engine matches errors to auto-fix actions
engine = RuleEngine()
matched = engine.match_errors([e.to_dict() for e in errors])
assert len(matched) == 2, f"Expected 2 matches, got {len(matched)}"
print(f'\nLayer 3+4: Matched {len(matched)} rules')
for m in matched:
    print(f'  {m.rule.name} -> {m.rule.action.value} on {m.error_file}:{m.error_line}')

# Verify TS property error -> NEEDS_AI
prop_match = [m for m in matched if m.rule.action == ActionType.NEEDS_AI]
assert len(prop_match) == 1, "TS property error should be NEEDS_AI"

# Layer 5: Complex errors go to AI
ai_errors = engine.get_ai_needed_errors([e.to_dict() for e in errors])
assert len(ai_errors) == 1, f"Expected 1 AI error, got {len(ai_errors)}"
print(f'\nLayer 5: {len(ai_errors)} errors need AI reasoning')
for e in ai_errors:
    print(f'  {e["file"]}:{e["line"]} -> {e["error"]}')

# Pipeline flow summary
auto_fixable = len(matched) - len(ai_errors)
print(f'\nPipeline: Build -> Parse ({len(errors)} errors) -> Fix ({auto_fixable} auto) -> Rebuild -> AI ({len(ai_errors)} remaining)')
assert auto_fixable == 1, f"Expected 1 auto-fixable, got {auto_fixable}"

# Context filtering test: 100K lines -> focused error regions
pipeline = ErrorPipeline(project_root=".", max_fix_rounds=1, on_status=lambda s: None, on_log=lambda s: None)
ai_context = pipeline._build_ai_context([e.to_dict() for e in errors])
assert 'src/login.ts' in ai_context
assert 'src/utils.ts' in ai_context
assert 'TS2339' in ai_context
lines_in_context = len(ai_context.split('\n'))
assert lines_in_context < 50, f"Context should be focused (<50 lines), got {lines_in_context}"
print(f'\nContext filtering: {lines_in_context} lines of focused context')

print('\nAll 5 layers verified successfully!')