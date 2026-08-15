# -*- coding: utf-8 -*-
# ============================================================
#  遮天九秘 · TVBox爬虫脚本（自动生成）
#  目标站: https://c453sddsc451azx.top（布布追剧）
#  注入九秘: 临, 兵, 斗, 者, 皆, 阵, 前
#  解码: 纯Python重建WASM签名（SHA-256 of finger/.../v=1）
# ============================================================
import sys, re, json, base64, html as html_module, os, threading, time, hashlib
from urllib.parse import quote, unquote, urljoin
try:
    from base.spider import Spider as BaseSpider
except ImportError:
    class BaseSpider: pass
try:
    import requests
except ImportError:
    requests = None

# ============================================================
#  WASM解码参数（逆向所得常量）
# ============================================================
DECODE_FINGER = "WF-2c064bc5b3400788f31b848849bc3a60f835423ba2dfe69d7ea93974c216e4f2"
DECODE_ID = "com.web.player"
DECODE_SK = "WEB-50a8e9c84a1dc05669a692ded99a2dac46527229e607a7be15db88dbc59059d1"
API_HEADERS = {
    "Accept": "application/json",
    "X-Client": "8f3d2a1c7b6e5d4c9a0b1f2e3d4c5b6a",
    "web-sign": "f65f3a83d6d9ad6f",
}
FALLBACK_CLASSES = [
    {"type_id": "1", "type_name": "电影"},
    {"type_id": "2", "type_name": "剧集"},
    {"type_id": "3", "type_name": "动漫"},
    {"type_id": "4", "type_name": "综艺"},
]
CATE_NAME = {"1": "电影", "2": "剧集", "3": "动漫", "4": "综艺"}


