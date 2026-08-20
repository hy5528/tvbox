# -*- coding: utf-8 -*-
# ============================================================
#  漫闪 (Manshan) · TVBox 爬虫脚本(由 manshan.jar 反编译重建)
#  原 dex 类: com.github.catvod.spider.Manshan
#  重建日期: 2026-08-16
#  适配 TVBox / OK影视 / 影视仓 等空壳影视App
# ------------------------------------------------------------
#  接口规范 (CatVod Spider):
#   - init(extend)              → 初始化,允许 ext={"deviceId": "..."}
#   - homeContent(filter)       → {"class":[...], "filters":{...}, "list":[...]}
#   - homeVideoContent()        → {"list":[...]}
#   - categoryContent(tid,pg,filter,extend) → {"list":[...], "page":..., "pagecount":..., ...}
#   - detailContent(ids)        → {"list":[{...}]}
#   - playerContent(flag,id,vipFlags) → {"parse":..., "url":..., "header":...}
#   - searchContent(key,quick,pg) → {"list":[...], ...}
# ============================================================
import re
import sys
import json
import time
import uuid
import base64
import hashlib
import threading
from urllib.parse import urlencode, quote, unquote, urlparse

try:
    from base.spider import Spider as BaseSpider
except ImportError:
    class BaseSpider:
        def init(self, extend=""):
            pass
        def getName(self):
            return ""
        def isVideoFormat(self, url):
            return False
        def manualVideoCheck(self):
            return False
        def destroy(self):
            pass
        def localProxy(self, params):
            return None

try:
    import requests
    from requests.adapters import HTTPAdapter
    from requests.packages.urllib3.util.retry import Retry
    requests.packages.urllib3.disable_warnings()
except Exception:
    requests = None
    HTTPAdapter = None
    Retry = None

try:
    from Crypto.Cipher import AES
    from Crypto.Util.Padding import unpad
    _HAS_CRYPTO = True
except Exception:
    _HAS_CRYPTO = False


# ============================================================
#  反编译所得常量 (与 dex 中 Manshan.g(arr,key) 的解密结果一致)
# ============================================================
HOST           = "https://app.manshan.fun"
PATH_LIST      = "/app/video/getList"            # 分类列表
PATH_CATEGORY  = "/app/category/getVideoList"   # 分类筛选
PATH_DETAIL    = "/app/video/getDetail"         # 详情
PATH_SEARCH    = "/app/video/search"            # 搜索
PATH_EPISODE   = "/app/episode/jx"              # 解析取 m3u8

# AES-ECB 解密 key (Manshan.g([I i, 0x25))
AES_KEY_BYTES  = b"zhuhongleipeipei"

# 签名 salt (Manshan.g([I h, 0x79))
SIGN_SALT      = "zhl's river app"

# 4 个 tab id(原 jar 写死,不在 homeContent 中动态请求)
TAB_RECOMMEND  = "3740c6fc9f992bd660303d2a23f6ebb5"
TAB_JAPAN_ANI  = "d1832ba165d0538f8c72ea09e84fd413"
TAB_CHINA_ANI  = "b7cbe964263375d9d825e452deb16a61"
TAB_4K         = "6ee3bcd148d1dcb98550d00b93232f24"

# 固定的"分类"伪分类(用 sort/category/genres/year 筛选用)
TAB_FILTERS    = "__category__"

DOU_REFERER    = "@Referer=https://movie.douban.com/"

DEFAULT_HEADERS = {
    "User-Agent": "Dart/3.11 (dart:io)",
    "Accept":     "application/json",
}

# 4 个 tab 对应标题
TABS = [
    {"type_id": TAB_RECOMMEND, "type_name": "推荐"},
    {"type_id": TAB_JAPAN_ANI, "type_name": "日漫"},
    {"type_id": TAB_CHINA_ANI, "type_name": "国漫"},
    {"type_id": TAB_4K,        "type_name": "4K"},
    {"type_id": TAB_FILTERS,   "type_name": "分类"},
]

