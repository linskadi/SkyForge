import unittest
from skyforge_engine.report.evidence_collector import EvidenceCollector
from skyforge_engine.report.do178_objectives import (
    check_objectives, DAL,
    STATUS_PASS, STATUS_FAIL, STATUS_PARTIAL, STATUS_NA,
)


class TestOBJ12Coverage(unittest.TestCase):
    def test_obj12_pass_when_no_breach(self):
        pipeline_result = {
            "requirement": {"req_id": "REQ-001", "safety_level": "DAL-B"},
            "simulation_result": {"passed": True, "contract_violation": None, "total_steps": 200},
        }
        results = check_objectives(pipeline_result, dal=DAL.B)
        obj12 = [r for r in results if r.obj_id == "OBJ-12"][0]
        self.assertEqual(obj12.status, STATUS_PASS)

    def test_obj12_pass_when_breach_resolved(self):
        pipeline_result = {
            "requirement": {"req_id": "REQ-001", "safety_level": "DAL-B"},
            "breach_resolved": True,
            "simulation_result": None,
        }
        results = check_objectives(pipeline_result, dal=DAL.B)
        obj12 = [r for r in results if r.obj_id == "OBJ-12"][0]
        self.assertEqual(obj12.status, STATUS_PASS)

    def test_obj12_partial_when_breach_detected(self):
        pipeline_result = {
            "requirement": {"req_id": "REQ-001", "safety_level": "DAL-B"},
            "simulation_result": {
                "passed": False,
                "contract_violation": {"contract_id": "CON-001", "failed_step": 42},
            },
        }
        results = check_objectives(pipeline_result, dal=DAL.B)
        obj12 = [r for r in results if r.obj_id == "OBJ-12"][0]
        self.assertEqual(obj12.status, STATUS_PARTIAL)

    def test_obj12_fail_when_no_simulation(self):
        pipeline_result = {
            "requirement": {"req_id": "REQ-001", "safety_level": "DAL-B"},
        }
        results = check_objectives(pipeline_result, dal=DAL.B)
        obj12 = [r for r in results if r.obj_id == "OBJ-12"][0]
        self.assertEqual(obj12.status, STATUS_FAIL)

    def test_obj12_contract_check_failure_overrides_no_breach_claim(self):
        pipeline_result = {
            "requirement": {"req_id": "REQ-001", "safety_level": "DAL-B"},
            "contract_check_result": {"passed": False},
            "breach_resolved": True,
            "breach_resolution_method": "verified_no_breach",
            "simulation_result": {"passed": True, "contract_violation": None, "total_steps": 200},
        }
        results = check_objectives(pipeline_result, dal=DAL.B)
        obj12 = [r for r in results if r.obj_id == "OBJ-12"][0]
        self.assertEqual(obj12.status, STATUS_PARTIAL)


class TestOBJ10Independence(unittest.TestCase):
    def test_obj10_fail_when_hitl_disabled_system_approved(self):
        pipeline_result = {
            "requirement": {"req_id": "REQ-001", "safety_level": "DAL-B"},
            "hil_approvals": {
                "code_review": {
                    "approved": True,
                    "reviewer": "system",
                    "status": "skipped",
                    "comments": "HIL 已禁用，自动通过",
                }
            },
        }
        results = check_objectives(pipeline_result, dal=DAL.B)
        obj10 = [r for r in results if r.obj_id == "OBJ-10"][0]
        self.assertEqual(obj10.status, STATUS_FAIL)

    def test_obj10_pass_with_real_human_review(self):
        pipeline_result = {
            "requirement": {"req_id": "REQ-001", "safety_level": "DAL-B"},
            "hil_approvals": {
                "code_review": {
                    "approved": True,
                    "reviewer": "qa-reviewer",
                    "status": "approved",
                    "comments": "reviewed",
                }
            },
        }
        results = check_objectives(pipeline_result, dal=DAL.B)
        obj10 = [r for r in results if r.obj_id == "OBJ-10"][0]
        self.assertEqual(obj10.status, STATUS_PASS)