class Spider(BaseSpider):
    def __init__(self):
        super().__init__()
        self.host = "https://c453sddsc451azx.top"
        self.headers = dict(API_HEADERS)
        self.headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36"
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        self.cache = {}

    # ---------- 基础 ----------
    def init(self, extend):
        pass

    def getName(self):
        return "BuBuZhuiJu"

    def isVideoFormat(self, url):
        return ".m3u8" in url or ".mp4" in url

    def manualVideoCheck(self):
        return False

    # ---------- 请求辅助 ----------
    def _get_json(self, path, params=None):
        r = self.session.get(self.host + path, params=params, timeout=15)
        return r.json()

    def _clean_title(self, raw):
        if not raw:
            return "未知标题"
        text = re.sub(r"<[^>]+>", "", raw)
        text = html_module.unescape(text)
        text = re.sub(r"\s+", " ", text).strip()
        return text or "未知标题"

    def _fix_pic(self, url):
        if not url:
            return ""
        if url.startswith("//"):
            url = "https:" + url
        elif url.startswith("/"):
            url = self.host + url
        return url

    # ---------- 解码 ----------
    @staticmethod
    def _varint(n):
        out = bytearray()
        while True:
            b = n & 0x7f
            n >>= 7
            if n:
                out.append(b | 0x80)
            else:
                out.append(b)
                return bytes(out)

    @staticmethod
    def _bytes_field(num, data):
        return bytes([num << 3 | 2]) + Spider._varint(len(data)) + data

    @staticmethod
    def _varint_field(num, val):
        return bytes([num << 3 | 0]) + Spider._varint(val)

    def _build_decode_request(self, url, flag, now=None, nonce_hex=None):
        if now is None:
            now = int(time.time())
        if nonce_hex is None:
            nonce_hex = os.urandom(16).hex()
        sign_src = ("finger=%s&id=%s&nonce=%s&sk=%s&time=%d&v=1"
                    % (DECODE_FINGER, DECODE_ID, nonce_hex, DECODE_SK, now))
        sign = hashlib.sha256(sign_src.encode("utf-8")).hexdigest().upper()
        buf = bytearray()
        buf += self._bytes_field(1, url.encode("utf-8"))
        buf += self._bytes_field(2, flag.encode("utf-8"))
        buf += self._varint_field(3, now)
        buf += self._bytes_field(4, nonce_hex.encode("utf-8"))
        buf += self._bytes_field(5, sign.encode("utf-8"))
        buf += self._bytes_field(6, DECODE_ID.encode("utf-8"))
        buf += self._varint_field(7, 1)
        return bytes(buf)

    def _parse_proto(self, data):
        i = 0
        fields = {}
        while i < len(data):
            tag = data[i]
            i += 1
            wt = tag & 7
            fno = tag >> 3
            if wt == 2:
                ln = 0
                sh = 0
                while True:
                    x = data[i]
                    i += 1
                    ln |= (x & 0x7f) << sh
                    if not x & 0x80:
                        break
                    sh += 7
                fields[fno] = data[i:i + ln]
                i += ln
            elif wt == 0:
                v = 0
                sh = 0
                while True:
                    x = data[i]
                    i += 1
                    v |= (x & 0x7f) << sh
                    if not x & 0x80:
                        break
                    sh += 7
                fields[fno] = v
            else:
                break
        return fields

    def decode_url(self, code, flag):
        key = (code, flag)
        if key in self.cache:
            return self.cache[key]
        body = self._build_decode_request(code, flag)
        r = self.session.post(self.host + "/api.php/web/decode/url",
                              data=body,
                              headers={"Content-Type": "application/x-protobuf"},
                              timeout=20)
        fields = self._parse_proto(r.content)
        if fields.get(1) != 1:
            return ""
        for k, v in fields.items():
            if isinstance(v, bytes) and b"http" in v:
                idx = v.index(b"http")
                m3u8 = v[idx:].decode("utf-8", "replace").rstrip("\x00")
                self.cache[key] = m3u8
                return m3u8
        return ""

    # ---------- 首页 ----------
    def homeContent(self, filter):
        try:
            return self._homeContent_inner(filter)
        except Exception as e:
            print(f"[临字秘] homeContent治愈: {e}")
            return {"class": FALLBACK_CLASSES}

    def _homeContent_inner(self, filter):
        d = self._get_json("/api.php/web/index/home")
        data = d.get("data") or {}
        cats = []
        for c in data.get("categories") or []:
            cats.append({"type_id": str(c.get("type_id")), "type_name": c.get("type_name")})
        if not cats:
            cats = FALLBACK_CLASSES
        return {"class": cats}

    # ---------- 分类 ----------
    def categoryContent(self, tid, pg, filter, extend):
        try:
            return self._categoryContent_inner(tid, pg, filter, extend)
        except Exception as e:
            print(f"[者字秘] categoryContent治愈: {e}")
            return {"list": [], "page": int(pg) if pg else 1, "pagecount": 1, "limit": 0, "total": 0}

    def _categoryContent_inner(self, tid, pg, filter, extend):
        params = {"page": int(pg or 1), "sort": "hits"}
        tname = CATE_NAME.get(str(tid))
        if tname:
            params["type_name"] = tname
        d = self._get_json("/api.php/web/filter/vod", params=params)
        items = d.get("data") or []
        videos = []
        for it in items:
            videos.append({
                "vod_id": it.get("vod_id"),
                "vod_name": it.get("vod_name"),
                "vod_pic": self._fix_pic(it.get("vod_pic")),
                "vod_remarks": it.get("vod_remarks") or "",
            })
        page = int(pg or 1)
        has_more = len(items) >= 18
        return {"list": videos, "page": page, "pagecount": page + 1 if has_more else page, "limit": 24, "total": page * 24 if has_more else (page - 1) * 24 + len(items)}

    # ---------- 详情 ----------
    def detailContent(self, ids):
        try:
            return self._detailContent_inner(ids)
        except Exception as e:
            print(f"[兵字秘] detailContent治愈: {e}")
            return {"list": []}

    def _detailContent_inner(self, ids):
        vod_id = ids[0] if ids and ids[0] else "1"
        if vod_id.startswith("http"):
            m = re.search(r"/(\d+)\.html", vod_id)
            vod_id = m.group(1) if m else vod_id
        d = self._get_json("/api.php/web/vod/get_detail", params={"vod_id": vod_id})
        items = d.get("data") or []
        detail = {}
        if items:
            detail = self._parse_detail(items[0])
        return {"list": [detail] if detail else []}

    def _parse_detail(self, item):
        vod_id = item.get("vod_id")
        play_from = item.get("vod_play_from") or ""
        play_url = item.get("vod_play_url") or ""
        return {
            "vod_id": str(vod_id),
            "vod_name": item.get("vod_name") or "",
            "vod_pic": self._fix_pic(item.get("vod_pic")),
            "vod_remarks": item.get("vod_remarks") or "",
            "vod_content": self._clean_title(item.get("vod_content") or ""),
            "vod_year": item.get("vod_year") or "",
            "vod_actor": item.get("vod_actor") or "",
            "vod_director": item.get("vod_director") or "",
            "vod_area": item.get("vod_area") or "",
            "vod_play_from": play_from,
            "vod_play_url": play_url,
        }

    # ---------- 播放 ----------
    def playerContent(self, flag, id, vipFlags=None):
        try:
            if not id:
                return {"parse": 0, "url": "", "header": {}}
            m3u8 = self.decode_url(id, flag)
            if not m3u8:
                return {"parse": 0, "url": id, "header": {}}
            return {"parse": 0, "url": m3u8, "header": {"User-Agent": self.headers["User-Agent"]}}
        except Exception as e:
            print(f"[斗字秘] playerContent治愈: {e}")
            return {"parse": 0, "url": id, "header": {}}

    # ---------- 搜索 ----------
    def searchContent(self, key, quick, pg="1"):
        try:
            d = self._get_json("/api.php/web/search/index", params={"wd": key})
            items = d.get("data") or []
            videos = []
            for it in items:
                videos.append({
                    "vod_id": it.get("vod_id"),
                    "vod_name": it.get("vod_name"),
                    "vod_pic": self._fix_pic(it.get("vod_pic")),
                    "vod_remarks": it.get("vod_remarks") or "",
                })
            return {"list": videos, "page": int(pg), "pagecount": 1}
        except Exception as e:
            print(f"[皆字秘] searchContent治愈: {e}")
            return {"list": [], "page": 1}

    # ---------- 其它 ----------
    def homeVideoContent(self):
        try:
            d = self._get_json("/api.php/web/index/home")
            data = d.get("data") or {}
            seen, videos = set(), []
            for c in data.get("categories") or []:
                for it in c.get("videos") or []:
                    vid = it.get("vod_id")
                    if vid in seen:
                        continue
                    seen.add(vid)
                    videos.append({
                        "vod_id": vid,
                        "vod_name": it.get("vod_name") or "",
                        "vod_pic": self._fix_pic(it.get("vod_pic")),
                        "vod_remarks": it.get("vod_remarks") or "",
                    })
            return {"list": videos, "page": 1}
        except Exception as e:
            print(f"[前字秘] homeVideoContent治愈: {e}")
            return {"list": []}