# filters(对应原 jar 静态常量 d())
FILTER_DEFS = [
    ("sort",     "排序", "最新,最热,好评"),
    ("category", "分类", "全部,国产动漫,日韩动漫,港台动漫,欧美动漫,动漫电影,国产剧,欧美剧,韩剧,港剧,日剧,其他"),
    ("genres",   "类型", "全部,喜剧,动画,短片,家庭,儿童,奇幻,剧情,运动,科幻,动作,爱情,歌舞,音乐,悬疑,冒险,战争,历史,恐怖,惊悚,古装,犯罪,西部,灾难,武侠,戏曲,传记,同性,纪录片,短剧,生活,都市,未知,脱口秀,热血,校园"),
    ("year",     "年份", "全部,2030,2028,2027,2026,2025,2024,2023,2022,2021,2020,2019,2018,2017,2016,2015,2014,2013,2012,2011,2010,2009,2008,2007,2006,2005,2004,2003,2002,2001,2000"),
]


# ============================================================
#  Spider
# ============================================================
class Spider(BaseSpider):
    def __init__(self):
        super().__init__()
        self.siteKey  = "manshan"
        self.deviceId = "tvbox-" + uuid.uuid4().hex[:16]
        self.last_ts  = 0
        self.last_call = 0.0
        self._lock    = threading.Lock()
        self._cache   = {}          # cache[cacheKey] = (ts, json_str)
        self._http    = None
        self._init_session()

    # ---------- 基础 ----------
    def getName(self):
        return "漫闪"

    def init(self, extend=""):
        """原 jar:init(Context, ext) — 取 deviceId;失败则 'tvbox-'+UUID[:16]"""
        try:
            if extend and extend.strip().startswith("{"):
                obj = json.loads(extend)
                did = obj.get("deviceId")
                if did:
                    self.deviceId = str(did)
        except Exception:
            pass
        # 触发一次 home,跟原 jar 行为一致
        try:
            self.homeContent(False)
        except Exception:
            pass

    def isVideoFormat(self, url):
        if not url:
            return False
        u = url.lower()
        return (".m3u8" in u) or (".mp4" in u) or ("/mpegurl" in u) or ("application/vnd.apple.mpegurl" in u)

    def manualVideoCheck(self):
        return False

    def destroy(self):
        try:
            if self._http:
                self._http.close()
        except Exception:
            pass

    def _init_session(self):
        if requests is None:
            return
        s = requests.Session()
        s.headers.update(DEFAULT_HEADERS)
        if HTTPAdapter and Retry:
            r = Retry(total=2, backoff_factor=0.3,
                      status_forcelist=[500, 502, 503, 504])
            ad = HTTPAdapter(max_retries=r, pool_connections=4, pool_maxsize=8)
            s.mount("http://", ad)
            s.mount("https://", ad)
        self._http = s

    # ---------- 签名 / 限速 ----------
    def _sign(self, path, ts_str):
        """sign = base64( md5(time + path + salt) )"""
        h = hashlib.md5()
        h.update(ts_str.encode("utf-8"))
        h.update(path.encode("utf-8"))
        h.update(SIGN_SALT.encode("utf-8"))
        return base64.urlsafe_b64encode(h.digest()).decode("ascii").rstrip("=")

    def _throttle(self, key):
        """原 jar:两次同 path 请求至少 250ms,且同一时间戳每秒最多 1 次"""
        with self._lock:
            now = time.time()
            # 距上次任何请求至少 0.25s
            gap = now - self.last_call
            if gap < 0.25:
                time.sleep(0.25 - gap)
            # 同 path 限制 1s/次
            ts = int(time.time())
            if self.last_ts == ts and key in getattr(self, "_last_keys", set()):
                time.sleep(0.03)
                ts = int(time.time())
            self.last_call = time.time()
            self.last_ts = ts
            if not hasattr(self, "_last_keys"):
                self._last_keys = set()
            self._last_keys = {key}

    # ---------- 加密请求 ----------
    def _aes_decrypt_str(self, b64_text):
        """AES/ECB/PKCS5Padding 解密,失败返回 None"""
        if not _HAS_CRYPTO:
            return None
        try:
            raw = base64.b64decode(b64_text)
            cipher = AES.new(AES_KEY_BYTES, AES.MODE_ECB)
            out = unpad(cipher.decrypt(raw), AES.block_size)
            return out.decode("utf-8", "replace")
        except Exception:
            return None

    def _request(self, path, params=None, post=False, encrypted=False, use_cache=True):
        """对应原 jar: a(path, map, encrypt, isPost)
        - encrypted=True 走 /app/episode/jx,响应 base64 后再 AES 解密
        - 其它路径直接拿 JSON
        """
        # 有序参数
        params = params or {}
        cache_key = ("P" if post else "G") + path + "|" + json.dumps(params, ensure_ascii=False, sort_keys=False)
        if use_cache:
            hit = self._cache.get(cache_key)
            if hit and (time.time() - hit[0] < 2.0):
                return hit[1]

        self._throttle(path)

        # 1. 构造 query string(顺序按入参 map 顺序)
        parts = []
        for k, v in params.items():
            if v is None or v == "":
                continue
            parts.append(quote(str(k), safe="") + "=" + quote(str(v), safe=""))
        ts = int(time.time() * 1000)
        sign = self._sign(path, str(ts))
        parts.append("sign=" + quote(sign, safe=""))
        parts.append("time=" + str(ts))
        url = HOST + path + "?" + "&".join(parts)

        # 2. HTTP
        text = None
        if self._http is not None:
            try:
                if post:
                    r = self._http.post(url, data="", timeout=(7, 15), verify=False)
                else:
                    r = self._http.get(url, timeout=(7, 15), verify=False)
                # 解压
                r.encoding = "utf-8"
                text = r.text
            except Exception as e:
                sys.stderr.write("[manshan] request error: %s\n" % e)
                return None
        else:
            # stdlib fallback
            try:
                import urllib.request, gzip
                req = urllib.request.Request(url, data=b"" if post else None,
                                             method="POST" if post else "GET")
                req.add_header("User-Agent", DEFAULT_HEADERS["User-Agent"])
                req.add_header("Accept", DEFAULT_HEADERS["Accept"])
                with urllib.request.urlopen(req, timeout=11) as resp:
                    raw = resp.read()
                    if resp.headers.get("Content-Encoding", "").lower() == "gzip":
                        raw = gzip.decompress(raw)
                    text = raw.decode("utf-8", "replace")
            except Exception as e:
                sys.stderr.write("[manshan] stdlib error: %s\n" % e)
                return None

        if text is None:
            return None
        text = text.strip()
        if not text:
            return None

        # 3. 加密响应 (所有接口都加密了)
        if not text.lstrip().startswith('{') and not text.lstrip().startswith('['):
            dec = self._aes_decrypt_str(text)
            if dec is not None:
                if '"code":-1' in dec:
                    raise RuntimeError("API rejected request")
                text = dec
        elif encrypted:
            dec = self._aes_decrypt_str(text)
            if dec is None:
                return None
            if '"code":-1' in dec:
                raise RuntimeError("API rejected request")
            text = dec

        # 4. 缓存
        if use_cache:
            self._cache[cache_key] = (time.time(), text)
        return text

    def _get_json(self, path, params=None, post=False, encrypted=False):
        text = self._request(path, params=params, post=post, encrypted=encrypted)
        if not text:
            return None
        try:
            return json.loads(text)
        except Exception:
            return None

    # ---------- 字段映射 n(JSONObject) ----------
    @staticmethod
    def _map_video(item):
        """对应原 jar: n(JSONObject) — 字段名重命名 + 拼 douban Referer"""
        if not item:
            return None
        out = {
            "vod_id":      str(item.get("id", "") or ""),
            "vod_name":    item.get("title", "") or "",
            "vod_remarks": item.get("remarks", "") or "",
        }
        # 兼容更多可能的封面字段名
        pic = (
            item.get("pic") or 
            item.get("thumb") or 
            item.get("cover") or 
            item.get("img") or 
            item.get("image") or 
            item.get("poster") or 
            ""
        )
        # 修正：只有当链接确实是豆瓣图片时，才追加 douban Referer，避免破坏其他 CDN 链接
        if pic and "doubanio.com" in pic and DOU_REFERER not in pic:
            pic = pic + DOU_REFERER
        out["vod_pic"] = pic or ""
        
        # 透传其它常用字段
        for k_src, k_dst in (("year", "vod_year"),
                              ("area", "vod_area"),
                              ("director", "vod_director"),
                              ("actor", "vod_actor"),
                              ("des", "vod_content"),
                              ("content", "vod_content"),
                              ("type", "vod_class"),
                              ("score", "vod_score")):
            v = item.get(k_src)
            if v not in (None, ""):
                out[k_dst] = v
        return out

    @staticmethod
    def _expand_list(arr):
        """对应原 jar: h(JSONArray) — 展开 videoList 子项 + 用 id 去重"""
        seen = set()
        out = []
        if not arr:
            return out
        for it in arr:
            if not isinstance(it, dict):
                continue
            sub = it.get("videoList")
            if isinstance(sub, list) and sub:
                for v in sub:
                    vid = str(v.get("id", "") or "")
                    if not vid or vid in seen:
                        continue
                    seen.add(vid)
                    out.append(v)
            else:
                vid = str(it.get("id", "") or "")
                if not vid or vid in seen:
                    continue
                seen.add(vid)
                out.append(it)
        return out

    # ---------- 首页 ----------
    def homeContent(self, filter):
        try:
            classes = list(TABS)
            # 拉每个 tab 的首页内容,塞到 list
            items = []
            for tab in TABS[:4]:
                try:
                    j = self._get_json(PATH_LIST, params={
                        "tabId": tab["type_id"],
                        "pageNo": "1",
                        "pageSize": "21",
                    })
                    arr = (j or {}).get("data") or []
                    items.extend(self._expand_list(arr))
                except Exception:
                    continue
            videos = []
            for it in items:
                m = self._map_video(it)
                if m:
                    videos.append(m)
            return {"class": classes, "list": videos, "filters": self._build_filters()}
        except Exception as e:
            sys.stderr.write("[manshan] homeContent: %s\n" % e)
            return {"class": TABS, "list": [], "filters": self._build_filters()}

    def homeVideoContent(self):
        return self.homeContent(False)

    def _build_filters(self):
        out = {}
        for key, name, csv in FILTER_DEFS:
            vals = [v for v in csv.split(",") if v]
            out[key] = [
                {"key": v, "name": v, "value": v if v != "全部" else ""}
                for v in vals
            ]
            out[key][0]["name"] = name
        return {TAB_FILTERS: out}

    # ---------- 分类 ----------
    def categoryContent(self, tid, pg, filter, extend):
        try:
            pg = str(pg or 1)
            ext = extend or {}
            # 分类筛选
            if tid == TAB_FILTERS:
                p = {
                    "sort":     ext.get("sort") or "最新",
                    "category": ext.get("category") or "全部",
                    "genres":   ext.get("genres") or "全部",
                    "year":     ext.get("year") or "全部",
                    "pageNo":   pg,
                    "pageSize": "21",
                }
                j = self._get_json(PATH_CATEGORY, params=p, post=True)
            else:
                j = self._get_json(PATH_LIST, params={
                    "tabId":    tid,
                    "pageNo":   pg,
                    "pageSize": "21",
                })
            data = (j or {}).get("data") or []
            arr = self._expand_list(data) if isinstance(data, list) else []
            videos = [self._map_video(it) for it in arr]
            videos = [v for v in videos if v]
            page = int(pg)
            pagecount = page if len(arr) < 21 else page + 1
            return {
                "list": videos,
                "page": page,
                "pagecount": pagecount,
                "limit": 21,
                "total": page * 21 if pagecount > page else (page - 1) * 21 + len(arr),
            }
        except Exception as e:
            sys.stderr.write("[manshan] categoryContent: %s\n" % e)
            return {"list": [], "page": 1, "pagecount": 1, "limit": 21, "total": 0}

    # ---------- 详情 ----------
    def detailContent(self, ids):
        try:
            if not ids:
                return {"list": []}
            vid = ids[0]
            j = self._get_json(PATH_DETAIL, params={"videoId": vid})
            data = (j or {}).get("data")
            if not data:
                return {"list": []}
            v = self._map_video(data) or {}
            eps = data.get("episodeList") or []
            # 拼装 vod_play_url: title1$eid1#title2$eid2#...(TVBox标准格式)
            play_parts = []
            for ep in eps:
                if not isinstance(ep, dict):
                    continue
                t = ep.get("title", "") or ""
                eid = ep.get("id", "") or ""
                vt = data.get("title", "") or ""
                play_parts.append("%s$%s@@%s" % (t, eid, vt))
            v["vod_play_from"] = "漫闪"
            v["vod_play_url"]  = "#".join(play_parts)
            v["vod_content"]   = v.get("vod_content") or data.get("des") or data.get("content") or ""
            return {"list": [v]}
        except Exception as e:
            sys.stderr.write("[manshan] detailContent: %s\n" % e)
            return {"list": []}

    # ---------- 播放 ----------
    def playerContent(self, flag, id, vipFlags=None):
        try:
            if not id:
                return {"parse": 0, "url": "", "header": {}}
            # id 形如 "episodeId@@videoTitle" 或 "episodeId"
            parts = id.split("@@", 1)
            episode_id = parts[0]
            video_title = unquote(parts[1], "utf-8") if len(parts) > 1 else ""

            p = {
                "videoTitle": video_title,
                "episodeId":  episode_id,
                "deviceId":   self.deviceId,
            }
            j = self._get_json(PATH_EPISODE, params=p, post=True, encrypted=True)
            data = (j or {}).get("data") if isinstance(j, dict) else None
            if not data:
                return {"parse": 0, "url": "", "header": {}}
            res = data.get("resolutionList") or []
            if not res:
                return {"parse": 0, "url": "", "header": {}}
            # 优先选 4k
            best = None
            for r in res:
                if (r.get("name") or "").lower() == "4k":
                    best = r
                    break
            if best is None:
                best = res[0]
            url = best.get("url") or ""
            if not url:
                return {"parse": 0, "url": "", "header": {}}

            headers = {}
            ph = data.get("playHeader") or {}
            ua = ph.get("User-Agent") or ph.get("UserAgent") or ""
            if ua:
                headers["User-Agent"] = ua
            if ph.get("Referer"):
                headers["Referer"] = ph["Referer"]
            if ph.get("Cookie"):
                headers["Cookie"] = ph["Cookie"]

            return {"parse": 0, "url": url, "header": headers}
        except Exception as e:
            sys.stderr.write("[manshan] playerContent: %s\n" % e)
            return {"parse": 0, "url": id or "", "header": {}}

    # ---------- 搜索 ----------
    def searchContent(self, key, quick, pg="1"):
        try:
            pg = str(pg or 1)
            j = self._get_json(PATH_SEARCH, params={"keyWord": key, "page": pg})
            data = (j or {}).get("data") or []
            arr = self._expand_list(data) if isinstance(data, list) else []
            videos = [self._map_video(it) for it in arr]
            videos = [v for v in videos if v]
            return {"list": videos, "page": int(pg), "pagecount": 1}
        except Exception as e:
            sys.stderr.write("[manshan] searchContent: %s\n" % e)
            return {"list": [], "page": 1}


# ============================================================
#  自检:本地可运行时跑一下冒烟
# ============================================================
if __name__ == "__main__":
    s = Spider()
    print("name:", s.getName())
    print("deviceId:", s.deviceId)
    print("homeContent:", json.dumps(s.homeContent(False), ensure_ascii=False)[:200], "...")
    print("searchContent:", json.dumps(s.searchContent("斗罗", False), ensure_ascii=False)[:200], "...")
