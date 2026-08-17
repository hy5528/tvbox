#!/usr/bin/python
# -*- coding: utf-8 -*-
import re, json, requests, urllib.parse, base64, hashlib
from base.spider import Spider

class Spider(Spider):
    def getName(self): return "耐看点播"
    def init(self, extend=""):
        self.name = "耐看点播"; self.host = "https://nkdvd.cc"; self.limit = 40
        self.headers = {"User-Agent":"Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 Chrome/120.0 Mobile Safari/537.36","Referer":self.host+"/","Accept":"text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8","Accept-Language":"zh-CN,zh;q=0.9"}
        self.classes = [{"type_id":"20","type_name":"电影"},{"type_id":"21","type_name":"剧集"},{"type_id":"22","type_name":"动漫"},{"type_id":"23","type_name":"综艺"},{"type_id":"24","type_name":"纪录片"},{"type_id":"25","type_name":"爽剧"}]
        self.filters = {c["type_id"]:[{"key":"area","name":"地区","value":[{"n":"全部","v":""},{"n":"大陆","v":"大陆"},{"n":"香港","v":"香港"},{"n":"台湾","v":"台湾"},{"n":"美国","v":"美国"},{"n":"韩国","v":"韩国"},{"n":"日本","v":"日本"},{"n":"泰国","v":"泰国"},{"n":"英国","v":"英国"}]},{"key":"year","name":"年份","value":[{"n":"全部","v":""},{"n":"2026","v":"2026"},{"n":"2025","v":"2025"},{"n":"2024","v":"2024"},{"n":"2023","v":"2023"},{"n":"2022","v":"2022"},{"n":"2021","v":"2021"},{"n":"2020","v":"2020"},{"n":"2019","v":"2019"},{"n":"2018","v":"2018"},{"n":"2017","v":"2017"}]},{"key":"order","name":"排序","value":[{"n":"最新","v":"time"},{"n":"最热","v":"hits"},{"n":"评分","v":"score"}]}] for c in self.classes}
    def _get(self, url, referer=None):
        try:
            h = dict(self.headers); h["Referer"] = referer or self.host + "/"
            r = requests.get(url, headers=h, timeout=15, verify=False); r.encoding = r.apparent_encoding or "utf-8"; return r.text
        except Exception as e: print(f"[{self.name}] 错误: 请求失败 - {e}"); return ""
    def _fix(self, u): return "https:" + u if u and u.startswith("//") else self.host + u if u and u.startswith("/") else u or ""
    def _clean(self, t): return re.sub(r"<[^>]+>|\s+", " ", t or "").strip()
    def _attr(self, html, key):
        m = re.search(key + r'=["\']([^"\']+)', html or "", re.I); return m.group(1) if m else ""
    def _parse_list(self, html):
        videos, seen = [], set()
        if not html: return videos
        blocks = re.findall(r'<a[^>]+href=["\']/video/\d+\.html["\'][\s\S]*?</a>', html, re.I) or re.findall(r'<div[^>]+class=["\'][^"\']*module-card-item[\s\S]*?</div>\s*</div>\s*</div>', html, re.I)
        if not blocks: blocks = re.findall(r'<a[^>]+href=["\'][^"\']*/video/\d+\.html["\'][\s\S]*?<img[\s\S]*?</a>', html, re.I)
        print(f"[{self.name}] 分类列表匹配到 {len(blocks)} 个视频")
        for b in blocks:
            try:
                m = re.search(r'/video/(\d+)\.html', b)
                if not m or m.group(1) in seen: continue
                seen.add(m.group(1)); img = re.search(r'<img[\s\S]*?>', b, re.I); img = img.group(0) if img else ""
                name = self._attr(b, "title") or self._attr(img, "alt") or self._clean("".join(re.findall(r'<div[^>]+class=["\'][^"\']*title[^"\']*["\'][^>]*>([\s\S]*?)</div>', b, re.I)))
                pic = self._fix(self._attr(img, "data-original") or self._attr(img, "data-src") or self._attr(img, "src"))
                remark = self._clean("".join(re.findall(r'<div[^>]+class=["\'][^"\']*note[^"\']*["\'][^>]*>([\s\S]*?)</div>', b, re.I)))
                if name: videos.append({"vod_id":m.group(1),"vod_name":name,"vod_pic":pic,"vod_remarks":remark})
            except Exception: continue
        return videos
    def homeContent(self, filter):
        try: return {"class":self.classes,"list":self._parse_list(self._get(self.host+"/")),"filters":self.filters}
        except Exception as e: print(f"[{self.name}] 错误: 首页获取失败 - {e}"); return {"class":self.classes,"list":[],"filters":self.filters}
    def categoryContent(self, tid, pg, filter, extend):
        try:
            pg = int(pg or 1); area = (extend or {}).get("area", ""); year = (extend or {}).get("year", ""); order = (extend or {}).get("order", "")
            if area or year or order:
                parts = [f"id/{tid}"]
                if area: parts.append("area/" + urllib.parse.quote(area))
                if year: parts.append("year/" + urllib.parse.quote(year))
                if order: parts.append("by/" + urllib.parse.quote(order))
                if pg > 1: parts.append("page/" + str(pg))
                url = self.host + "/vodshow/" + "/".join(parts) + ".html"
            else: url = f"{self.host}/type/{tid}.html" if pg == 1 else f"{self.host}/vodshow/id/{tid}/page/{pg}.html"
            print(f"[{self.name}] 分类爬取: {url}")
            return {"list":self._parse_list(self._get(url)),"page":pg,"pagecount":999,"limit":self.limit,"total":999}
        except Exception as e: print(f"[{self.name}] 错误: 分类爬取失败 - {e}"); return {"list":[],"page":1,"pagecount":1,"limit":self.limit,"total":0}
    def detailContent(self, ids):
        res = {"list":[]}
        for vid in ids:
            try:
                html = self._get(f"{self.host}/video/{vid}.html")
                name = self._clean((re.search(r'<h1[^>]*>([\s\S]*?)</h1>', html, re.I) or re.search(r'<title>([\s\S]*?)(?:详情介绍|在线观看|-)', html, re.I) or ["",""])[1])
                poster = re.search(r'<div[^>]+class=["\'][^"\']*module-info-poster[\s\S]*?<img[\s\S]*?>', html, re.I); poster = poster.group(0) if poster else ""
                pic = self._fix(self._attr(poster, "data-original") or self._attr(poster, "data-src") or self._attr(poster, "src"))
                content = self._clean((re.search(r'<div[^>]+class=["\'][^"\']*module-info-introduction-content[\s\S]*?>([\s\S]*?)</div>', html, re.I) or re.search(r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)', html, re.I) or ["",""])[1])
                sources = [self._clean(x) for x in re.findall(r'<[^>]+class=["\'][^"\']*module-tab-item[^"\']*["\'][^>]*>([\s\S]*?)</[^>]+>', html, re.I)]
                eps = re.findall(r'<a[^>]+href=["\']([^"\']*/player/[^"\']+)["\'][^>]*>([\s\S]*?)</a>', html, re.I)
                groups, play_from, play_url = {}, [], []
                for u, t in eps:
                    m = re.search(r'/player/\d+-(\d+)-\d+\.html', u); sid = m.group(1) if m else "1"
                    groups.setdefault(sid, []).append(f"{self._clean(t)}${self._fix(u)}")
                for sid in sorted(groups.keys(), key=lambda x:int(x) if x.isdigit() else 0):
                    idx = int(sid) - 1 if sid.isdigit() else len(play_from)
                    play_from.append(sources[idx] if idx < len(sources) and sources[idx] else f"线路{sid}"); play_url.append("#".join(groups[sid]))
                print(f"[{self.name}] 详情页提取到 {len(play_from)} 个播放源")
                res["list"].append({"vod_id":vid,"vod_name":name,"vod_pic":pic,"vod_content":content,"vod_play_from":"$$$".join(play_from),"vod_play_url":"$$$".join(play_url)})
            except Exception as e: print(f"[{self.name}] 错误: 详情解析失败 - {e}"); continue
        return res
    def searchContent(self, key, quick, pg="1"):
        try:
            pg = int(pg or 1); q = urllib.parse.quote(key); url = f"{self.host}/vodsearch/{q}-------------.html" if pg == 1 else f"{self.host}/vodsearch/{q}----------{pg}---.html"; print(f"[{self.name}] 搜索爬取: {url}")
            return {"list":self._parse_list(self._get(url)),"page":pg,"pagecount":99}
        except Exception as e: print(f"[{self.name}] 错误: 搜索失败 - {e}"); return {"list":[],"page":1,"pagecount":1}

    def _decode_api_url(self, s):
        try:
            key = hashlib.md5(b"test").hexdigest(); raw = base64.b64decode(s); code = "".join(chr(b ^ ord(key[i % len(key)])) for i, b in enumerate(raw)); parts = base64.b64decode(code).decode("utf-8").split("/")
            a = json.loads(base64.b64decode(parts[0]).decode("utf-8")); b = json.loads(base64.b64decode(parts[1]).decode("utf-8")); mid = ""
            for i, x in enumerate(parts):
                if i not in (0, 1): mid += x + ("" if i + 1 == len(parts) else "/")
            dec = base64.b64decode(mid + "===").decode("utf-8"); return "".join(a[b.index(ch)] if ch in b else ch for ch in dec)
        except Exception as e: print(f"[{self.name}] 错误: 直链解码失败 - {e}"); return ""
    def playerContent(self, flag, id, vipFlags):
        try:
            url = self._fix(id)
            if "/player/" in url:
                html = self._get(url, self.host + "/"); m = re.search(r'player_aaaa\s*=\s*(\{[\s\S]*?\})\s*</script>', html)
                if m:
                    data = json.loads(m.group(1)); vid = data.get("url", "")
                    if data.get("encrypt") == "1": vid = urllib.parse.unquote(vid)
                    elif data.get("encrypt") == "2": vid = urllib.parse.unquote(base64.b64decode(vid).decode("utf-8"))
                    h = dict(self.headers); h.update({"Referer": self.host + "/player/?vid=" + urllib.parse.quote(vid, safe=""), "Origin": self.host, "X-Requested-With": "XMLHttpRequest"})
                    r = requests.post(self.host + "/player/api.php", headers=h, data={"vid": vid}, timeout=15, verify=False); j = r.json(); enc = ((j.get("data") or {}).get("url") or ""); real = self._decode_api_url(enc) if enc else ""
                    if real: url = real
            print(f"[{self.name}] 播放解析: {flag} -> {url[:80]}...")
            return {"parse":0,"playUrl":"","url":url,"header":{"User-Agent":self.headers["User-Agent"],"Referer":self.host+"/"}}
        except Exception as e: print(f"[{self.name}] 错误: 播放解析失败 - {e}"); return {"parse":1,"playUrl":"","url":self._fix(id),"header":self.headers}