class TestOBJ18PRSystem(unittest.TestCase):
    def test_obj18_fail_for_main_branch_pr_record(self):
        pipeline_result = {
            "requirement": {"req_id": "REQ-001", "safety_level": "DAL-B"},
            "problem_reports": [
                {"pr_id": "PR-001", "branch": "main", "status": "merged"},
            ],
        }
        results = check_objectives(pipeline_result, dal=DAL.B)
        obj18 = [r for r in results if r.obj_id == "OBJ-18"][0]
        self.assertEqual(obj18.status, STATUS_FAIL)

    def test_obj18_pass_for_isolated_branch_pr_record(self):
        pipeline_result = {
            "requirement": {"req_id": "REQ-001", "safety_level": "DAL-B"},
            "problem_reports": [
                {"pr_id": "PR-001", "branch": "skyforge/REQ-001", "status": "open"},
            ],
        }
        results = check_objectives(pipeline_result, dal=DAL.B)
        obj18 = [r for r in results if r.obj_id == "OBJ-18"][0]
        self.assertEqual(obj18.status, STATUS_PASS)


class TestOBJ17Coverage(unittest.TestCase):
    def test_obj17_pass_with_tool_and_human_reviews(self):
        pipeline_result = {
            "requirement": {"req_id": "REQ-001", "safety_level": "DAL-A"},
            "independent_reviews": [
                {"reviewer_id": "cppcheck", "reviewer_role": "automated_tool", "is_author": False, "approved": True},
                {"reviewer_id": "human-hil", "reviewer_role": "human_reviewer", "is_author": False, "approved": True},
            ],
        }
        results = check_objectives(pipeline_result, dal=DAL.A)
        obj17 = [r for r in results if r.obj_id == "OBJ-17"][0]
        self.assertEqual(obj17.status, STATUS_PASS)

    def test_obj17_partial_only_tool_reviews(self):
        pipeline_result = {
            "requirement": {"req_id": "REQ-001", "safety_level": "DAL-A"},
            "independent_reviews": [
                {"reviewer_id": "cppcheck", "reviewer_role": "automated_tool", "is_author": False, "approved": True},
            ],
        }
        results = check_objectives(pipeline_result, dal=DAL.A)
        obj17 = [r for r in results if r.obj_id == "OBJ-17"][0]
        self.assertEqual(obj17.status, STATUS_PARTIAL)

    def test_obj17_pass_with_hil_and_independent_flag(self):
        pipeline_result = {
            "requirement": {"req_id": "REQ-001", "safety_level": "DAL-A"},
            "hil_history": [{"checkpoint": "sim_pass", "approved": True}],
            "contract_check_result": {"independent_verification": True},
        }
        results = check_objectives(pipeline_result, dal=DAL.A)
        obj17 = [r for r in results if r.obj_id == "OBJ-17"][0]
        self.assertEqual(obj17.status, STATUS_PASS)

    def test_obj17_fail_no_reviews(self):
        pipeline_result = {
            "requirement": {"req_id": "REQ-001", "safety_level": "DAL-A"},
        }
        results = check_objectives(pipeline_result, dal=DAL.A)
        obj17 = [r for r in results if r.obj_id == "OBJ-17"][0]
        self.assertEqual(obj17.status, STATUS_FAIL)

    def test_obj17_na_for_dal_d(self):
        pipeline_result = {
            "requirement": {"req_id": "REQ-001", "safety_level": "DAL-D"},
        }
        results = check_objectives(pipeline_result, dal=DAL.D)
        obj17 = [r for r in results if r.obj_id == "OBJ-17"][0]
        self.assertEqual(obj17.status, STATUS_NA)


class TestObjectiveCoverageMethods(unittest.TestCase):
    def test_obj13_fails_when_coverage_is_static_even_at_100_percent(self):
        pipeline_result = {
            "requirement": {"req_id": "REQ-001", "safety_level": "DAL-A"},
            "coverage_result": {
                "method": "static_analysis",
                "statement_coverage": 100.0,
                "decision_coverage": 100.0,
                "mcdc_coverage": 100.0,
            },
        }
        results = check_objectives(pipeline_result, dal=DAL.A)
        obj13 = [r for r in results if r.obj_id == "OBJ-13"][0]
        self.assertEqual(obj13.status, STATUS_FAIL)

    def test_obj13_passes_with_real_gcov_at_target(self):
        pipeline_result = {
            "requirement": {"req_id": "REQ-001", "safety_level": "DAL-A"},
            "coverage_result": {
                "method": "gcov",
                "statement_coverage": 100.0,
                "decision_coverage": 100.0,
                "mcdc_coverage": 100.0,
            },
        }
        results = check_objectives(pipeline_result, dal=DAL.A)
        obj13 = [r for r in results if r.obj_id == "OBJ-13"][0]
        self.assertEqual(obj13.status, STATUS_PASS)


