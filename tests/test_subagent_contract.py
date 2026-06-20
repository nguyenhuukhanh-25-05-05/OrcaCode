"""Tests for Structured Subagent Contracts."""
import pytest
import sys
sys.path.insert(0, r'D:\OrcaCode-main')

from core.services.subagent_contract import (
    SubagentTask, SubagentResult, ContractStatus, ContractSeverity,
    ContractValidator, ContractValidation, ContractViolation,
    ContractRegistry, CodeReviewContract,
    parse_subagent_result,
)


class TestSubagentTask:
    def test_task_creation(self):
        task = SubagentTask(
            task_id='refactor-001',
            goal='Refactor auth.py to use async',
            contract_type='refactor',
            files=['auth.py', 'middleware.py'],
            constraints=['Must be backward compatible'],
            expected_output={'modified_files': 'list'},
        )
        assert task.to_dict()['task_id'] == 'refactor-001'

    def test_task_to_prompt(self):
        task = SubagentTask(
            task_id='rf-1', goal='Refactor',
            contract_type='refactor',
            expected_output={'backward_compatible': 'bool'},
        )
        prompt = task.to_prompt()
        assert '<SUBTASK' in prompt
        assert 'Refactor' in prompt
        assert 'backward_compatible' in prompt


class TestSubagentResult:
    def test_result_passed(self):
        result = SubagentResult(
            task_id='rf-1', status=ContractStatus.COMPLETE,
            contract_type='refactor', summary='Done',
            modified_files=['auth.py'],
            checks_performed=['Lint passed'],
        )
        assert result.passed
        assert result.all_files_touched == {'auth.py'}

    def test_result_failed(self):
        result = SubagentResult(
            task_id='t-1', status=ContractStatus.FAILED,
            summary='Failed', failures=['Build error'],
        )
        assert not result.passed

    def test_format_for_review(self):
        result = SubagentResult(
            task_id='rf-1', status=ContractStatus.COMPLETE,
            contract_type='refactor', summary='Done',
        )
        report = result.format_for_review()
        assert '<SUBTASK_RESULT' in report
        assert 'rf-1' in report


class TestContractValidator:
    def test_passing_validation(self):
        result = SubagentResult(
            task_id='rf-1', status=ContractStatus.COMPLETE,
            modified_files=['auth.py'],
            checks_performed=['Lint passed'],
        )
        v = ContractValidator.validate(result, expected_files=['auth.py'])
        assert v.valid
        assert len(v.violations) == 0

    def test_missing_expected_file(self):
        result = SubagentResult(
            task_id='rf-1', status=ContractStatus.COMPLETE,
            modified_files=['auth.py'],
        )
        v = ContractValidator.validate(result, expected_files=['auth.py', 'missing.py'])
        assert not v.valid
        assert any('missing.py' in str(vc) for vc in v.violations)

    def test_failed_status_blocks(self):
        result = SubagentResult(
            task_id='t-1', status=ContractStatus.FAILED,
            failures=['error'],
        )
        v = ContractValidator.validate(result)
        assert not v.valid

    def test_format_report(self):
        v = ContractValidation()
        assert 'passed' in v.format_report().lower()

        v.violations.append(ContractViolation(
            field='status', message='Not complete',
        ))
        assert 'issues' in v.format_report().lower()


class TestContractRegistry:
    def test_register_and_list(self):
        reg = ContractRegistry()
        reg.register('refactor', lambda r: ContractValidation([]))
        assert 'refactor' in reg.list_contracts()

    def test_validate_unknown_contract(self):
        reg = ContractRegistry()
        result = SubagentResult(task_id='x', status=ContractStatus.COMPLETE)
        assert reg.validate('unknown', result) is None


class TestSpecializedContracts:
    def test_code_review_contract(self):
        cr = CodeReviewContract(
            task_id='cr-1', status=ContractStatus.COMPLETE,
            review_issues=[{'severity': 'high', 'file': 'auth.py'}],
            quality_score=0.85,
        )
        assert cr.quality_score == 0.85
        assert len(cr.to_dict()['review_issues']) == 1


class TestParseSubagentResult:
    def test_parse_json_block(self):
        text = """Here's the result:
```json
{
    "task_id": "subt-1",
    "contract_type": "refactor",
    "status": "complete",
    "summary": "Done",
    "modified_files": ["auth.py"],
    "checks_performed": ["lint ok"],
    "n_llm_calls": 3
}
```"""
        parsed = parse_subagent_result(text)
        assert parsed is not None
        assert parsed.task_id == 'subt-1'
        assert parsed.status == ContractStatus.COMPLETE
        assert 'auth.py' in parsed.modified_files

    def test_parse_xml_block(self):
        text = """Done.
<SUBTASK_RESULT contract="refactor" id="sub-2" status="complete">
Summary: Refactored auth module
Modified: auth.py, middleware.py
Checks: lint passed, tests passed
Failures: none
</SUBTASK_RESULT>"""
        parsed = parse_subagent_result(text)
        assert parsed is not None
        assert parsed.task_id == 'sub-2'
        assert 'middleware.py' in parsed.modified_files

    def test_parse_no_result(self):
        assert parse_subagent_result("No result here") is None
