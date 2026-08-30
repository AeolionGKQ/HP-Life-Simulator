from __future__ import annotations

from backend.app.core.config import Settings, get_settings, update_llm_thinking
from backend.app.providers.openai_compatible import (
    THINKING_DISABLE_FIELDS,
    OpenAICompatibleProvider,
)


async def apply_thinking_setting(*, enable_thinking: bool) -> tuple[Settings, str]:
    """开关模型思考；关闭前先探测服务是否接受关闭参数。

    返回 (最新配置, 面向玩家的说明)。若服务拒绝全部参数，则保持开启，
    以免之后每次生成剧情都因为未知参数失败。
    """
    if enable_thinking:
        settings = update_llm_thinking(
            enable_thinking=True,
            thinking_disable_fields=None,
        )
        return settings, "模型思考已开启。"

    current = get_settings()
    if not current.llm.api_key.get_secret_value():
        settings = update_llm_thinking(
            enable_thinking=False,
            thinking_disable_fields=None,
        )
        return settings, "模型思考已关闭；模型服务尚未配置，暂时无法验证它是否接受关闭参数。"

    provider = OpenAICompatibleProvider(
        current.llm,
        persist_thinking_fields=False,
    )
    accepted, verified = await provider.probe_thinking_disable_fields()

    if not verified:
        settings = update_llm_thinking(
            enable_thinking=False,
            thinking_disable_fields=None,
        )
        return settings, "模型思考已关闭；本次未能验证模型服务，若之后被拒绝会自动恢复开启。"

    if not accepted:
        settings = update_llm_thinking(
            enable_thinking=True,
            thinking_disable_fields=None,
        )
        return settings, "你的模型服务不接受关闭思考的参数，已保持开启；更换模型或服务后可再次点击重试。"

    if len(accepted) == len(THINKING_DISABLE_FIELDS):
        settings = update_llm_thinking(
            enable_thinking=False,
            thinking_disable_fields=None,
        )
        return settings, "模型思考已关闭。"

    settings = update_llm_thinking(
        enable_thinking=False,
        thinking_disable_fields=accepted,
    )
    joined = "、".join(accepted)
    return settings, f"模型思考已关闭；该服务只接受 {joined}，其余参数已停用。"

