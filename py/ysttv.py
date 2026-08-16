#!/usr/bin/python
# -*- coding: utf-8 -*-
import re, json, requests
from urllib.parse import quote
try:
    from lxml import etree
except Exception:
    etree = None
from base.spider import Spider

BADIMG = ("poster_loading", "logo", "thumb.png", "playing.gif", "favicon", "doubanio", "discord")
PAGEFMT = ["%s/p/%s", "%s?page=%s", "%s/page/%s", "%s/%s"]
SEARCHFMT = ["/search/%s", "/vod/search/%s", "/search/index/wd/%s", "/index.php/vod/search/wd/%s", "/search?wd=%s"]


class Spider(Spider):
    def getName(self): return "影视天堂"

    def init(self, extend=""):
        self.host = "https://ysttv.com"
        try: ext = json.loads(extend) if str(extend).strip().startswith("{") else {}
        except Exception: ext = {}
        if ext.get("host"): self.host = ext["host"].rstrip("/")
        self.pageFmt = ext.get("pageFmt", "")
        self.searchFmt = ext.get("searchFmt", "")
        self.headers = {"User-Agent": ext.get("ua", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"), "Referer": self.host + "/", "Accept-Language": "zh-CN,zh;q=0.9"}
        self.categories = [{"type_id": "movie", "type_name": "电影"}, {"type_id": "teleplay", "type_name": "剧集"}, {"type_id": "variety", "type_name": "综艺"}, {"type_id": "anime", "type_name": "动漫"}, {"type_id": "playlet", "type_name": "短剧"}]
        self.genres = [["全部", ""], ["动作", "action"], ["喜剧", "comedy"], ["科幻", "sci-fi"], ["悬疑", "mystery"], ["爱情", "romance"], ["犯罪", "crime"], ["恐怖", "horror"], ["剧情", "drama"], ["奇幻", "fantasy"], ["惊悚", "thriller"], ["冒险", "adventure"], ["动画", "animation"], ["历史", "history"], ["同性", "lgbt"], ["纪录片", "documentary"], ["古装", "costume"], ["武侠", "wuxia"], ["音乐", "music"], ["歌舞", "musical"], ["运动", "sports"], ["灾难", "disaster"], ["传记", "biography"], ["儿童", "kids"]]
        self.years = [["全部", ""]] + [[str(y), "year%d" % y] for y in range(2025, 2014, -1)]
        self.areas = [["全部", ""], ["大陆", "area-china"], ["台湾", "area-taiwan"], ["香港", "area-hong-kong"], ["美国", "area-usa"], ["韩国", "area-korea"], ["日本", "area-japan"], ["英国", "area-uk"], ["法国", "area-france"], ["泰国", "area-thailand"], ["印度", "area-india"], ["加拿大", "area-canada"]]
        self.sorts = [["最新", ""], ["人气", "hot"], ["评分", "rating"]]

    def _fix(self, u):
        if not u: return ""
        if u.startswith("//"): return "https:" + u
        if u.startswith("/"): return self.host + u
        return u

    def _get(self, path):
        url = path if path.startswith("http") else self.host + path
        try:
            r = requests.get(url, headers=self.headers, timeout=15); r.encoding = "utf-8"
            if r.status_code >= 400: print("[WARN] status=%s url=%s" % (r.status_code, url)); return None
            return r.text
        except requests.exceptions.Timeout: print("[ERROR] 请求超时: %s" % url)
        except requests.exceptions.ConnectionError: print("[ERROR] 连接错误: %s" % url)
        except Exception as e: print("[ERROR] 请求失败: %s, %s" % (url, str(e)))
        return None

    def _img(self, node):
        for at in ("data-original", "data-src", "data-echo", "src"):
            for v in node.xpath('.//img/@%s' % at):
                if v and not any(b in v for b in BADIMG): return v
        return ""

    def _parse_list(self, html):
        if not html: return []
        if etree is None:
            print("[WARN] lxml 不可用，降级为正则解析")
            out, seen = [], set()
            for vid, title in re.findall(r'/detail/(\d+)/?"[^>]*?title="([^"]*)"', html):
                if vid in seen: continue
                seen.add(vid); out.append({"vod_id": vid, "vod_name": title, "vod_pic": ""})
            return out
        tree = etree.HTML(html); results, seen = [], set()
        items = tree.xpath('//a[contains(@href,"/detail/") and .//img]') + tree.xpath('//a[contains(@href,"/detail/")]')
        for it in items:
            try:
                m = re.search(r'/detail/(\d+)', it.get("href", ""))
                if not m or m.group(1) in seen: continue
                name = (it.get("title") or "".join(it.xpath('.//img/@alt')[:1])).strip()
                if not name: continue
                seen.add(m.group(1))
                note = [x.strip() for x in it.xpath('.//span//text() | .//em//text() | .//i//text()') if x.strip() and x.strip() != name]
                results.append({"vod_id": m.group(1), "vod_name": name, "vod_pic": self._fix(self._img(it)), "vod_remarks": " ".join(note)[:30]})
            except Exception: continue
        return results

    def _first(self, lst): return lst[0]["vod_id"] if lst else ""

    def _paged(self, base, pg):
        if pg == "1": return self._get(base)
        if self.pageFmt: return self._get(self.pageFmt % (base, pg))
        first = self._first(self._parse_list(self._get(base)))
        for f in PAGEFMT:
            html = self._get(f % (base, pg))
            got = self._parse_list(html)
            if got and self._first(got) != first:
                self.pageFmt = f
                print("[INFO] 分页格式确定: %s" % (f % ("{base}", "{pg}")))
                return html
        print("[WARN] 未能确定分页格式，仅返回首页")
        return None

    def homeContent(self, filter):
        fl = {}
        for c in self.categories:
            fl[c["type_id"]] = [{"key": "genre", "name": "类型", "value": [{"n": g[0], "v": g[1]} for g in self.genres]},
                                {"key": "year", "name": "年份", "value": [{"n": y[0], "v": y[1]} for y in self.years]},
                                {"key": "area", "name": "地区", "value": [{"n": a[0], "v": a[1]} for a in self.areas]},
                                {"key": "sort", "name": "排序", "value": [{"n": s[0], "v": s[1]} for s in self.sorts]}]
        return {"class": self.categories, "list": self._parse_list(self._get("/")), "filters": fl}

    def homeVideoContent(self): return {"list": self._parse_list(self._get("/"))}

    def categoryContent(self, tid, pg, filter, extend):
        pg = str(pg or "1"); ex = extend or {}
        facet = ex.get("genre") or ex.get("year") or ex.get("area") or ex.get("sort") or ""
        base = "/vod/%s" % tid + ("/%s" % facet if facet else "")
        lst = self._parse_list(self._paged(base, pg))
        return {"page": int(pg), "pagecount": int(pg) + 1 if lst else int(pg), "limit": 32, "total": 999999, "list": lst}

    def searchContent(self, key, quick, pg="1"):
        pg = str(pg or "1")
        for f in ([self.searchFmt] if self.searchFmt else SEARCHFMT):
            lst = self._parse_list(self._get(f % quote(key)))
            if lst:
                self.searchFmt = f
                print("[INFO] 搜索格式确定: %s" % f)
                return {"list": lst, "page": int(pg)}
        print("[WARN] 未能确定搜索接口，需抓包补 searchFmt")
        return {"list": [], "page": int(pg)}

    def _field(self, text, key):
        m = re.search(r'%s\s*[:：]\s*([^\n]{1,200})' % key, text)
        return m.group(1).strip(" \u3000|/") if m else ""

    def detailContent(self, ids):
        vid = re.sub(r'\D', '', str(ids[0]))
        html = self._get("/detail/%s/" % vid)
        if not html or etree is None: return {"list": []}
        tree = etree.HTML(html)
        text = "\n".join(x.strip() for x in tree.xpath('//text()') if x.strip())
        pic = ""
        for v in tree.xpath('//img/@src | //img/@data-original | //img/@data-src'):
            if v and not any(b in v for b in BADIMG) and re.search(r'/cover/|/upload/|jinyingimage', v): pic = v; break
        vod = {"vod_id": vid,
               "vod_name": ("".join(tree.xpath('//h1//text()')).strip() or self._field(text, "og:title")).strip("《》"),
               "vod_pic": self._fix(pic),
               "vod_year": "".join(tree.xpath('//a[contains(@href,"/year")]/text()')[:1]).strip(),
               "vod_area": "".join(tree.xpath('//a[contains(@href,"/area-")]/text()')[:1]).strip(),
               "type_name": " ".join(x.strip() for x in tree.xpath('//a[contains(@href,"/vod/") and not(contains(@href,"/year")) and not(contains(@href,"/area-"))]/text()')[:3] if x.strip()),
               "vod_director": self._field(text, "导演"), "vod_actor": self._field(text, "主演"),
               "vod_remarks": ("共%s集" % self._field(text, "集数")) if self._field(text, "集数").isdigit() and self._field(text, "集数") != "1" else (self._field(text, "评分") or self._field(text, "集数")),
               "vod_content": self._field(text, "剧情") or self._field(text, "简介")}
        ph = self._get("/player/%s/" % vid)
        eps = []
        if ph:
            pt = etree.HTML(ph)
            for a in pt.xpath('//a[contains(@href,"/player/%s/")]' % vid):
                lk = a.get("href", "")
                nm = ("".join(a.xpath('.//text()')).strip() or a.get("title", "")).strip()
                if not lk or not nm or lk.rstrip("/").endswith("/%s" % vid): continue
                item = nm.replace("$", "").replace("#", "") + "$" + self._fix(lk)
                if item not in eps: eps.append(item)
        vod["vod_play_from"] = "影视天堂"
        vod["vod_play_url"] = "#".join(eps or ["正片$%s/player/%s/" % (self.host, vid)])
        return {"list": [vod]}

    def playerContent(self, flag, id, vipFlags):
        pid = id if id.startswith("http") else self._fix(id)
        html = self._get(pid) or ""
        url = ""
        for p in [r'var\s+now\s*=\s*["\']([^"\']+)["\']', r'var\s+player_\w+\s*=\s*(\{.*?\})\s*[;<]', r'"(?:url|video_url|playUrl)"\s*:\s*"([^"]+\.(?:m3u8|mp4)[^"]*)"', r'url:\s*["\']([^"\']+\.(?:m3u8|mp4)[^"\']*)["\']', r'(https?://[^\s"\'\\<>]+\.(?:m3u8|mp4)[^\s"\'\\<>]*)']:
            m = re.search(p, html.replace("\\/", "/"), re.S)
            if not m: continue
            val = m.group(1)
            if val.startswith("{"):
                try: val = json.loads(val).get("url", "")
                except Exception:
                    m2 = re.search(r'"(https?://[^"]+\.(?:m3u8|mp4)[^"]*)"', val); val = m2.group(1) if m2 else ""
            if val: url = self._fix(val); break
        if not url: return {"parse": 1, "url": pid, "header": self.headers}
        return {"parse": 0, "url": url, "header": {"User-Agent": self.headers["User-Agent"], "Referer": self.host + "/"}}
