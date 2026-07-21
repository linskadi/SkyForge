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
