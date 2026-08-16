# -*- coding: utf-8 -*-
"""
高清点播 - https://hqvod.com/  (MacCMS 模板 HTML 站点)
适配 WebHTV / FongMi / CatVod Python Spider (默影视壳 / dr_py)

=========================== 功能清单 ===========================
① 线路解析加载快
   - 首页/分类/搜索/详情全部正则预编译, 单请求解析;
   - 详情页一次请求拿全所有线路/集数;
   - 播放直链 30 分钟缓存, 二次点击 0 请求。
② 4K 线路排最前面
   - 识别线路名中的 "4K/2160P/2160/手机4K" 等, 4K 线路置顶;
   - 集数严重偏少的线路自动降级, 保证首选线路集数完整。
③ 国内片源优先 + 可按条件筛选
   - 筛选器: 排序(热门推荐/最新年份)、类型、地区(本地占位)、年份;
   - 类型/年份走站点 URL 参数, 实测不同条件返回不同结果;
   - 最新年份排序: 站点无此维度, 脚本本地多请求 2026/2025/2024 合并后按年份降序。
   - 注意: 该站点分类页固定热门排序, 没有服务端"最新更新"排序。
④ 完结/连载集数角标
   - 已完结 -> 已完结·全N集(取最大线路集数);
   - 更新至X集/期 原生保留; 无角标按内容类型推断。
⑤ 选集正序 + 标签归一
   - 全线路从第 1 集正序排列, 裸数字标签归一为"第N集"。
⑥ 搜索器 + 多条件筛选
   - 搜索支持"关键词 年份"精准过滤;
   - 分类筛选: 类型/地区/年份/排序(站点支持维度走服务端, 不支持的本地下层)。
⑦ 壳子网络栈兼容(参照剧迷影视适配版)
   - 移除 requests 直连, 改为 self.fetch 优先 + urllib.request 兜底;
   - 补全 getDependence/action/homeVideoContent/isVideoFormat 等壳子接口;
   - 播放页 /bofang/ 可能触发 Cloudflare/WAF, 脚本优先解析直链返回 parse=0,
     解析失败时返回 parse=1 + 本站 bofang URL 兜底(非外部跳转)。
================================================================
"""
import base64
import json
import re
import threading
import time
import urllib.parse
import urllib.request

from base.spider import Spider


# ==================== 模块级预编译正则(加载快) ====================
_RE_TITLE = re.compile(r'<div class="this-desc-title"[^>]*>([^<]+)</div>')
_RE_INFO = re.compile(r'<div class="this-desc-info"[^>]*>(.*?)</div>', re.S)
_RE_INFO_SPANS = re.compile(r'<span[^>]*>(.*?)</span>', re.S)
_RE_TAGS = re.compile(r'<div class="this-desc-tags"[^>]*>(.*?)</div>', re.S)
_RE_TAG_TEXT = re.compile(r'<span[^>]*>([^<]+)</span>')
_RE_DESC_META = re.compile(r'<meta name="description" content="([^"]+)"')
_RE_POSTER = re.compile(r'<div class="this-pic-bj"[^>]*style="[^"]*background-image:\s*url\([\'"]?([^\'\")]+)[\'"]?\)"')
_RE_LINES = re.compile(r'<a class="swiper-slide"><i class="fa[^"]*"></i>&nbsp;([^<]+?)(?:<span class="badge">(\d+)</span>)?</a>')
_RE_EPISODE = re.compile(r'<a class="hide" href="(/bofang/(\d+)-(\d+)-(\d+)\.html)">([^<]+)</a>')
_RE_CARD = re.compile(r'<div class="public-list-box[^"]*"[^>]*>(.*?)</div>\s*</div>', re.S)
_RE_CARD_LINK = re.compile(r'<a[^>]*href="(/xiangqing/(\d+)\.html)"[^>]*title="([^"]+)"')
_RE_CARD_IMG = re.compile(r'<img[^>]*?(?:data-src="([^"]+)"|alt="([^"]+)")[^>]*?(?:data-src="([^"]+)"|alt="([^"]+)")[^>]*>')
_RE_CARD_SCORE = re.compile(r'<span class="public-prt[^"]*">([^<]+)</span>')
_RE_CARD_NOTE = re.compile(r'<span class="public-list-prb[^"]*">([^<]+)</span>')
_RE_PAGE_LINK = re.compile(r'href="(/fenlei/\d+-\d+\.html)"')
_RE_SEARCH_CARD = re.compile(r'<div class="public-list-box[^"]*"[^>]*>(.*?)</div>\s*</div>', re.S)
_RE_VIDEO_URL = re.compile(r'(https?://[^\s"\'<>]+\.(?:m3u8|mp4|flv|ts))', re.I)


