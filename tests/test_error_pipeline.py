"""Test the 5-layer error handling pipeline."""
from core.services.error_parser import ErrorParser, ParsedError
from core.services.rule_engine import RuleEngine, ActionType, Rule
from core.services.error_pipeline import ErrorPipeline, BuildConfig, PipelineResult


def test_error_parser_tsc():
    """Test TSC error parsing."""
    parser = ErrorParser("tsc")
    output = """src/login.ts(42,5): error TS2339: Property 'token' does not exist on type 'User'.
src/utils.ts(10,1): warning TS6133: 'foo' is declared but its value is never read.
"""
    errors = parser.parse(output)
    assert len(errors) == 2, f"Expected 2 errors, got {len(errors)}"
    assert errors[0].file == "src/login.ts"
    assert errors[0].line == 42
    assert errors[0].severity == "error"
    assert errors[0].code == "TS2339"
    assert errors[0].source == "tsc"
    assert errors[1].severity == "warning"
    print("PASS: test_error_parser_tsc")


def test_error_parser_eslint():
    """Test ESLint error parsing."""
    parser = ErrorParser("eslint")
    output = """src/app.ts
  10:5  error  'foo' is defined but never used  no-unused-vars
  20:1  warning  Unexpected console statement  no-console

✖ 2 problems (1 error, 1 warning)
"""
    errors = parser.parse(output)
    assert len(errors) == 2, f"Expected 2 errors, got {len(errors)}"
    assert errors[0].file == "src/app.ts"
    assert errors[0].line == 10
    assert errors[0].severity == "error"
    assert errors[0].code == "no-unused-vars"
    print("PASS: test_error_parser_eslint")


def test_error_parser_pylint():
    """Test pylint error parsing."""
    parser = ErrorParser("pylint")
    output = """src/main.py:10:0: E0001: syntax error near 'import' (syntax-error)
src/utils.py:5:0: W0611: Unused import os (unused-import)
"""
    errors = parser.parse(output)
    assert len(errors) == 2, f"Expected 2 errors, got {len(errors)}"
    assert errors[0].code == "E0001"
    assert errors[0].severity == "error"
    assert errors[1].code == "W0611"
    assert errors[1].severity == "warning"
    print("PASS: test_error_parser_pylint")


def test_error_parser_generic():
    """Test generic file:line:message parsing."""
    parser = ErrorParser()
    output = "src/app.py:42: NameError: name 'foo' is not defined\n"
    errors = parser.parse(output)
    assert len(errors) == 1
    assert errors[0].file == "src/app.py"
    assert errors[0].line == 42
    print("PASS: test_error_parser_generic")


def test_rule_engine_matching():
    """Test rule engine pattern matching."""
    engine = RuleEngine()

    # Test TypeScript property error → NEEDS_AI
    errors = [
        {"file": "src/login.ts", "line": 42, "error": "Property 'token' does not exist", "severity": "error", "source": "tsc"},
    ]
    matches = engine.match_errors(errors)
    assert len(matches) == 1
    assert matches[0].rule.action == ActionType.NEEDS_AI

    # Test Cannot find module → SEARCH_FILE
    errors = [
        {"file": "src/app.ts", "line": 5, "error": "Cannot find module './config'", "severity": "error", "source": "tsc"},
    ]
    matches = engine.match_errors(errors)
    assert len(matches) == 1
    assert matches[0].rule.action == ActionType.SEARCH_FILE

    # Test unused variable eslint → DELETE_LINE
    errors = [
        {"file": "src/app.ts", "line": 10, "error": "'foo' is defined but never used", "severity": "error", "source": "eslint"},
    ]
    matches = engine.match_errors(errors)
    assert len(matches) == 1
    assert matches[0].rule.action == ActionType.DELETE_LINE

    print("PASS: test_rule_engine_matching")


def test_rule_engine_command_format():
    """Test command formatting with placeholders."""
    engine = RuleEngine()
    cmd = engine.format_command(
        "npx eslint --fix {file}",
        "src/app.ts",
        {"error": "test", "line": 10, "col": 5}
    )
    assert cmd == "npx eslint --fix src/app.ts"

    cmd = engine.format_command(
        "pip install {module_name}",
        "src/app.py",
        {"error": "No module named 'requests'", "line": 1, "col": 0}
    )
    assert cmd == "pip install requests"

    print("PASS: test_rule_engine_command_format")


def test_pipeline_with_mock_build():
    """Test pipeline with a build command that produces errors."""
    pipeline = ErrorPipeline(
        project_root=".",
        max_fix_rounds=1,
        on_status=lambda s: None,
        on_log=lambda s: None,
    )

    # Use a command that produces known output
    pipeline.add_build_step(BuildConfig(
        command='python -c "import sys; print(\'src/app.py:10: NameError: name x is not defined\'); sys.exit(1)"',
        tool="generic",
        timeout=10,
    ))

    result = pipeline.run()
    assert result.total_errors_found > 0 or result.build_success is False
    print(f"PASS: test_pipeline_with_mock_build (errors={result.total_errors_found})")


def test_pipeline_result_summary():
    """Test PipelineResult summary output."""
    result = PipelineResult(
        build_success=False,
        total_errors_found=10,
        auto_fixed_count=7,
        remaining_count=3,
        rounds=2,
        fixed_details=[
            {"rule": "eslint_auto_fix", "file": "src/a.ts", "line": 10, "action": "run_command"},
        ],
    )
    summary = result.to_summary()
    assert "10" in summary
    assert "7" in summary
    assert "3" in summary
    assert "eslint_auto_fix" in summary
    print("PASS: test_pipeline_result_summary")


def test_error_parser_json():
    """Test JSON format parsing (ESLint JSON output)."""
    parser = ErrorParser("eslint")
    json_data = [
        {
            "filePath": "src/app.ts",
            "messages": [
                {"line": 10, "column": 5, "severity": 2, "message": "Unexpected any", "ruleId": "no-explicit-any"},
                {"line": 20, "column": 1, "severity": 1, "message": "Missing return type", "ruleId": "explicit-function-return-type"},
            ]
        }
    ]
    errors = parser.parse_json(json_data, tool="eslint")
    assert len(errors) == 2
    assert errors[0].severity == "error"
    assert errors[1].severity == "warning"
    print("PASS: test_error_parser_json")


if __name__ == "__main__":
    test_error_parser_tsc()
    test_error_parser_eslint()
    test_error_parser_pylint()
    test_error_parser_generic()
    test_rule_engine_matching()
    test_rule_engine_command_format()
    test_pipeline_with_mock_build()
    test_pipeline_result_summary()
    test_error_parser_json()
    print("\n✅ All tests passed!")