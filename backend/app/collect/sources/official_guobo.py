"""国博官网采集 connector（per-site 配置）。

继承 OfficialConnector，只配置 site-specific 属性。
目录页用正则提展品名+详情链接，详情页正文交 LLM#1 提取。
"""

from app.collect.sources.official_base import OfficialConnector

# 国博馆藏精品目录页，11 个分页
_BASE = "https://www.chnmuseum.cn/zp/zpml/kgfjp/"
_GUOBO_CATALOG_URLS = [
    (_BASE if i == 0 else f"{_BASE}index_{i}.shtml") for i in range(11)
]

_GUOBO_SKIP = {
    "国家博物馆", "首页", "征集", "保管", "研究", "展览", "社教", "文创", "服务",
    "学习", "视频", "登录", "注册", "分享", "下载", "导航", "馆藏精品",
    "隐私政策", "隐私安全声明", "版权声明", "留言板", "联系我们", "网站地图",
}


class OfficialGuoboConnector(OfficialConnector):
    """中国国家博物馆官网采集。"""

    museum_name = "中国国家博物馆"
    base_url = "https://www.chnmuseum.cn"
    catalog_urls = _GUOBO_CATALOG_URLS
    link_regex = r'<a[^>]*href="([^"]*)"[^>]*title="([^"]*)"'
    skip_titles = _GUOBO_SKIP
