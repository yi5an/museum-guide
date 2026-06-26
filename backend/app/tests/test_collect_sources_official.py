from unittest.mock import AsyncMock, patch

from app.collect.base import CollectContext
from app.collect.sources.official_guobo import OfficialGuoboConnector
from app.collect.sources.wiki_list import WikiListConnector


class _Resp:
    def __init__(self, text, status_code=200):
        self.status_code = status_code
        self.text = text


_FAKE_HTML = """
<html><body>
<a href="/wiki/中国国家博物馆" title="中国国家博物馆">中国国家博物馆</a>
<a href="/wiki/故宫博物院" title="故宫博物院">故宫博物院</a>
<a href="/wiki/上海博物馆" title="上海博物馆">上海博物馆</a>
<a href="/wiki/编辑" title="编辑">编辑</a>
</body></html>
"""


async def test_wiki_list_discovers_museums():
    connector = WikiListConnector()
    ctx = CollectContext()
    with patch("app.collect.sources.wiki_list.httpx.get", return_value=_Resp(_FAKE_HTML)):
        items = await connector.discover(ctx)
    names = [i["name"] for i in items]
    assert "中国国家博物馆" in names
    assert "故宫博物院" in names
    # 过滤掉导航噪声
    assert "编辑" not in names
    assert all("source_ref" in i for i in items)


_INDEX_HTML = """
<html><body>
<a href="./kgfjp/001.shtml" title="后母戊鼎">后母戊鼎</a>
<a href="./kgfjp/002.shtml" title="四羊方尊">四羊方尊</a>
<a href="/index.shtml" title="首页">首页</a>
</body></html>
"""
_DETAIL_HTML = "<html><body>后母戊鼎，商代王室祭祀用青铜方鼎，1939年出土。</body></html>"


async def test_official_guobo_three_stages():
    connector = OfficialGuoboConnector()
    ctx = CollectContext()

    # discover 会分页调 httpx.get 多次；用一个有状态的 mock：
    # 第一页(目录)返回 200，之后的目录页返回 404 让循环 break。
    # 详情页单独返回 _DETAIL_HTML。
    call_state = {"idx_called": False}

    def _fake_get(url, **kwargs):
        if "index" in url:
            if not call_state["idx_called"]:
                call_state["idx_called"] = True
                return _Resp(_INDEX_HTML)
            return _Resp("", status_code=404)  # 后续分页 404，break
        # 详情页
        return _Resp(_DETAIL_HTML)

    with patch("app.collect.sources.official_guobo.httpx.get", side_effect=_fake_get):
        items = await connector.discover(ctx)
        assert len(items) == 2
        assert items[0]["name"] == "后母戊鼎"
        assert items[0]["source_ref"].startswith("https://www.chnmuseum.cn")

        raw = await connector.fetch(items[0], ctx)
        assert raw == _DETAIL_HTML

    # parse 交 LLM，mock 它
    fake_llm = AsyncMock()
    fake_llm.extract_exhibit = AsyncMock(return_value={
        "name": "后母戊鼎", "dynasty": "商代", "category": "青铜器",
        "description": "商代方鼎", "source_ref": items[0]["source_ref"],
    })
    connector._llm = fake_llm  # 注入 mock
    fields = await connector.parse(_DETAIL_HTML, items[0], ctx)
    assert fields["name"] == "后母戊鼎"
    assert fields["dynasty"] == "商代"
