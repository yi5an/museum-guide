"""河南博物院官网采集 connector（per-site 配置）。

继承 OfficialConnector。目录页展品链接结构与国博不同：
href 与展品名(cp-title)分离在不同标签，需 DOTALL 跨标签正则匹配；
链接为协议相对 URL(//开头)，由基类 _absolutize 补全。
详情页交 LLM#1 提取。
"""

import re

from app.collect.sources.official_base import OfficialConnector

# 河南博物院典藏精品页（boutique），含约 12 件精品展品
_HENAN_CATALOG_URLS = [
    "https://www.chnmus.net/ch/collection/boutique/index.html",
]

# 展品链接+名分散：<a href="URL">...<div class="cp-title">名称</div></a>
# 用 DOTALL 让 . 匹配换行，跨标签提取
_HENAN_LINK_REGEX = r'<a[^>]*href="([^"]+)"[^>]*>(?:(?!</a>).)*?<div class="cp-title">([^<]+)</div>'


class OfficialHenanConnector(OfficialConnector):
    """河南博物院官网采集。"""

    museum_name = "河南博物院"
    base_url = "https://www.chnmus.net"
    catalog_urls = _HENAN_CATALOG_URLS
    link_regex = _HENAN_LINK_REGEX
    link_regex_flags = re.DOTALL
    skip_titles = {"首页"}