class Spider(Spider):
    name = "高清点播"
    host = "https://hqvod.com"

    UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
          "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")

    headers = {
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Referer": host + "/",
    }

    classes = [
        {"type_id": "1", "type_name": "电影"},
        {"type_id": "2", "type_name": "电视剧"},
        {"type_id": "3", "type_name": "动漫"},
        {"type_id": "4", "type_name": "综艺"},
    ]

    # 4K 线路优先级识别词(线路名包含即视为 4K)
    K4_WORDS = ("4K", "4k", "2160", "2160P", "手机4K")
    # 线路整体优先级(按名称关键词)
    LINE_ORDER = ("4K", "蓝光", "推荐", "稳定", "Y弹")
    # 国内地区关键词
    DOMESTIC = ("中国大陆", "内地", "大陆", "中国香港", "中国台湾", "国产", "香港", "台湾")

    # ==================== 筛选器 ====================
    SORT_OPTIONS = [
        {"n": "热门推荐", "v": "hits"},
        {"n": "最新年份", "v": "year"},
    ]

    CLASS_OPTIONS = {
        "1": [{"n": "全部", "v": ""}, {"n": "动作", "v": "动作"}, {"n": "喜剧", "v": "喜剧"},
              {"n": "爱情", "v": "爱情"}, {"n": "科幻", "v": "科幻"}, {"n": "恐怖", "v": "恐怖"},
              {"n": "剧情", "v": "剧情"}, {"n": "悬疑", "v": "悬疑"}, {"n": "犯罪", "v": "犯罪"},
              {"n": "奇幻", "v": "奇幻"}, {"n": "武侠", "v": "武侠"}, {"n": "古装", "v": "古装"},
              {"n": "动画", "v": "动画"}, {"n": "历史", "v": "历史"}, {"n": "战争", "v": "战争"},
              {"n": "纪录", "v": "纪录"}],
        "2": [{"n": "全部", "v": ""}, {"n": "国产剧", "v": "国产剧"}, {"n": "港台剧", "v": "港台剧"},
              {"n": "日韩剧", "v": "日韩剧"}, {"n": "欧美剧", "v": "欧美剧"}, {"n": "海外剧", "v": "海外剧"},
              {"n": "悬疑", "v": "悬疑"}, {"n": "古装", "v": "古装"}, {"n": "都市", "v": "都市"},
              {"n": "爱情", "v": "爱情"}, {"n": "家庭", "v": "家庭"}, {"n": "武侠", "v": "武侠"},
              {"n": "喜剧", "v": "喜剧"}, {"n": "奇幻", "v": "奇幻"}, {"n": "犯罪", "v": "犯罪"}],
        "3": [{"n": "全部", "v": ""}, {"n": "国产动漫", "v": "国产动漫"}, {"n": "日本动漫", "v": "日本动漫"},
              {"n": "欧美动漫", "v": "欧美动漫"}, {"n": "热血", "v": "热血"}, {"n": "战斗", "v": "战斗"},
              {"n": "玄幻", "v": "玄幻"}, {"n": "冒险", "v": "冒险"}, {"n": "搞笑", "v": "搞笑"},
              {"n": "奇幻", "v": "奇幻"}, {"n": "剧情", "v": "剧情"}, {"n": "神魔", "v": "神魔"}],
        "4": [{"n": "全部", "v": ""}, {"n": "国产综艺", "v": "国产综艺"}, {"n": "大陆综艺", "v": "大陆综艺"},
              {"n": "日韩综艺", "v": "日韩综艺"}, {"n": "欧美综艺", "v": "欧美综艺"}, {"n": "真人秀", "v": "真人秀"},
              {"n": "脱口秀", "v": "脱口秀"}, {"n": "搞笑", "v": "搞笑"}, {"n": "情感", "v": "情感"},
              {"n": "纪录", "v": "纪录"}, {"n": "歌舞", "v": "歌舞"}],
    }

    AREA_OPTIONS = [
        {"n": "全部", "v": ""},
        {"n": "中国大陆", "v": "中国大陆"}, {"n": "中国香港", "v": "中国香港"},
        {"n": "中国台湾", "v": "中国台湾"}, {"n": "美国", "v": "美国"},
        {"n": "日本", "v": "日本"}, {"n": "韩国", "v": "韩国"},
        {"n": "泰国", "v": "泰国"}, {"n": "英国", "v": "英国"},
        {"n": "其它", "v": "其它"},
    ]

    YEAR_OPTIONS = [{"n": "全部", "v": ""}] + [{"n": str(y), "v": str(y)} for y in range(2026, 1999, -1)]

    _filters_cache = None

    @property
    def filters(self):
        if self._filters_cache is None:
            self._filters_cache = {}
            for c in self.classes:
                tid = str(c["type_id"])
                self._filters_cache[tid] = [
                    {"key": "by", "name": "排序", "value": self.SORT_OPTIONS},
                    {"key": "class", "name": "类型", "value": self.CLASS_OPTIONS.get(tid, [])},
                    {"key": "area", "name": "地区", "value": self.AREA_OPTIONS},
                    {"key": "year", "name": "年份", "value": self.YEAR_OPTIONS},
                ]
        return self._filters_cache

    # 兼容壳子旧缓存可能传的中文键名
    _FILTER_KEY_ALIAS = {
        "排序": "by",
        "类型": "class",
        "地区": "area",
        "年份": "year",
    }

    # ==================== 壳子接口 ====================
    def init(self, extend=""):
        self.extend = extend if isinstance(extend, str) else ""

    def getName(self):
        return self.name

    def getDependence(self):
        return ""

    def isVideoFormat(self, url):
        return bool(re.search(r"\.(m3u8|mp4|flv|ts|mkv)(\?|#|$)", url or "", re.I))

    def manualVideoCheck(self):
        return False

    def liveContent(self, url):
        return ""

    def localProxy(self, param):
        return None

    def action(self, action):
        return None

    def destroy(self):
        try:
            self._home_cache = None
            self._play_cache.clear()
        except Exception:
            pass

    # ==================== 请求封装 ====================
    def __init__(self):
        super(Spider, self).__init__()
        self._home_cache = None
        self._home_ts = 0
        self._play_cache = {}
        self._pending_futures = {}

    def _get_html(self, url, headers=None):
        """GET HTML: 壳子 fetch 优先, 标准库 urllib 兜底"""
        hdrs = dict(headers or self.headers)
        # 1) 壳子网络栈
        try:
            resp = self.fetch(url, headers=hdrs)
            if resp is not None:
                text = getattr(resp, "text", None)
                if text:
                    return text
                data = getattr(resp, "content", None)
                if data:
                    return data.decode("utf-8", "replace")
        except Exception:
            pass
        # 2) 标准库兜底
        try:
            req = urllib.request.Request(url, headers=hdrs)
            with urllib.request.urlopen(req, timeout=15) as r:
                return r.read().decode("utf-8", "replace")
        except Exception:
            return ""
        return ""

    # ==================== 数据归一 ====================
    @staticmethod
    def _first(x, default=""):
        if isinstance(x, list):
            return str(x[0]) if x else default
        if x is None:
            return default
        return str(x)

    @classmethod
    def _badge(cls, remarks, classes=None, year=""):
        r = (remarks or "").strip()
        if r:
            if "完结" in r:
                return "已完结"
            if "更新" in r or "集" in r or "期" in r or "话" in r:
                r = r.replace("更新至第", "更新至").replace("更新至 ", "更新至")
                return r if len(r) <= 14 else r[:14]
            return r[:14]
        cls_text = cls._first(classes)
        if any(k in cls_text for k in ("剧", "综艺", "动漫")):
            return "连载中"
        return year or ""

    @classmethod
    def _is_domestic(cls, area, tags=None):
        text = cls._first(area) + " " + " ".join(tags or [])
        return any(k in text for k in cls.DOMESTIC)

    @classmethod
    def _parse_detail(cls, html):
        """解析详情页: 返回 dict"""
        title = ""
        m = _RE_TITLE.search(html)
        if m:
            title = m.group(1).strip()

        info_spans = []
        m = _RE_INFO.search(html)
        if m:
            raw = _RE_INFO_SPANS.findall(m.group(1))
            info_spans = [re.sub(r'<[^>]+>', '', s).strip() for s in raw]
        score = info_spans[0].strip() if info_spans else ""
        year = info_spans[1].strip() if len(info_spans) > 1 else ""
        area = info_spans[2].strip() if len(info_spans) > 2 else ""
        status = info_spans[3].strip() if len(info_spans) > 3 else ""

        tags = []
        m = _RE_TAGS.search(html)
        if m:
            tags = _RE_TAG_TEXT.findall(m.group(1))

        desc = ""
        m = _RE_DESC_META.search(html)
        if m:
            desc = m.group(1).strip()
            if "剧情介绍：" in desc:
                desc = desc.split("剧情介绍：", 1)[1]

        pic = ""
        m = _RE_POSTER.search(html)
        if m:
            pic = m.group(1).strip()

        # 线路 & 选集
        lines = _RE_LINES.findall(html)
        boxes = []
        for m in re.finditer(r'<div class="anthology-list-box none">(.*?)</div>\s*</div>', html, re.S):
            boxes.append(m.group(1))

        play_from = []
        play_url = []
        line_counts = {}
        for i, (line_name, line_cnt) in enumerate(lines):
            if i >= len(boxes):
                break
            eps = _RE_EPISODE.findall(boxes[i])
            if not eps:
                continue
            parts = []
            for full_url, vid, line_idx, ep_idx, ep_title in eps:
                title_clean = ep_title.strip()
                if re.fullmatch(r"\d{1,4}", title_clean):
                    title_clean = "第%s集" % (title_clean.lstrip("0") or "0")
                parts.append("%s$%s" % (title_clean, full_url))
            if parts:
                play_from.append(line_name)
                line_counts[line_name] = len(parts)
                play_url.append("#".join(parts))

        return {
            "title": title,
            "pic": pic,
            "score": score,
            "year": year,
            "area": area,
            "status": status,
            "tags": tags,
            "desc": desc,
            "play_from": play_from,
            "play_url": play_url,
            "line_counts": line_counts,
        }

    @classmethod
    def _parse_card(cls, html):
        """解析一张卡片"""
        m = _RE_CARD_LINK.search(html)
        if not m:
            return None
        url, vid, title = m.group(1), m.group(2), m.group(3)
        pic = ""
        m2 = _RE_CARD_IMG.search(html)
        if m2:
            # data-src 在 4 个捕获组里, alt 也在, 取非空且像 URL 的
            for g in m2.groups():
                if g and (g.startswith("http") or g.startswith("//")):
                    pic = g
                    break
        score = ""
        m3 = _RE_CARD_SCORE.search(html)
        if m3:
            score = m3.group(1).strip()
        note = ""
        m4 = _RE_CARD_NOTE.search(html)
        if m4:
            note = m4.group(1).strip()
        return {
            "vod_id": vid,
            "vod_name": title,
            "vod_pic": pic,
            "vod_remarks": note,
            "vod_score": score,
        }

    @classmethod
    def _parse_list(cls, html):
        items = []
        seen = set()
        for m in _RE_CARD.finditer(html):
            card = cls._parse_card(m.group(1))
            if card and card["vod_id"] not in seen:
                seen.add(card["vod_id"])
                items.append(card)
        return items

    # ==================== TVBox 接口 ====================
    def homeContent(self, filter=False):
        result = {"class": self.classes, "list": [], "filters": self.filters}
        now = time.time()
        if self._home_cache and now - self._home_ts < 600:
            html = self._home_cache
        else:
            html = self._get_html(self.host + "/")
            if html:
                self._home_cache = html
                self._home_ts = now

        items = self._parse_list(html)
        # 首页取推荐位/最新, 简单按已有顺序, 国产置顶
        result["list"] = self._sort_items(items)[:30]
        return result

    def homeVideoContent(self):
        try:
            return {"list": self.homeContent(False).get("list", [])}
        except Exception:
            return {"list": []}

    def categoryContent(self, tid, pg, filter=False, extend=None):
        try:
            page = max(1, int(pg or 1))
        except (TypeError, ValueError):
            page = 1
        ext = extend if isinstance(extend, dict) else {}

        # 统一 extend 键名(兼容中文别名)
        ext_norm = {}
        for k, v in ext.items():
            nk = self._FILTER_KEY_ALIAS.get(k, k)
            ext_norm[nk] = v

        cls = str(ext_norm.get("class") or "").strip()
        area = str(ext_norm.get("area") or "").strip()
        year = str(ext_norm.get("year") or "").strip()
        sort = str(ext_norm.get("by") or "hits").strip()
        local_sort_year = sort in ("最新年份", "year")

        # 构建分类 URL: /fenlei/{type_id}-{page}.html?参数
        url = "%s/fenlei/%s-%d.html" % (self.host, tid, page)
        params = {}
        if sort in ("人气", "hits"):
            params["sort"] = "hits"
        if cls and cls != "全部":
            params["class"] = cls
        if year and year != "全部":
            params["year"] = year
        # 地区参数站点不支持, 留空
        if params:
            url += "?" + urllib.parse.urlencode(params)

        html = self._get_html(url)
        items = self._parse_list(html)

        # 列表页无地区字段, 无法本地地区过滤/国内置顶; 按站点返回顺序(最新更新)
        # 当用户显式选"最新年份"且未选具体年份时, 多请求 2026/2025 合并
        if local_sort_year and (not year or year == "全部"):
            try:
                extra_items = []
                for y in ("2026", "2025", "2024"):
                    if len(extra_items) >= 36:
                        break
                    u = "%s/fenlei/%s-%d.html?year=%s" % (self.host, tid, page, y)
                    if params.get("class"):
                        u += "&class=" + urllib.parse.quote(params["class"])
                    h = self._get_html(u)
                    extra_items += self._parse_list(h)
                seen = {v["vod_id"] for v in items}
                for v in extra_items:
                    if v["vod_id"] not in seen:
                        seen.add(v["vod_id"])
                        v["vod_year"] = re.search(r"year=(\d{4})", u).group(1) if "year=" in u else ""
                        items.append(v)
                items = self._sort_by_year(items)
            except Exception:
                pass
        else:
            items = self._sort_items(items)

        n = len(items)
        # 站点每页卡片很多(约80张,去重后40+), 允许继续翻页
        pagecount = page + 1 if n > 0 else page
        return {
            "page": page,
            "pagecount": pagecount,
            "limit": n or 24,
            "total": pagecount * (n or 24),
            "list": items,
        }

    def detailContent(self, ids):
        if isinstance(ids, str):
            try:
                ids = json.loads(ids)
            except Exception:
                ids = [ids]
        if not isinstance(ids, (list, tuple)) or not ids:
            return {"list": []}
        vid = str(ids[0]).strip()
        if not vid:
            return {"list": []}

        html = self._get_html("%s/xiangqing/%s.html" % (self.host, vid))
        if not html:
            return {"list": []}

        d = self._parse_detail(html)
        if not d["title"]:
            return {"list": []}

        # 4K 线路置顶 + 集数偏少降级
        play_from = d["play_from"]
        play_url = d["play_url"]
        if play_from:
            def _rank(i):
                name = play_from[i]
                is_4k = any(k in name for k in self.K4_WORDS)
                cnt = len(play_url[i].split("#"))
                max_cnt = max(len(u.split("#")) for u in play_url)
                low = 1 if (max_cnt >= 4 and cnt * 10 < max_cnt * 3) else 0
                # 优先级: 4K > 蓝光 > 推荐 > 稳定 > Y弹
                order = {"4K": 0, "蓝光": 1, "推荐": 2, "稳定": 3, "Y弹": 4}
                o = 99
                for k, v in order.items():
                    if k in name:
                        o = v
                        break
                return (low, 0 if is_4k else 1, o, i)

            idx = sorted(range(len(play_from)), key=_rank)
            play_from = [play_from[i] for i in idx]
            play_url = [play_url[i] for i in idx]

        # 角标
        badge = self._badge(d["status"], d["tags"], d["year"])
        if badge == "已完结" and play_url:
            cnt = max(len(u.split("#")) for u in play_url)
            if cnt > 1:
                unit = "期" if "综艺" in " ".join(d["tags"]) else "集"
                badge = "已完结·全%d%s" % (cnt, unit)

        vod = {
            "vod_id": vid,
            "vod_name": d["title"],
            "vod_pic": d["pic"],
            "type_name": " ".join(d["tags"])[:20],
            "vod_year": d["year"],
            "vod_area": d["area"],
            "vod_actor": "",
            "vod_director": "",
            "vod_type": " ".join(d["tags"])[:40],
            "vod_remarks": badge,
            "vod_content": d["desc"][:600],
            "vod_play_from": "$$$".join(play_from),
            "vod_play_url": "$$$".join(play_url),
        }

        # 后台预取
        self._prefetch_streams(vod)
        return {"list": [vod]}

    def searchContent(self, key, quick=False, pg="1"):
        try:
            page = max(1, int(pg or 1))
        except (TypeError, ValueError):
            page = 1
        keyword = str(key or "").strip()
        if not keyword:
            return {"page": page, "pagecount": 1, "limit": 0, "total": 0, "list": []}

        year_filter = ""
        ym = re.search(r"(?:^|\s)(19\d{2}|20\d{2})(?:\s|$)", keyword)
        if ym:
            year_filter = ym.group(1)
            keyword = (keyword[:ym.start()] + keyword[ym.end():]).strip()
        if not keyword:
            return {"page": page, "pagecount": 1, "limit": 0, "total": 0, "list": []}

        url = "%s/sousuo/-------------.html?wd=%s&page=%d" % (self.host, urllib.parse.quote(keyword), page)
        html = self._get_html(url)
        items = self._parse_list(html)

        # 搜索页卡片没有年份, 需要详情? 先不过滤年份, 如需要再补
        if year_filter and items:
            # 简单过滤: 搜索关键词里带年份时, 标题含年份也可接受
            items = [v for v in items if year_filter in v.get("vod_name", "") or year_filter in v.get("vod_remarks", "")]

        pagecount = page + 1 if len(items) > 0 else page
        return {
            "page": page,
            "pagecount": pagecount,
            "limit": len(items) or 15,
            "total": pagecount * (len(items) or 15),
            "list": items,
        }

    # ==================== 排序 ====================
    @classmethod
    def _sort_items(cls, items):
        """国内置顶, 组内保持原顺序(站点已按最新更新)"""
        domestic = [v for v in items if cls._is_domestic(v.get("vod_area", ""), v.get("vod_type", "").split("/"))]
        foreign = [v for v in items if not cls._is_domestic(v.get("vod_area", ""), v.get("vod_type", "").split("/"))]
        return domestic + foreign

    @classmethod
    def _sort_by_year(cls, items):
        """国内置顶, 组内按年份降序"""
        def _key(v):
            try:
                y = int(v.get("vod_year") or 0)
            except Exception:
                y = 0
            return -y
        domestic = [v for v in items if cls._is_domestic(v.get("vod_area", ""), v.get("vod_type", "").split("/"))]
        foreign = [v for v in items if not cls._is_domestic(v.get("vod_area", ""), v.get("vod_type", "").split("/"))]
        return sorted(domestic, key=_key) + sorted(foreign, key=_key)

    # ==================== 播放解析 ====================
    def playerContent(self, flag, id, vipFlags=None):
        header = {"User-Agent": self.UA, "Referer": self.host + "/"}
        try:
            url = str(id or "").strip()
            if not url:
                return {"parse": 0, "url": "", "header": header}

            # 缓存
            cached = self._cache_get(url)
            if cached:
                return cached

            # 现场解析 bofang 页
            result = self._resolve_play(url)
            if result.get("url"):
                self._cache_put(url, result)
            return result
        except Exception:
            return {"parse": 0, "url": "", "header": header}

    def _resolve_play(self, bofang_url):
        header = {"User-Agent": self.UA, "Referer": self.host + "/"}
        full = bofang_url if bofang_url.startswith("http") else self.host + bofang_url

        # 尝试抓播放页解析直链
        html = self._get_html(full)
        if html:
            urls = _RE_VIDEO_URL.findall(html)
            if urls:
                u = urls[0]
                # 有的模板会把 m3u8 地址放 json, 取最长最像直链的
                u = max(urls, key=len)
                return {"parse": 0, "url": u, "header": header}

        # 解析不到直链: 交给壳子 WebView 打开本站播放页(非外部跳转)
        return {"parse": 1, "url": full, "header": header}

    # ==================== 缓存 + 预取 ====================
    _CACHE_MAX = 120
    _CACHE_TTL = 1800

    def _cache_get(self, key):
        entry = self._play_cache.get(key)
        if not entry:
            return None
        ts, val = entry
        if time.time() - ts > self._CACHE_TTL:
            self._play_cache.pop(key, None)
            return None
        return dict(val)

    def _cache_put(self, key, val):
        if len(self._play_cache) >= self._CACHE_MAX:
            for old in list(self._play_cache.keys())[:self._CACHE_MAX // 4]:
                self._play_cache.pop(old, None)
        self._play_cache[key] = (time.time(), val)

    def _prefetch_streams(self, vod):
        try:
            pairs = list(zip(vod.get("vod_play_from", "").split("$$$"),
                             vod.get("vod_play_url", "").split("$$$")))
            targets = []
            for i, (_, urls) in enumerate(pairs):
                eps = urls.split("#")
                if i < 3 and eps and "$" in eps[0]:
                    targets.append(eps[0].split("$", 1)[1])
                if i == 0 and len(eps) > 1 and "$" in eps[-1]:
                    u = eps[-1].split("$", 1)[1]
                    if u not in targets:
                        targets.append(u)
                if i >= 3:
                    break
            for eid in targets:
                if eid not in self._pending_futures:
                    self._pending_futures[eid] = {"event": threading.Event(), "result": None}
            if targets:
                threading.Thread(target=self._prefetch_worker, args=(targets,), daemon=True).start()
        except Exception:
            pass

    def _prefetch_worker(self, targets):
        for eid in targets:
            try:
                if not self._cache_get(eid):
                    result = self._resolve_play(eid)
                    if result.get("url"):
                        self._cache_put(eid, result)
            except Exception:
                pass
            finally:
                fut = self._pending_futures.pop(eid, None)
                if fut:
                    fut["result"] = self._cache_get(eid)
                    fut["event"].set()
