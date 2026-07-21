"""sanitizer 模块单元测试 — 覆盖 5 项净化规则与边界场景。"""

from skyforge_llm.security.sanitizer import sanitize_input


def test_pure_path():
    """纯路径输入应被替换为 <PROJECT_ROOT>，并记录到 mapping。"""
    result = sanitize_input("/home/alice/project")
    assert "<PROJECT_ROOT>" in result.text
    assert result.mapping.get("/home/alice") == "<PROJECT_ROOT>"


def test_pure_address():
    """纯硬件地址应被替换为 0xREG_BASE_0000，并记录到 mapping。"""
    result = sanitize_input("0xDEADBEEF")
    assert "0xREG_BASE_0000" in result.text
    assert result.mapping.get("0xDEADBEEF") == "0xREG_BASE_0000"


def test_pure_version():
    """纯版本号应被替换为 <VERSION_0>，并记录到 mapping。"""
    result = sanitize_input("v1.2.3-alpha")
    assert "<VERSION_0>" in result.text
    assert result.mapping.get("v1.2.3-alpha") == "<VERSION_0>"


def test_pure_project_name():
    """项目代号应被替换为 <PROJECT_NAME>，并记录到 mapping。"""
    result = sanitize_input("SkyForge 是工具")
    assert "<PROJECT_NAME>" in result.text
    assert result.mapping.get("SkyForge") == "<PROJECT_NAME>"


def test_c_block_comment():
    """C 块注释应被替换为 <C_COMMENT_0>，并记录到 mapping。"""
    result = sanitize_input("int x; /* 这是注释 */")
    assert "<C_COMMENT_0>" in result.text
    assert "/* 这是注释 */" in result.mapping
    assert result.mapping["/* 这是注释 */"] == "<C_COMMENT_0>"


def test_c_line_comment():
    """C 行注释应被替换为 <C_COMMENT_0>。"""
    result = sanitize_input("int x; // 这是行注释")
    assert "<C_COMMENT_0>" in result.text
    assert "// 这是行注释" in result.mapping
    assert result.mapping["// 这是行注释"] == "<C_COMMENT_0>"


def test_c_multiline_comment():
    """跨行 C 注释应被整体替换为 <C_COMMENT_0>。"""
    result = sanitize_input("int x; /* 多行\n注释 */")
    assert "<C_COMMENT_0>" in result.text
    assert "/* 多行\n注释 */" in result.mapping
    assert result.mapping["/* 多行\n注释 */"] == "<C_COMMENT_0>"


def test_mixed_input():
    """混合输入应被全部脱敏，mapping 完整。"""
    prompt = "SkyForge v1.2.3-alpha /home/alice 0xDEADBEEF /* 注释 */"
    result = sanitize_input(prompt)
    assert "<PROJECT_NAME>" in result.text
    assert "<VERSION_0>" in result.text
    assert "<PROJECT_ROOT>" in result.text
    assert "0xREG_BASE_0000" in result.text
    assert "<C_COMMENT_0>" in result.text
    # mapping 应包含所有原始敏感信息
    assert "SkyForge" in result.mapping
    assert "v1.2.3-alpha" in result.mapping
    assert "/home/alice" in result.mapping
    assert "0xDEADBEEF" in result.mapping
    assert "/* 注释 */" in result.mapping


def test_no_sensitive_info():
    """无敏感信息输入应原样返回，mapping 为空 dict。"""
    result = sanitize_input("普通文本无敏感信息")
    assert result.text == "普通文本无敏感信息"
    assert result.mapping == {}


def test_mapping_completeness():
    """验证混合输入场景下 mapping 字典的 keys 包含全部原始敏感信息。"""
    prompt = "SkyForge v1.2.3-alpha /home/alice 0xDEADBEEF /* 注释 */"
    result = sanitize_input(prompt)
    expected_keys = {
        "SkyForge",
        "v1.2.3-alpha",
        "/home/alice",
        "0xDEADBEEF",
        "/* 注释 */",
    }
    assert expected_keys.issubset(set(result.mapping.keys()))


def test_comment_is_sanitized_first():
    """C 注释内的路径/版本号不应被二次脱敏。

    注释 /* /home/user */ 应整体被替换为 <C_COMMENT_0>，
    其中的 /home/user 不应单独出现在 mapping 中。
    """
    result = sanitize_input("/* /home/user */")
    assert result.text == "<C_COMMENT_0>"
    assert result.mapping.get("/* /home/user */") == "<C_COMMENT_0>"
    # /home/user 不应作为独立路径出现在 mapping 中
    assert "/home/user" not in result.mapping
