"""测试 skyforge_engine.core.verifiers 验证器分层."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))

import pytest

from skyforge_engine.core.protocols import (
    ToolNotFoundError,
    VerificationResult,
    VerifierProtocol,
)
from skyforge_engine.core.verifiers import (
    CBMCVerifier,
    ContractVerifier,
    CppcheckVerifier,
    VerifierChain,
    Z3Verifier,
)


class DummyVerifier:
    """用于链式测试的 dummy 验证器。"""

    def __init__(self, name: str, available: bool = True, passed: bool = True):
        self._name = name
        self._available = available
        self._passed = passed

    @property
    def tool_name(self) -> str:
        return self._name

    def is_available(self) -> bool:
        return self._available

    def verify(self, code: str, contract: str | None = None, **kwargs):
        if not self._available:
            raise ToolNotFoundError(self._name)
        return VerificationResult(
            passed=self._passed,
            tool_name=self._name,
            tool_available=True,
        )


class TestProtocolCompliance:
    """测试各验证器实现 VerifierProtocol."""

    def test_z3_verifier_protocol(self):
        verifier = Z3Verifier()
        assert isinstance(verifier, VerifierProtocol)
        assert verifier.tool_name == "z3"

    def test_cbmc_verifier_protocol(self):
        verifier = CBMCVerifier()
        assert isinstance(verifier, VerifierProtocol)
        assert verifier.tool_name == "cbmc"

    def test_contract_verifier_protocol(self):
        verifier = ContractVerifier()
        assert isinstance(verifier, VerifierProtocol)
        assert verifier.tool_name == "contract"

    def test_cppcheck_verifier_protocol(self):
        verifier = CppcheckVerifier()
        assert isinstance(verifier, VerifierProtocol)
        assert verifier.tool_name == "cppcheck"


class TestAvailability:
    """测试工具不可用时的行为。"""

    def test_z3_unavailable_raises(self, monkeypatch):
        verifier = Z3Verifier()
        monkeypatch.setattr(verifier, "is_available", lambda: False)
        with pytest.raises(ToolNotFoundError) as exc_info:
            verifier.verify("code")
        assert exc_info.value.tool_name == "z3"

    def test_cbmc_unavailable_raises(self, monkeypatch):
        verifier = CBMCVerifier()
        monkeypatch.setattr(verifier, "is_available", lambda: False)
        with pytest.raises(ToolNotFoundError) as exc_info:
            verifier.verify("int main() {}")
        assert exc_info.value.tool_name == "cbmc"

    def test_cppcheck_unavailable_raises(self, monkeypatch):
        verifier = CppcheckVerifier()
        monkeypatch.setattr(verifier, "is_available", lambda: False)
        with pytest.raises(ToolNotFoundError) as exc_info:
            verifier.verify("int main() {}")
        assert exc_info.value.tool_name == "cppcheck"

    def test_contract_verifier_requires_contract(self):
        verifier = ContractVerifier()
        with pytest.raises(ValueError, match="contract 参数为必填项"):
            verifier.verify(code="", contract=None)

    def test_contract_verifier_invalid_yaml(self):
        verifier = ContractVerifier()
        with pytest.raises(ValueError, match="YAML 解析失败"):
            verifier.verify(code="", contract="not: valid: yaml: [")

    def test_contract_verifier_non_dict_contract(self):
        verifier = ContractVerifier()
        with pytest.raises(ValueError, match="非字典"):
            verifier.verify(code="", contract="- list_item")


class TestVerifierChain:
    """测试 VerifierChain 组合行为。"""

    def test_verify_all_empty(self):
        chain = VerifierChain()
        results = chain.verify_all("code")
        assert results == []

    def test_verify_all_success(self):
        v1 = DummyVerifier("v1", passed=True)
        v2 = DummyVerifier("v2", passed=True)
        chain = VerifierChain([v1, v2])
        results = chain.verify_all("code")
        assert len(results) == 2
        assert all(r.passed for r in results)
        assert results[0].tool_name == "v1"
        assert results[1].tool_name == "v2"

    def test_verify_all_with_failure_no_fail_fast(self):
        v1 = DummyVerifier("v1", passed=False)
        v2 = DummyVerifier("v2", passed=True)
        chain = VerifierChain([v1, v2])
        results = chain.verify_all("code")
        assert len(results) == 2
        assert results[0].passed is False
        assert results[1].passed is True

    def test_verify_all_with_failure_fail_fast(self):
        v1 = DummyVerifier("v1", passed=False)
        v2 = DummyVerifier("v2", passed=True)
        chain = VerifierChain([v1, v2], fail_fast=True)
        results = chain.verify_all("code")
        assert len(results) == 1
        assert results[0].passed is False

    def test_verify_all_tool_unavailable_no_fail_fast(self):
        v1 = DummyVerifier("v1", available=False)
        v2 = DummyVerifier("v2", passed=True)
        chain = VerifierChain([v1, v2])
        results = chain.verify_all("code")
        assert len(results) == 2
        assert results[0].passed is False
        assert results[0].tool_available is False
        assert results[1].passed is True

    def test_verify_all_tool_unavailable_fail_fast(self):
        v1 = DummyVerifier("v1", available=False)
        v2 = DummyVerifier("v2", passed=True)
        chain = VerifierChain([v1, v2], fail_fast=True)
        with pytest.raises(ToolNotFoundError):
            chain.verify_all("code")

    def test_verify_any_first_passes(self):
        v1 = DummyVerifier("v1", passed=True)
        v2 = DummyVerifier("v2", passed=False)
        chain = VerifierChain([v1, v2])
        result = chain.verify_any("code")
        assert result.passed is True
        assert result.tool_name == "v1"

    def test_verify_any_second_passes(self):
        v1 = DummyVerifier("v1", passed=False)
        v2 = DummyVerifier("v2", passed=True)
        chain = VerifierChain([v1, v2])
        result = chain.verify_any("code")
        assert result.passed is True
        assert result.tool_name == "v2"

    def test_verify_any_none_pass(self):
        v1 = DummyVerifier("v1", passed=False)
        v2 = DummyVerifier("v2", passed=False)
        chain = VerifierChain([v1, v2])
        result = chain.verify_any("code")
        assert result.passed is False
        assert result.tool_name == "verifier_chain"

    def test_verify_any_unavailable_skips(self):
        v1 = DummyVerifier("v1", available=False)
        v2 = DummyVerifier("v2", passed=True)
        chain = VerifierChain([v1, v2])
        result = chain.verify_any("code")
        assert result.passed is True
        assert result.tool_name == "v2"

    def test_verify_all_unavailable_raises_last(self):
        v1 = DummyVerifier("v1", available=False)
        v2 = DummyVerifier("v2", available=False)
        chain = VerifierChain([v1, v2])
        with pytest.raises(ToolNotFoundError):
            chain.verify_any("code")

    def test_chain_add(self):
        chain = VerifierChain()
        chain.add(DummyVerifier("v1"))
        assert len(chain._verifiers) == 1

    def test_chain_add_returns_self(self):
        chain = VerifierChain()
        result = chain.add(DummyVerifier("v1"))
        assert result is chain
