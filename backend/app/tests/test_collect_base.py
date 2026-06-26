from app.collect.base import CollectContext


def test_collect_context_defaults():
    ctx = CollectContext()
    assert ctx.cancelled is False
    ctx.cancel()
    assert ctx.cancelled is True


async def test_collect_context_sleep_cancellable():
    """sleep 在被 cancel 后立即返回而非阻塞。"""
    ctx = CollectContext()
    ctx.cancel()
    # 已 cancel，sleep 应立即返回
    await ctx.sleep(100)  # 不会真的等
