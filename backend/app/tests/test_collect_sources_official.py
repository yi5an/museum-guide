from unittest.mock import AsyncMock, patch

from app.collect.base import CollectContext
from app.collect.sources.official_guobo import OfficialGuoboConnector
from app.collect.sources.official_henan import OfficialHenanConnector
from app.collect.sources.wiki_list import WikiListConnector


class _Resp:
    def __init__(self, text, status_code=200):
        self.status_code = status_code
        self.text = text


_FAKE_CATEGORY_HTML = """
<html><body>
<a href="/wiki/北京博物馆列表" title="北京博物馆列表">北京博物馆列表</a>
<a href="/wiki/上海博物馆列表" title="上海市博物馆列表">上海市博物馆列表</a>
<a href="/wiki/Category:中国博物馆列表" title="Category:中国博物馆列表">分类</a>
</body></html>
"""
_FAKE_PROV_HTML = """
<html><body>
<a href="/wiki/中国国家博物馆" title="中国国家博物馆">中国国家博物馆</a>
<a href="/wiki/故宫博物院" title="故宫博物院">故宫博物院</a>
<a href="/wiki/上海博物馆" title="上海博物馆">上海博物馆</a>
<a href="/wiki/编辑" title="编辑">编辑</a>
<a href="/wiki/北京博物馆列表" title="北京博物馆列表">列表本身</a>
</body></html>
"""


async def test_wiki_list_discovers_museums():
    """两步发现：分类页→省份子页→博物馆名。"""
    connector = WikiListConnector()
    ctx = CollectContext()
    # 第1次返回分类页（含省份链接），后续返回省份页（含馆名）
    with patch(
        "app.collect.base.httpx.get",
        side_effect=[_Resp(_FAKE_CATEGORY_HTML), _Resp(_FAKE_PROV_HTML), _Resp(_FAKE_PROV_HTML)],
    ):
        items = await connector.discover(ctx)
    names = [i["name"] for i in items]
    assert "中国国家博物馆" in names
    assert "故宫博物院" in names
    assert "上海博物馆" in names
    # 过滤掉导航噪声和列表本身
    assert "编辑" not in names
    assert "北京博物馆列表" not in names
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

    with patch("app.collect.base.httpx.get", side_effect=_fake_get):
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


# === 河南博物院官网 connector（验证基类可复用）===

_HENAN_INDEX_HTML = """
<html><body>
<div class="list-item">
  <a href="//www.chnmus.net/content/redirect?id=111">
    <div class="cp-title">贾湖骨笛</div>
  </a>
</div>
<div class="list-item">
  <a href="//www.chnmus.net/content/redirect?id=222">
    <div class="cp-title">莲鹤方壶</div>
  </a>
</div>
</body></html>
"""
_HENAN_DETAIL_HTML = "<html><body>贾湖骨笛 距今约8000年 骨笛...</body></html>"


async def test_official_henan_three_stages():
    """河南博物院 connector：验证 OfficialConnector 基类可复用于不同结构官网。"""
    connector = OfficialHenanConnector()
    ctx = CollectContext()

    def _fake_get(url, **kwargs):
        if "boutique" in url:
            return _Resp(_HENAN_INDEX_HTML)
        # 详情页
        return _Resp(_HENAN_DETAIL_HTML)

    with patch("app.collect.base.httpx.get", side_effect=_fake_get):
        items = await connector.discover(ctx)
        assert len(items) == 2
        assert items[0]["name"] == "贾湖骨笛"
        # 协议相对链接(//开头)应被补全为 https://
        assert items[0]["source_ref"].startswith("https://www.chnmus.net")

        raw = await connector.fetch(items[0], ctx)
        assert raw == _HENAN_DETAIL_HTML

    fake_llm = AsyncMock()
    fake_llm.extract_exhibit = AsyncMock(return_value={
        "name": "贾湖骨笛", "dynasty": "新石器", "category": "骨器",
        "description": "中国最早的乐器", "source_ref": items[0]["source_ref"],
    })
    connector._llm = fake_llm
    fields = await connector.parse(_HENAN_DETAIL_HTML, items[0], ctx)
    assert fields["name"] == "贾湖骨笛"


async def test_registry_official_per_museum():
    """registry 按 museum_id 返回对应官网 connector。"""
    from app.collect.registry import get_connector, has_official

    # 国博(id=1) -> OfficialGuoboConnector
    c1 = get_connector("official", museum_id=1)
    assert c1.museum_name == "中国国家博物馆"

    # 河南(id=7) -> OfficialHenanConnector
    c7 = get_connector("official", museum_id=7)
    assert c7.museum_name == "河南博物院"

    assert has_official(1) is True
    assert has_official(7) is True
    assert has_official(3) is False  # 上海博物馆未接入官网

    # 未接入的馆应抛错
    try:
        get_connector("official", museum_id=3)
        assert False, "应抛 ValueError"
    except ValueError:
        pass

