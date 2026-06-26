from unittest.mock import patch

from app.collect.base import CollectContext
from app.collect.sources.baike import BaikeConnector
from app.collect.sources.wiki import WikiConnector


class _FakeResponse:
    def __init__(self, payload):
        self.status_code = payload["status_code"]
        self._json = payload["json"]

    def json(self):
        return self._json()


def _fake_baike_response(keyword: str):
    return {
        "status_code": 200,
        "json": lambda: {
            "key": keyword,
            "abstract": f"{keyword}是商代晚期青铜礼器，1939年出土于河南安阳。",
        },
    }


async def test_baike_connector_three_stages():
    connector = BaikeConnector()
    ctx = CollectContext()

    # discover：传入展品名列表
    items = await connector.discover(ctx, exhibit_names=["司母戊鼎"])
    assert len(items) == 1
    assert items[0]["name"] == "司母戊鼎"
    assert "source_ref" in items[0]

    # fetch + parse：mock httpx
    with patch("app.collect.base.httpx.get") as mock_get:
        mock_get.return_value = _FakeResponse(_fake_baike_response("司母戊鼎"))
        raw = await connector.fetch(items[0], ctx)
        assert raw is not None

        fields = await connector.parse(raw, items[0], ctx)
        assert fields["name"] == "司母戊鼎"
        assert "商" in fields["description"] or fields["dynasty"]


async def test_baike_connector_not_found():
    connector = BaikeConnector()
    ctx = CollectContext()

    items = await connector.discover(ctx, exhibit_names=["不存在的展品"])
    assert len(items) == 1

    with patch("app.collect.base.httpx.get") as mock_get:
        mock_get.return_value = _FakeResponse({"status_code": 200, "json": lambda: {}})
        raw = await connector.fetch(items[0], ctx)
        assert raw is None  # 百科未命中


class _FakeWikiSearchResponse:
    status_code = 200

    def json(self):
        return {"query": {"search": [{"title": "司母戊鼎"}]}}


class _FakeWikiSummaryResponse:
    status_code = 200

    def json(self):
        return {"extract": "后母戊鼎是中国商代晚期青铜方鼎，1939年河南安阳出土。"}


async def test_wiki_connector_exhibit():
    connector = WikiConnector()
    ctx = CollectContext()
    items = await connector.discover(ctx, exhibit_names=["司母戊鼎"])
    assert len(items) == 1

    responses = [_FakeWikiSearchResponse(), _FakeWikiSummaryResponse()]
    with patch("app.collect.base.httpx.get", side_effect=responses):
        raw = await connector.fetch(items[0], ctx)
        assert raw is not None
        fields = await connector.parse(raw, items[0], ctx)
        assert fields["name"] == "司母戊鼎"
        assert "商" in fields["description"]
