# -*- coding: utf-8 -*-
# 云朵影视 - y23xxa23duo12.xyz
# by TRAE
# Vue SPA + 苹果CMS API + 解析播放 (需登录Cookie)
import re
import sys
import json
import time
import os
import hashlib
import urllib.request
import urllib.parse
import ssl
from urllib.parse import quote

sys.path.append('..')
from base.spider import Spider


class Spider(Spider):

    # ---- decode/url 签名 (逆向自 web_app_wasm) ----
    DEV = "com.web.player.6c3b998c"
    ID = "WF-9e14d752872961ca1f5f125a6607c2712535b8d8b5c1294423c2da8436a41000"
    SK = "WEB-df5526941b0e3165d0a8485119ca3628b45f2b4a5c4b888bf01645a7060e1638"

    def getName(self):
        return "云朵影视"

    def init(self, extend=""):
        self.host = "https://y23xxa23duo12.xyz"
        self.api = f"{self.host}/api.php/web"
        self.ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        self.web_sign = "yda81x6d9ad3c4s"
        self.x_client = "8f3d2a1c7b6e5d4c9a0b1f2e3d4c5b6a"
        # 登录账号
        self.username = "suixin"
        self.password = "123456"
        # Session cookie缓存
        self._session_cookie = None
        # SSL
        self._ssl_ctx = ssl.create_default_context()
        self._ssl_ctx.check_hostname = False
        self._ssl_ctx.verify_mode = ssl.CERT_NONE

    def getDependence(self):
        return []

    def isVideoFormat(self, url):
        pass

    def manualVideoCheck(self):
        pass

    def action(self, action):
        pass

    def destroy(self):
        pass

    def _get_cookie(self):
        """登录获取session cookie"""
        if self._session_cookie:
            return self._session_cookie
        try:
            login_url = f"{self.api}/account/login"
            body = json.dumps({"username": self.username, "password": self.password}).encode('utf-8')
            req = urllib.request.Request(login_url, data=body, method='POST')
            req.add_header("Content-Type", "application/json")
            req.add_header("Accept", "application/json")
            req.add_header("X-Client", self.x_client)
            req.add_header("web-sign", self.web_sign)
            req.add_header("User-Agent", self.ua)
            resp = urllib.request.urlopen(req, timeout=15, context=self._ssl_ctx)
            # 提取Set-Cookie
            cookie_header = resp.headers.get("Set-Cookie", "")
            if cookie_header:
                # 解析 cookie值
                for part in cookie_header.split(';'):
                    part = part.strip()
                    if '=' in part and 'yunduo_web_session' in part:
                        self._session_cookie = part
                        break
            if not self._session_cookie:
                # 尝试从headers列表中获取
                for h in resp.headers.get_all("Set-Cookie") or []:
                    if 'yunduo_web_session' in h:
                        val = h.split(';')[0]
                        self._session_cookie = val
                        break
        except Exception as e:
            print(f'login error: {e}')
        return self._session_cookie or ""

    def fetch_html(self, url):
        """发送带认证的HTTP请求"""
        try:
            req = urllib.request.Request(url)
            req.add_header("User-Agent", self.ua)
            req.add_header("Accept", "application/json")
            req.add_header("X-Client", self.x_client)
            req.add_header("web-sign", self.web_sign)
            cookie = self._get_cookie()
            if cookie:
                req.add_header("Cookie", cookie)
            resp = urllib.request.urlopen(req, timeout=15, context=self._ssl_ctx)
            return resp.read().decode('utf-8', errors='replace')
        except Exception as e:
            print(f'fetch_html error: {e}')
            return ""

    # ---- decode/url protobuf 工具 ----
    def _proto_varint(self, n):
        out = bytearray()
        while True:
            x = n & 0x7f
            n >>= 7
            if n:
                out.append(x | 0x80)
            else:
                out.append(x)
                break
        return bytes(out)

    def _proto_bytes(self, field, data):
        return self._proto_varint((field << 3) | 2) + self._proto_varint(len(data)) + data

    def _proto_varint_field(self, field, value):
        return self._proto_varint(field << 3) + self._proto_varint(value)

    def _build_decode_request(self, token, play_from, ts_ms, nonce_hex):
        sign = hashlib.sha256(
            ("finger=%s&id=%s&nonce=%s&sk=%s&time=%d&v=1" % (self.ID, self.DEV, nonce_hex, self.SK, ts_ms)).encode()
        ).hexdigest().upper()
        req = b""
        req += self._proto_bytes(1, token.encode())
        req += self._proto_bytes(2, play_from.encode())
        req += self._proto_varint_field(3, ts_ms)
        req += self._proto_bytes(4, nonce_hex.encode())
        req += self._proto_bytes(5, sign.encode())
        req += self._proto_bytes(6, self.DEV.encode())
        req += self._proto_varint_field(7, 1)
        return req

    def _parse_decode_response(self, data):
        result = {}
        i = 0
        n = len(data)
        while i < n:
            key = 0
            shift = 0
            while True:
                b = data[i]; i += 1
                key |= (b & 0x7f) << shift
                shift += 7
                if not (b & 0x80):
                    break
            field = key >> 3
            wire = key & 7
            if wire == 0:
                val = 0
                shift = 0
                while True:
                    b = data[i]; i += 1
                    val |= (b & 0x7f) << shift
                    shift += 7
                    if not (b & 0x80):
                        break
                result[field] = val
            elif wire == 2:
                ln = 0
                shift = 0
                while True:
                    b = data[i]; i += 1
                    ln |= (b & 0x7f) << shift
                    shift += 7
                    if not (b & 0x80):
                        break
                result[field] = data[i:i+ln]
                i += ln
            elif wire == 1:
                result[field] = data[i:i+8]; i += 8
            elif wire == 5:
                result[field] = data[i:i+4]; i += 4
            else:
                break
        return result

    def _decode_url(self, token, play_from):
        """调用 decode/url 接口, 返回真实可播放地址; 失败返回空串"""
        try:
            ts_ms = int(time.time() * 1000)
            nonce_hex = os.urandom(16).hex()
            body = self._build_decode_request(token, play_from, ts_ms, nonce_hex)
            req = urllib.request.Request(f"{self.api}/decode/url", data=body, method='POST')
            req.add_header("Content-Type", "application/x-protobuf")
            req.add_header("Accept", "application/x-protobuf")
            req.add_header("User-Agent", self.ua)
            req.add_header("X-Client", self.x_client)
            req.add_header("web-sign", self.web_sign)
            cookie = self._get_cookie()
            if cookie:
                req.add_header("Cookie", cookie)
            resp = urllib.request.urlopen(req, timeout=20, context=self._ssl_ctx)
            fields = self._parse_decode_response(resp.read())
            url = fields.get(3)
            if url and url.startswith(b"http"):
                return url.decode('utf-8', errors='replace')
        except Exception as e:
            print(f'decode_url error: {e}')
        return ""

    def _play_url(self, vod_id, ep, src_from=""):
        """构造网站播放页URL, 附带线路(source)与集数(ep)参数"""
        url = f"{self.host}/play/{vod_id}?ep={ep}"
        if src_from:
            url += f"&source={quote(src_from)}"
        return url

    def _ref_host(self, url):
        """从播放链接中提取 scheme://host 作为 Referer"""
        try:
            pr = urllib.parse.urlparse(url)
            if pr.scheme and pr.netloc:
                return f"{pr.scheme}://{pr.netloc}"
        except Exception:
            pass
        return self.host

    def homeContent(self, filter):
        result = {"class": [], "filters": {}, "list": []}
        try:
            html = self.fetch_html(self.api + "/index/home")
            if html:
                data = json.loads(html)
                if data.get("code") == 200 and data.get("data"):
                    home = data["data"]
                    categories = home.get("categories", [])
                    for cat in categories:
                        type_name = cat.get("type_name", "")
                        result["class"].append({
                            "type_name": type_name,
                            "type_id": type_name,
                        })
                    result["filters"] = self._build_filters()
                    seen = set()
                    for cat in categories:
                        videos = cat.get("videos", [])
                        for v in videos:
                            vid = str(v.get("vod_id", ""))
                            if vid and vid not in seen:
                                seen.add(vid)
                                result["list"].append({
                                    "vod_id": vid,
                                    "vod_name": v.get("vod_name", ""),
                                    "vod_pic": v.get("vod_pic", ""),
                                    "vod_remarks": v.get("vod_remarks", ""),
                                })
                    for rec in home.get("recommend", []):
                        vid = str(rec.get("vod_id", ""))
                        if vid and vid not in seen:
                            seen.add(vid)
                            result["list"].append({
                                "vod_id": vid,
                                "vod_name": rec.get("vod_name", ""),
                                "vod_pic": rec.get("vod_pic", ""),
                                "vod_remarks": rec.get("vod_remarks", ""),
                            })
        except Exception as e:
            print(f'homeContent error: {e}')
        return result

    def homeVideoContent(self):
        pass

    def _build_filters(self):
        years = [{"n": "全部", "v": ""}]
        for y in range(2026, 2005, -1):
            years.append({"n": str(y), "v": str(y)})

        areas = [
            {"n": "全部", "v": ""},
            {"n": "中国大陆", "v": "中国大陆"}, {"n": "中国香港", "v": "中国香港"},
            {"n": "中国台湾", "v": "中国台湾"}, {"n": "美国", "v": "美国"},
            {"n": "日本", "v": "日本"}, {"n": "韩国", "v": "韩国"},
            {"n": "泰国", "v": "泰国"}, {"n": "英国", "v": "英国"},
            {"n": "法国", "v": "法国"}, {"n": "印度", "v": "印度"},
            {"n": "其他", "v": "其他"},
        ]

        sorts = [
            {"n": "时间", "v": "time"},
            {"n": "人气", "v": "hits"},
            {"n": "评分", "v": "score"},
        ]

        movie_class = [
            {"n": "全部", "v": ""},
            {"n": "动作", "v": "动作"}, {"n": "喜剧", "v": "喜剧"},
            {"n": "爱情", "v": "爱情"}, {"n": "科幻", "v": "科幻"},
            {"n": "恐怖", "v": "恐怖"}, {"n": "剧情", "v": "剧情"},
            {"n": "战争", "v": "战争"}, {"n": "犯罪", "v": "犯罪"},
            {"n": "奇幻", "v": "奇幻"}, {"n": "冒险", "v": "冒险"},
            {"n": "悬疑", "v": "悬疑"}, {"n": "动画", "v": "动画"},
            {"n": "古装", "v": "古装"}, {"n": "武侠", "v": "武侠"},
            {"n": "历史", "v": "历史"}, {"n": "家庭", "v": "家庭"},
            {"n": "惊悚", "v": "惊悚"},
        ]

        tv_class = [
            {"n": "全部", "v": ""},
            {"n": "剧情", "v": "剧情"}, {"n": "喜剧", "v": "喜剧"},
            {"n": "爱情", "v": "爱情"}, {"n": "科幻", "v": "科幻"},
            {"n": "悬疑", "v": "悬疑"}, {"n": "恐怖", "v": "恐怖"},
            {"n": "古装", "v": "古装"}, {"n": "动作", "v": "动作"},
            {"n": "家庭", "v": "家庭"}, {"n": "战争", "v": "战争"},
            {"n": "犯罪", "v": "犯罪"}, {"n": "历史", "v": "历史"},
            {"n": "冒险", "v": "冒险"}, {"n": "奇幻", "v": "奇幻"},
            {"n": "国产剧", "v": "国产剧"},
        ]

        anime_class = [
            {"n": "全部", "v": ""},
            {"n": "国产动漫", "v": "国产动漫"}, {"n": "日本动漫", "v": "日本动漫"},
            {"n": "欧美动漫", "v": "欧美动漫"}, {"n": "海外动漫", "v": "海外动漫"},
            {"n": "其他", "v": "其他"},
        ]

        variety_filters = [
            {"key": "area", "name": "地区", "value": areas},
            {"key": "sort", "name": "排序", "value": sorts},
            {"key": "year", "name": "年份", "value": years},
        ]

        return {
            "电影": [
                {"key": "class", "name": "类型", "value": movie_class},
                {"key": "area", "name": "地区", "value": areas},
                {"key": "sort", "name": "排序", "value": sorts},
                {"key": "year", "name": "年份", "value": years},
            ],
            "剧集": [
                {"key": "class", "name": "类型", "value": tv_class},
                {"key": "area", "name": "地区", "value": areas},
                {"key": "sort", "name": "排序", "value": sorts},
                {"key": "year", "name": "年份", "value": years},
            ],
            "综艺": variety_filters,
            "动漫": [
                {"key": "class", "name": "类型", "value": anime_class},
                {"key": "sort", "name": "排序", "value": sorts},
                {"key": "year", "name": "年份", "value": years},
            ],
        }

    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if pg else 1
        result = {"list": [], "page": page, "pagecount": 1, "limit": 24, "total": 0}
        try:
            url = f"{self.api}/filter/vod?type_name={quote(tid)}&page={page}&sort=hits"
            if extend:
                area = extend.get("area", "")
                if area and area != "全部":
                    url += f"&area={quote(area)}"
                cls = extend.get("class", "")
                if cls and cls != "全部":
                    url += f"&class={quote(cls)}"
                year = extend.get("year", "")
                if year and year != "全部":
                    url += f"&year={year}"
                sort = extend.get("sort", "")
                if sort:
                    url += f"&sort={sort}"

            html = self.fetch_html(url)
            if html:
                data = json.loads(html)
                if data.get("code") == 200 and isinstance(data.get("data"), list):
                    items = data["data"]
                    for v in items:
                        result["list"].append({
                            "vod_id": str(v.get("vod_id", "")),
                            "vod_name": v.get("vod_name", ""),
                            "vod_pic": v.get("vod_pic", ""),
                            "vod_remarks": v.get("vod_remarks", ""),
                        })
                    # 使用API返回的分页数据
                    api_total = data.get("total", 0)
                    api_pagecount = data.get("pageCount", 0)
                    if api_total and api_total > 0:
                        result["total"] = api_total
                    else:
                        result["total"] = len(items)
                    if api_pagecount and api_pagecount > 0:
                        result["pagecount"] = api_pagecount
                    elif items and len(items) >= 20:
                        result["pagecount"] = page + 1
                    else:
                        result["pagecount"] = page
        except Exception as e:
            print(f'categoryContent error: {e}')
        return result

    def detailContent(self, ids):
        result = {"list": []}
        try:
            vod_id = ids[0]
            # 使用 detail_v2 获取详情和播放信息
            html = self.fetch_html(f"{self.api}/vod/detail_v2?vod_id={vod_id}")
            if html:
                data = json.loads(html)
                if data.get("code") == 200 and data.get("data"):
                    d = data["data"]
                    detail = d.get("detail", {})
                    playback = d.get("playback", {})
                    sources = playback.get("sources", [])

                    play_from = []
                    play_url = []
                    vod_id_str = str(vod_id)

                    for i, source in enumerate(sources):
                        display_name = source.get("display_name", source.get("from", ""))
                        episodes = source.get("episodes", [])
                        # 懒加载线路: detail_v2 仅返回默认线路的完整集数,
                        # 其他线路 episodes 为空但 episode_count 有值, 用占位集数保留多线路
                        if not episodes:
                            ep_count = int(source.get("episode_count", 0) or 0)
                            if ep_count > 0:
                                episodes = [{"title": "第%02d集" % n} for n in range(1, ep_count + 1)]
                            else:
                                continue
                        urls = []
                        for idx, ep in enumerate(episodes, start=1):
                            title = ep.get("title", str(idx))
                            url = ep.get("url", "")
                            pid_value = f"{vod_id_str}_{idx}_{i}"
                            urls.append(f"{title}${pid_value}")
                        if urls:
                            play_from.append(display_name)
                            play_url.append("#".join(urls))

                    content = detail.get("vod_content", "")
                    vod_content = re.sub(r'<[^>]+>', '', content).strip()

                    result["list"] = [{
                        "vod_id": str(detail.get("vod_id", vod_id)),
                        "vod_name": detail.get("vod_name", ""),
                        "vod_pic": detail.get("vod_pic", ""),
                        "vod_director": detail.get("vod_director", ""),
                        "vod_actor": detail.get("vod_actor", ""),
                        "vod_year": str(detail.get("vod_year", "")),
                        "vod_area": detail.get("vod_area", ""),
                        "vod_content": vod_content,
                        "vod_remarks": detail.get("vod_remarks", ""),
                        "vod_play_from": "$$$".join(play_from),
                        "vod_play_url": "$$$".join(play_url),
                    }]
        except Exception as e:
            print(f'detailContent error: {e}')
        return result

    def searchContent(self, key, quick, pg="1"):
        result = {"list": []}
        try:
            wd = quote(key)
            url = f"{self.api}/search/index?wd={wd}&pg={pg}"
            html = self.fetch_html(url)
            if html:
                data = json.loads(html)
                if data.get("code") == 200 and isinstance(data.get("data"), list):
                    for v in data["data"]:
                        result["list"].append({
                            "vod_id": str(v.get("vod_id", "")),
                            "vod_name": v.get("vod_name", ""),
                            "vod_pic": v.get("vod_pic", ""),
                            "vod_remarks": v.get("vod_remarks", ""),
                        })
        except Exception as e:
            print(f'searchContent error: {e}')
        return result

    def playerContent(self, flag, pid, vipFlags):
        result = {}
        try:
            # pid格式: vod_id_ep_index_source_index
            parts = pid.split("_")
            vod_id = parts[0]
            ep_idx = int(parts[1]) if len(parts) > 1 else 1
            src_idx = int(parts[2]) if len(parts) > 2 else 0
            src_from = ""

            # 调用 playback_v2 获取播放信息
            html = self.fetch_html(f"{self.api}/vod/playback_v2?vod_id={vod_id}")
            if html:
                data = json.loads(html)
                if data.get("code") == 200 and data.get("data"):
                    sources = data["data"].get("sources", [])
                    if src_idx < len(sources):
                        source = sources[src_idx]
                        src_from = source.get("from", "")
                        episodes = source.get("episodes", [])
                        if ep_idx <= len(episodes):
                            ep = episodes[ep_idx - 1]
                            play_url = ep.get("url", "")

                            if play_url:
                                if play_url.startswith("http"):
                                    # 网页URL (如优酷) 或直链
                                    if re.search(r'\.(m3u8|mp4|flv|ts|mkv|webm|m4s)(\?|$)', play_url, re.I):
                                        result["parse"] = 0
                                        result["url"] = play_url
                                    else:
                                        result["parse"] = 1
                                        result["url"] = play_url
                                else:
                                    # 加密token: 本地签名后调用 decode/url 取真实地址
                                    real = self._decode_url(play_url, src_from)
                                    if real:
                                        result["parse"] = 0
                                        result["url"] = real
                                    else:
                                        result["parse"] = 1
                                        result["url"] = self._play_url(vod_id, ep_idx, src_from)

                                result["header"] = {
                                    "User-Agent": self.ua,
                                    "Referer": self._ref_host(result.get("url", "")) if result.get("parse") == 0 else self.host,
                                }
                                cookie = self._get_cookie()
                                if cookie:
                                    result["header"]["Cookie"] = cookie
                                return result

            # 回退: 用网站播放页 (带线路参数)
            result["parse"] = 1
            result["url"] = self._play_url(vod_id, ep_idx, src_from)
            result["header"] = {"User-Agent": self.ua, "Referer": self._ref_host(result["url"])}
        except Exception as e:
            print(f'playerContent error: {e}')
            result["parse"] = 0
            result["url"] = ""
        return result

    def localProxy(self, params):
        return self.Mlocal(params)