class TestEvidenceCollectorOBJ12(unittest.TestCase):
    def _make_ec(self):
        ec = EvidenceCollector()
        ec.start_session()
        return ec

    def test_record_contract_breach(self):
        ec = self._make_ec()
        item = ec.record_contract_breach(
            contract_id="CON-001",
            failed_step=42,
            assertion_message="postcondition failed",
            breach_type="postcondition",
        )
        self.assertEqual(item.do178c_ref, "OBJ-12")
        self.assertEqual(item.data["contract_id"], "CON-001")
        self.assertEqual(item.data["failed_step"], 42)

    def test_record_breach_resolution(self):
        ec = self._make_ec()
        item = ec.record_breach_resolution(
            contract_id="CON-001",
            resolution_method="code_repair",
            repair_iteration=2,
        )
        self.assertEqual(item.do178c_ref, "OBJ-12")
        self.assertEqual(item.data["resolution_method"], "code_repair")

    def test_no_breach_is_not_valid_resolution_evidence(self):
        self.assertFalse(
            EvidenceCollector._is_evidence_valid_for_objective(
                "OBJ-12",
                {"contract_id": "CON-001", "resolution_method": "no_breach"},
            )
        )

    def test_verified_no_breach_is_valid_only_after_checks(self):
        self.assertTrue(
            EvidenceCollector._is_evidence_valid_for_objective(
                "OBJ-12",
                {"contract_id": "CON-001", "resolution_method": "verified_no_breach"},
            )
        )


class TestEvidenceCollectorObjectiveValidity(unittest.TestCase):
    def test_statement_coverage_must_meet_target(self):
        self.assertFalse(
            EvidenceCollector._is_evidence_valid_for_objective(
                "A-7.5",
                {"statement_coverage": 80.0, "statement_target": 100.0},
            )
        )
        self.assertTrue(
            EvidenceCollector._is_evidence_valid_for_objective(
                "A-7.5",
                {
                    "statement_coverage": 100.0,
                    "statement_target": 100.0,
                    "method": "gcov",
                    "is_real_coverage": True,
                },
            )
        )

    def test_static_coverage_is_not_valid_a75_evidence_even_at_target(self):
        self.assertFalse(
            EvidenceCollector._is_evidence_valid_for_objective(
                "A-7.5",
                {
                    "statement_coverage": 100.0,
                    "statement_target": 100.0,
                    "method": "static_analysis",
                    "is_real_coverage": False,
                },
            )
        )

    def test_main_branch_pr_is_invalid_evidence(self):
        self.assertFalse(
            EvidenceCollector._is_evidence_valid_for_objective(
                "A-8.2",
                {"pr_id": "PR-001", "branch": "main", "status": "merged"},
            )
        )

    def test_disabled_hitl_is_invalid_independence_evidence(self):
        self.assertFalse(
            EvidenceCollector._is_evidence_valid_for_objective(
                "A-9.1",
                {
                    "approved": True,
                    "reviewer": "system",
                    "status": "skipped",
                    "comments": "HIL 已禁用，自动通过",
                },
            )
        )


class TestEvidenceCollectorOBJ17(unittest.TestCase):
    def _make_ec(self):
        ec = EvidenceCollector()
        ec.start_session()
        return ec

    def test_record_independent_review(self):
        ec = self._make_ec()
        item = ec.record_independent_review(
            reviewer_id="cppcheck-2.21.0",
            reviewer_role="automated_tool",
            is_author=False,
            scope="static_analysis",
            approved=True,
            comments="Third-party tool",
        )
        self.assertEqual(item.do178c_ref, "OBJ-17")
        self.assertTrue(item.data["independent"])
        self.assertTrue(item.data["approved"])

    def test_independent_review_is_author_not_independent(self):
        ec = self._make_ec()
        item = ec.record_independent_review(
            reviewer_id="agent-1",
            reviewer_role="tool",
            is_author=True,
            scope="code_review",
            approved=True,
        )
        self.assertFalse(item.data["independent"])


if __name__ == "__main__":
    unittest.main()
