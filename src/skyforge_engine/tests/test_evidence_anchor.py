"""SkyForge 链上证据锚定模块测试。

覆盖：
- canonical JSON 序列化稳定性（键排序/紧凑分隔符/UTF-8）
- SHA-256 哈希确定性与跨输入区分
- 证据包 index.json 锚定哈希
- pipeline 结果摘要锚定哈希与 ABI 校验
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))

import pytest

from skyforge_engine.chain.evidence_anchor import (
    CHAIN_ID,
    EVIDENCE_ANCHOR_ABI,
    build_evidence_payload,
    canonical_json,
    compute_anchor_hash,
    compute_anchor_hash_from_package,
    compute_anchor_hash_from_report,
    verify_anchor,
)


class TestCanonicalJson:
    def test_key_sorting_stable(self):
        a = canonical_json({"b": 1, "a": {"d": 4, "c": 3}})
        b = canonical_json({"a": {"c": 3, "d": 4}, "b": 1})
        assert a == b
        assert a == '{"a":{"c":3,"d":4},"b":1}'

    def test_compact_separators(self):
        out = canonical_json({"x": [1, 2, 3]})
        assert " " not in out

    def test_utf8_preserved(self):
        out = canonical_json({"name": "航空证据"})
        assert "航空证据" in out


class TestAnchorHash:
    def test_deterministic(self):
        payload = {"a": 1, "b": "x"}
        assert compute_anchor_hash(payload) == compute_anchor_hash(payload)

    def test_different_payload_differs(self):
        assert compute_anchor_hash({"a": 1}) != compute_anchor_hash({"a": 2})

    def test_sha256_known_vector(self):
        assert compute_anchor_hash({}) == (
            "44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a"
        )


class TestPackageAnchoring:
    def test_hash_from_package_index(self, tmp_path):
        index = {
            "evidence_package": {
                "session_id": "s1",
                "total_items": 2,
            },
            "categories": {"verification": 1, "tools": 1},
        }
        (tmp_path / "index.json").write_text(
            json.dumps(index), encoding="utf-8"
        )

        expected = compute_anchor_hash(index)
        assert compute_anchor_hash_from_package(str(tmp_path)) == expected

    def test_missing_index_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            compute_anchor_hash_from_package(str(tmp_path))

    def test_verify_anchor_self_check(self, tmp_path):
        index = {"a": 1}
        (tmp_path / "index.json").write_text(
            json.dumps(index), encoding="utf-8"
        )
        result = verify_anchor(str(tmp_path))
        assert result["matches"] is True
        assert result["hash"] == compute_anchor_hash(index)


class TestReportPayload:
    def test_payload_stable_across_key_order(self):
        p1 = build_evidence_payload(
            {"language": "C", "metrics": {"code_lines": 12, "violations": 0}}
        )
        p2 = build_evidence_payload(
            {
                "metrics": {"violations": 0, "code_lines": 12},
                "language": "C",
            }
        )
        assert p1 == p2
        assert compute_anchor_hash(p1) == compute_anchor_hash(p2)

    def test_payload_changes_with_metrics(self):
        base = {"language": "C", "metrics": {"code_lines": 10, "violations": 0}}
        changed = {"language": "C", "metrics": {"code_lines": 11, "violations": 0}}
        assert compute_anchor_hash_from_report(base) != compute_anchor_hash_from_report(
            changed
        )

    def test_payload_normalizes_missing_values(self):
        payload = build_evidence_payload({})
        assert payload["requirements"]["count"] == 0
        assert payload["code"]["lines"] == 0
        assert payload["verification"]["misra_violations"] == 0
        assert payload["verification"]["contract_passed"] is False


class TestAbi:
    def test_abi_has_anchor_and_verify(self):
        names = {entry["name"] for entry in EVIDENCE_ANCHOR_ABI}
        assert {"anchor", "verify", "getEvidence", "getHashCount"} <= names

    def test_sepolia_chain_id(self):
        assert CHAIN_ID == 11155111
