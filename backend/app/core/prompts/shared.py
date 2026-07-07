"""共享的提示词工具函数。"""


def get_reflection_prompt(error_message, code) -> str:
    """生成代码错误反思提示词。

    Args:
        error_message: 错误信息。
        code: 出错的代码。

    Returns:
        反思提示词字符串。
    """
    return f"""The code execution encountered an error:
{error_message}

Please analyze the error, identify the cause, and provide a corrected version of the code.
Consider:
1. Syntax errors
2. Missing imports
3. Incorrect variable names or types
4. File path issues
5. Any other potential issues

Previous code:
{code}

Please provide an explanation of what went wrong and provide corrected code."""
