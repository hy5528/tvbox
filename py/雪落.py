#!/usr/bin/python
# -*- coding: utf-8 -*-
import re, json, time, requests, hashlib
from collections import Counter
from urllib.parse import quote
try:
    from lxml import etree
except Exception:
    etree = None
from base.spider import Spider

# ---- 雪落影视 /lines 取流签名（内联自 xl_aes.py，纯 Python AES-ECB，TVBox 无需额外模块）----
# raw = f"{pid}-{t_ms}"; key = utf8(md5(raw).hexdigest()[:16]); sg = AES-128-ECB(pkcs7(raw), key).hex().upper()
_SBOX = [
    0x63,0x7c,0x77,0x7b,0xf2,0x6b,0x6f,0xc5,0x30,0x01,0x67,0x2b,0xfe,0xd7,0xab,0x76,
    0xca,0x82,0xc9,0x7d,0xfa,0x59,0x47,0xf0,0xad,0xd4,0xa2,0xaf,0x9c,0xa4,0x72,0xc0,
    0xb7,0xfd,0x93,0x26,0x36,0x3f,0xf7,0xcc,0x34,0xa5,0xe5,0xf1,0x71,0xd8,0x31,0x15,
    0x04,0xc7,0x23,0xc3,0x18,0x96,0x05,0x9a,0x07,0x12,0x80,0xe2,0xeb,0x27,0xb2,0x75,
    0x09,0x83,0x2c,0x1a,0x1b,0x6e,0x5a,0xa0,0x52,0x3b,0xd6,0xb3,0x29,0xe3,0x2f,0x84,
    0x53,0xd1,0x00,0xed,0x20,0xfc,0xb1,0x5b,0x6a,0xcb,0xbe,0x39,0x4a,0x4c,0x58,0xcf,
    0xd0,0xef,0xaa,0xfb,0x43,0x4d,0x33,0x85,0x45,0xf9,0x02,0x7f,0x50,0x3c,0x9f,0xa8,
    0x51,0xa3,0x40,0x8f,0x92,0x9d,0x38,0xf5,0xbc,0xb6,0xda,0x21,0x10,0xff,0xf3,0xd2,
    0xcd,0x0c,0x13,0xec,0x5f,0x97,0x44,0x17,0xc4,0xa7,0x7e,0x3d,0x64,0x5d,0x19,0x73,
    0x60,0x81,0x4f,0xdc,0x22,0x2a,0x90,0x88,0x46,0xee,0xb8,0x14,0xde,0x5e,0x0b,0xdb,
    0xe0,0x32,0x3a,0x0a,0x49,0x06,0x24,0x5c,0xc2,0xd3,0xac,0x62,0x91,0x95,0xe4,0x79,
    0xe7,0xc8,0x37,0x6d,0x8d,0xd5,0x4e,0xa9,0x6c,0x56,0xf4,0xea,0x65,0x7a,0xae,0x08,
    0xba,0x78,0x25,0x2e,0x1c,0xa6,0xb4,0xc6,0xe8,0xdd,0x74,0x1f,0x4b,0xbd,0x8b,0x8a,
    0x70,0x3e,0xb5,0x66,0x48,0x03,0xf6,0x0e,0x61,0x35,0x57,0xb9,0x86,0xc1,0x1d,0x9e,
    0xe1,0xf8,0x98,0x11,0x69,0xd9,0x8e,0x94,0x9b,0x1e,0x87,0xe9,0xce,0x55,0x28,0xdf,
    0x8c,0xa1,0x89,0x0d,0xbf,0xe6,0x42,0x68,0x41,0x99,0x2d,0x0f,0xb0,0x54,0xbb,0x16]
_RCON = [0x01,0x02,0x04,0x08,0x10,0x20,0x40,0x80,0x1b,0x36]


def _aes_expand_key(key):
    nk, nr = len(key)//4, len(key)//4 + 6
    w = [[key[4*i], key[4*i+1], key[4*i+2], key[4*i+3]] for i in range(nk)]
    for i in range(nk, 4*(nr+1)):
        t = w[i-1][:]
        if i % nk == 0:
            t = t[1:] + t[:1]
            t = [_SBOX[b] for b in t]
            t[0] ^= _RCON[i//nk - 1]
        elif nk > 6 and i % nk == 4:
            t = [_SBOX[b] for b in t]
        w.append([w[i-nk][j] ^ t[j] for j in range(4)])
    return w


def _aes_encrypt_block(plain, round_keys):
    nr = len(round_keys)//4 - 1

    def ark(s, rnd):
        rk = round_keys[rnd*4: rnd*4+4]
        for r in range(4):
            for c in range(4):
                s[r][c] ^= rk[r][c]

    def sub(s):
        for r in range(4):
            for c in range(4):
                s[r][c] = _SBOX[s[r][c]]

    def shr(s):
        s[0][1], s[1][1], s[2][1], s[3][1] = s[1][1], s[2][1], s[3][1], s[0][1]
        s[0][2], s[1][2], s[2][2], s[3][2] = s[2][2], s[3][2], s[0][2], s[1][2]
        s[0][3], s[1][3], s[2][3], s[3][3] = s[3][3], s[0][3], s[1][3], s[2][3]

    def xtime(a):
        return ((a << 1) ^ 0x1b) & 0xff if a & 0x80 else (a << 1) & 0xff

    def mix(s):
        for r in range(4):
            a0, a1, a2, a3 = s[r][0], s[r][1], s[r][2], s[r][3]
            s[r][0] = xtime(a0) ^ (xtime(a1) ^ a1) ^ a2 ^ a3
            s[r][1] = a0 ^ xtime(a1) ^ (xtime(a2) ^ a2) ^ a3
            s[r][2] = a0 ^ a1 ^ xtime(a2) ^ (xtime(a3) ^ a3)
            s[r][3] = (xtime(a0) ^ a0) ^ a1 ^ a2 ^ xtime(a3)

    s = [list(plain[4*i:4*i+4]) for i in range(4)]
    ark(s, 0)
    for rnd in range(1, nr):
        sub(s); shr(s); mix(s); ark(s, rnd)
    sub(s); shr(s); ark(s, nr)
    return b''.join(bytes(s[c]) for c in range(4))


def _xlys_sign(pid, t_ms):
    raw = ("%s-%s" % (pid, t_ms)).encode()
    key = hashlib.md5(raw).hexdigest()[:16].encode()
    rk = _aes_expand_key(key)
    pad = 16 - len(raw) % 16
    data = raw + bytes([pad]) * pad
    return b''.join(_aes_encrypt_block(data[i:i+16], rk) for i in range(0, len(data), 16)).hex().upper()

# 注意：站点存在 /aiad (AI脱衣/AI换脸类工具) 入口，本源不抓取、不引用、不提供任何访问路径
GENRES = [["动作", "dongzuo"], ["爱情", "aiqing"], ["喜剧", "xiju"], ["科幻", "kehuan"], ["恐怖", "kongbu"],
          ["战争", "zhanzheng"], ["武侠", "wuxia"], ["魔幻", "mohuan"], ["剧情", "juqing"], ["动画", "donghua"],
          ["惊悚", "jingsong"], ["3D", "3D"], ["灾难", "zainan"], ["悬疑", "xuanyi"], ["警匪", "jingfei"],
          ["文艺", "wenyi"], ["青春", "qingchun"], ["冒险", "maoxian"], ["犯罪", "fanzui"], ["纪录", "jilu"],
          ["古装", "guzhuang"], ["奇幻", "qihuan"], ["国语", "guoyu"], ["综艺", "zongyi"], ["历史", "lishi"],
          ["运动", "yundong"], ["原创压制", "yuanchuang"], ["美剧", "meiju"], ["韩剧", "hanju"],
          ["国产电视剧", "guoju"], ["日剧", "riju"], ["英剧", "yingju"], ["德剧", "deju"], ["俄剧", "eju"],
          ["巴剧", "baju"], ["加剧", "jiaju"], ["西剧", "spanish"], ["意大利剧", "yidaliju"], ["泰剧", "taiju"],
          ["港台剧", "gangtaiju"], ["法剧", "faju"], ["澳剧", "aoju"], ["短剧", "duanju"]]
ITEM_RE = re.compile(r'^/([A-Za-z0-9]+)/(\d+)\.htm$')


class Spider(Spider):
    def getName(self): return "雪落影视"

    def init(self, extend=""):
        self.host = "https://v.xl.in.ua"
        try: ext = json.loads(extend) if str(extend).strip().startswith("{") else {}
        except Exception: ext = {}
        if ext.get("host"): self.host = ext["host"].rstrip("/")
        self.headers = {"User-Agent": ext.get("ua", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"), "Referer": self.host + "/", "Accept-Language": "zh-CN,zh;q=0.9"}
        if ext.get("cookie"): self.headers["Cookie"] = ext["cookie"]
        # 会话保持：/lines 接口要求先访问站点种下 JSESSIONID，否则返回 403 非法请求
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        self.categories = [{"type_id": "all0", "type_name": "电影"}, {"type_id": "all1", "type_name": "剧集"}] + \
                           [{"type_id": g[1], "type_name": g[0]} for g in GENRES]

    def _fix(self, u):
        if not u: return ""
        if u.startswith("//"): return "https:" + u
        if u.startswith("/"): return self.host + u
        return u

    def _get(self, path):
        url = path if path.startswith("http") else self.host + path
        try:
            r = self.session.get(url, timeout=15)
            raw = r.content
            # 统一处理 BOM：UTF-8 (EF BB BF) / UTF-16 (FF FE / FE FF)，避免 lxml 误判 UCS4 little endian
            for bom, enc in ((b'\xef\xbb\xbf', "utf-8-sig"), (b'\xff\xfe', "utf-16"), (b'\xfe\xff', "utf-16")):
                if raw.startswith(bom):
                    body = raw.decode(enc, errors="ignore")
                    break
            else:
                body = r.text
            body = body.lstrip("\ufeff")
            return body
        except requests.exceptions.Timeout: print("[ERROR] 请求超时: %s" % url)
        except requests.exceptions.ConnectionError: print("[ERROR] 连接错误: %s" % url)
        except Exception as e: print("[ERROR] 请求失败: %s, %s" % (url, str(e)))
        return None

    def _tree(self, html, tag="页面"):
        if not html: return None
        if etree is None: print("[WARN] lxml 不可用"); return None
        if isinstance(html, bytes):
            try: html = html.decode("utf-8-sig", errors="ignore")
            except Exception: html = str(html)
        else:
            html = html.lstrip("\ufeff")
        try:
            # 编码为 UTF-8 bytes 后交给 lxml，避免部分 lxml 版本对 str 的编码探测
            # 误判（如 XMLSyntaxError: encoding not supported USC4 little endian）。
            # recover=True 容忍不完整/非法 HTML。
            parser = etree.HTMLParser(encoding="utf-8", recover=True)
            tree = etree.fromstring(html.encode("utf-8", errors="replace"), parser)
            if tree is None:
                tree = etree.HTML(html.encode("utf-8"), parser=parser)
        except Exception as e:
            print("[WARN] %s etree解析异常: %s: %s: %s，长度=%d 片段=%r" % (tag, type(e).__name__, e, html[:80], len(html), html[:80]))
            return None
        if tree is None: print("[WARN] %s etree解析为空，长度=%d 片段=%r" % (tag, len(html), html[:80]))
        return tree

    def _regex_list(self, html):
        out, seen = [], set()
        # 首页 banner 容器：图/标题/链接分离（banner-btns 内是纯按钮，图在容器顶部）
        for part in re.split(r'<div class="banner-slide', html)[1:]:
            href_m = re.search(r'href="(/[A-Za-z0-9]+/\d+\.htm)"', part)
            if not href_m: continue
            href = href_m.group(1)
            if href in seen: continue
            mm = ITEM_RE.match(href)
            if not mm: continue
            name = ""
            nm = re.search(r'<h1[^>]*class="[^"]*banner-title[^"]*"[^>]*>(.*?)</h1>', part, re.S)
            if nm: name = re.sub(r'<[^>]+>', '', nm.group(1)).strip()
            pic = ""
            im = re.search(r'<img[^>]*src="([^"]+)"[^>]*class="[^"]*banner-img[^"]*"', part) or \
                 re.search(r'<img[^>]*class="[^"]*banner-img[^"]*"[^>]*src="([^"]+)"', part)
            if im: pic = im.group(1)
            seen.add(href)
            out.append({"vod_id": "%s/%s" % (mm.group(1), mm.group(2)), "vod_name": name,
                         "vod_pic": self._fix(pic), "vod_remarks": ""})
        for m in re.finditer(r'<a\b([^>]*?href="(/[A-Za-z0-9]+/\d+\.htm)"[^>]*)>(.*?)</a>', html, re.S):
            attrs, href, inner = m.group(1), m.group(2), m.group(3)
            mm = ITEM_RE.match(href)
            if not mm or href in seen: continue
            name = re.search(r'title="([^"]*)"', attrs)
            name = name.group(1).strip() if name else ""
            if not name:
                alt = re.search(r'alt="([^"]*)"', inner)
                name = alt.group(1).strip() if alt else ""
            if not name: continue
            pic = ""
            for at in ("data-src", "data-original", "src"):
                v = re.search(at + r'="([^"]+)"', inner)
                if v and v.group(1).strip() and not v.group(1).startswith("data:"):
                    pic = v.group(1); break
            note = ""
            nm = re.search(r'class="episode-badge"[^>]*>([^<]*)', inner)
            if nm: note = nm.group(1).strip()
            seen.add(href)
            out.append({"vod_id": "%s/%s" % (mm.group(1), mm.group(2)), "vod_name": name,
                         "vod_pic": self._fix(pic), "vod_remarks": note})
        return self._clean_title(out)

    def _clean_title(self, items):
        # 站点列表项标题形如 "2024日漫《愿来世为他人》12集全.HD1080P.日语繁中【ANi]"
        # 提取书名号内剧名，书名号后的集数（如"12集全"/"更至22集"）作为 vod_remarks
        for it in items:
            name = it.get("vod_name", "")
            m = re.search(r'《(.+?)》', name)
            if not m: continue
            it["vod_name"] = m.group(1).strip()
            if not it.get("vod_remarks"):
                tail = name[m.end():]
                rm = re.search(r'(?:更至)?\s*\d+(?:/\d+)?\s*集(?:全)?', tail)
                if rm: it["vod_remarks"] = rm.group(0)
        return items

    def _parse_list(self, html):
        if not html: return []
        tree = self._tree(html, "列表") if etree else None
        if tree is None: return self._regex_list(html)
        groups = {}
        for a in tree.xpath('//a[@href]'):
            href = a.get("href", "")
            m = ITEM_RE.match(href.split("?")[0].split("#")[0])
            if not m: continue
            groups.setdefault((m.group(1), m.group(2)), []).append(a)
        # 首页 banner 容器：<a> 只是按钮，图在 img.banner-img、标题在 h1.banner-title
        bmap = {}
        for b in tree.xpath('//div[contains(@class,"banner-slide")]'):
            links = b.xpath('.//a[starts-with(@href,"/")][@href]')
            if not links: continue
            href = links[0].get("href", "")
            m = ITEM_RE.match(href.split("?")[0].split("#")[0])
            if not m: continue
            pic = b.xpath('.//img[contains(@class,"banner-img")]/@src')
            name = "".join(b.xpath('.//h1[contains(@class,"banner-title")]//text()')).strip()
            bmap[(m.group(1), m.group(2))] = (name, pic[0] if pic else "")
        results = []
        for (genre, vid), anchors in groups.items():
            name, pic, note = "", "", ""
            bname, bpic = bmap.get((genre, vid), ("", ""))
            for a in anchors:
                if not name:
                    h4 = "".join(a.xpath('.//h4//text()')).strip()
                    if h4: name = h4
                if not pic:
                    for at in ("data-original", "data-src", "src"):
                        v = a.xpath('.//img/@%s' % at)
                        if v and v[0].strip(): pic = v[0]; break
                if not note: note = "".join(a.xpath('.//span//text() | .//em//text()')).strip()
            if not name:
                for a in anchors:
                    cand = (a.xpath('./following-sibling::h4[1]//text()')
                            or a.xpath('./preceding-sibling::h4[1]//text()')
                            or a.xpath('../h4//text()')
                            or a.xpath('../following-sibling::h4[1]//text()')
                            or a.xpath('../preceding-sibling::h4[1]//text()'))
                    if cand: name = "".join(cand).strip(); break
            if not name and bname: name = bname
            if not name:
                for a in anchors:
                    if a.get("title"): name = a.get("title").strip(); break
            if not name: continue
            if not pic and bpic: pic = bpic
            results.append({"vod_id": "%s/%s" % (genre, vid), "vod_name": name,
                             "vod_pic": self._fix(pic), "vod_remarks": note})
        return self._clean_title(results)

    def _first(self, lst): return lst[0]["vod_id"] if lst else ""

    def _paged(self, base, pg):
        if pg == "1": return self._get(base)
        sep = "&" if "?" in base else "?"
        cands = ["%s" + sep + "page=%s"]
        if "?" in base:
            path, qs = base.split("?", 1)
            cands.append(path + "/%s?" + qs)
        else:
            cands.append("%s/%s")
        first = self._first(self._parse_list(self._get(base)))
        for f in cands:
            try:
                u = f % (base, pg) if f.count("%s") == 2 else f % (pg,)
            except Exception:
                continue
            html = self._get(u)
            got = self._parse_list(html)
            if got and self._first(got) != first:
                print("[INFO] 分页格式确定: %s" % u)
                return html
        print("[WARN] 未能确定分页格式，仅返回首屏")
        return self._get(base)

    def homeContent(self, filter):
        fl = {"all0": [{"key": "area", "name": "地区", "value": [{"n": "全部", "v": ""}, {"n": "中国大陆", "v": "中国大陆"}]}],
              "all1": [{"key": "area", "name": "地区", "value": [{"n": "全部", "v": ""}, {"n": "中国大陆", "v": "中国大陆"}]}]}
        return {"class": self.categories, "list": self._parse_list(self._get("/")), "filters": fl}

    def homeVideoContent(self): return {"list": self._parse_list(self._get("/"))}

    def categoryContent(self, tid, pg, filter, extend):
        pg = str(pg or "1")
        if tid.startswith("all"):
            base = "/s/all?type=%s" % tid[3:]
            area = (extend or {}).get("area", "")
            if area: base += "&area=%s" % quote(area)
        else:
            base = "/s/%s" % tid
        lst = self._parse_list(self._paged(base, pg))
        return {"page": int(pg), "pagecount": int(pg) + 1 if lst else int(pg), "limit": 30, "total": 999999, "list": lst}

    def searchContent(self, key, quick, pg="1"):
        pg = str(pg or "1")
        for p in ["/s/all?wd=%s&page=%s" % (quote(key), pg), "/search?wd=%s&page=%s" % (quote(key), pg)]:
            lst = self._parse_list(self._get(p))
            if lst: return {"list": lst, "page": int(pg)}
        return {"list": [], "page": int(pg)}

    def _field(self, text, key):
        m = re.search(r'%s\s*[:：]\s*([^\n]{1,200})' % key, text)
        return m.group(1).strip(" \u3000|/") if m else ""

    def detailContent(self, ids):
        vid = str(ids[0])
        html = self._get("/%s.htm" % vid)
        if not html: return {"list": []}
        if etree is not None:
            tree = self._tree(html, "详情页")
            if tree is not None:
                return self._detail_xpath(vid, html, tree)
        return self._detail_regex(vid, html)

    def _detail_xpath(self, vid, html, tree):
        text = "\n".join(x.strip() for x in tree.xpath('//text()') if x.strip())
        title_line = "".join(tree.xpath('//h1//text()')).strip()
        m = re.match(r'^(.*?)\s*[\(（](\d{4})[\)）]\s*$', title_line)
        name, year = (m.group(1), m.group(2)) if m else (title_line, self._field(text, "年份"))
        rate_m = re.search(r'(\d\.\d)\s*豆瓣评分', text)
        pic = ""
        for v in tree.xpath('//img/@data-original | //img/@src'):
            if v and v.strip(): pic = v; break
        freq = {}
        for a in tree.xpath('//a[starts-with(@href,"/s/")]'):
            h = a.get("href"); freq[h] = freq.get(h, 0) + 1
        baseline = Counter(freq.values()).most_common(1)[0][0] if freq else 0
        item_genres = [h.split("/s/")[-1] for h, c in freq.items() if c > baseline]
        slug_name = {g[1]: g[0] for g in GENRES}
        type_name = " ".join(slug_name.get(s, s) for s in item_genres) or self._field(text, "类型")
        vod = {"vod_id": vid, "vod_name": name, "vod_pic": self._fix(pic),
               "vod_year": year, "vod_area": self._field(text, "制片国家"),
               "type_name": type_name,
               "vod_director": " ".join(tree.xpath('//a[contains(@href,"/director/")]/text()')),
               "vod_actor": " ".join(tree.xpath('//a[contains(@href,"/performer/")]/text()')),
               "vod_remarks": (rate_m.group(1) + "分") if rate_m else (self._field(text, "集数") and ("共%s集" % self._field(text, "集数"))),
               "vod_content": ""}
        pre = text.split("在线播放", 1)[0] if "在线播放" in text else text
        lines = [l.strip() for l in pre.split("\n") if l.strip()]
        last_label = -1
        for i, l in enumerate(lines):
            if re.match(r'^[\u4e00-\u9fffA-Za-z]{2,8}[:：]', l): last_label = i
        content_lines = lines[last_label + 1:] if last_label >= 0 else lines
        vod["vod_content"] = " ".join(content_lines)[:500]
        vod["vod_play_from"] = "雪落影视"
        vod["vod_play_url"] = self._regex_eps(vid, html)
        return {"list": [vod]}

    def _regex_eps(self, vid, html):
        eps, seen = [], set()
        for m2 in re.finditer(r'<a[^>]+href="([^"]*?/play/%s-\d+\.htm[^"]*)"[^>]*>([^<]*)</a>' % re.escape(vid.split("/")[-1]), html):
            href, nm = m2.group(1), m2.group(2).strip()
            if not nm or href in seen: continue
            seen.add(href)
            eps.append(nm.replace("$", "").replace("#", "") + "$" + self._fix(href))
        return "#".join(eps) if eps else ("播放$%s/play/%s-0.htm" % (self.host, vid.split("/")[-1]))

    def _detail_regex(self, vid, html):
        text = re.sub(r'<script[\s\S]*?</script>', '', html)
        text = re.sub(r'<style[\s\S]*?</style>', '', text)
        text = re.sub(r'<[^>]+>', '\n', text)
        text = re.sub(r'&nbsp;?', ' ', text)
        text = re.sub(r'&amp;', '&', text)
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        text_flat = "\n".join(lines)
        title_line = ""
        m = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.S)
        if m: title_line = re.sub(r'<[^>]+>', '', m.group(1)).strip()
        m = re.match(r'^(.*?)\s*[\(（](\d{4})[\)）]\s*$', title_line)
        name, year = (m.group(1), m.group(2)) if m else (title_line, self._field(text_flat, "年份"))
        rate_m = re.search(r'(\d\.\d)\s*豆瓣评分', text_flat)
        pic = ""
        pm = re.search(r'class="movie-poster"[^>]*>\s*<img[^>]*src="([^"]+)"', html)
        if pm: pic = pm.group(1)
        if not pic:
            im = re.search(r'<img[^>]+src="(https?://[^"]+)"', html)
            if im: pic = im.group(1)
        freq = {}
        for h in re.findall(r'<a[^>]+href="(/s/[^"]+)"', html):
            freq[h] = freq.get(h, 0) + 1
        baseline = Counter(freq.values()).most_common(1)[0][0] if freq else 0
        item_genres = [h.split("/s/")[-1] for h, c in freq.items() if c > baseline]
        slug_name = {g[1]: g[0] for g in GENRES}
        type_name = " ".join(slug_name.get(s, s) for s in item_genres) or self._field(text_flat, "类型")
        director = " ".join(dict.fromkeys(re.findall(r'href="/director/[^"]*"[^>]*>([^<]+)<', html)))
        actor = " ".join(dict.fromkeys(re.findall(r'href="/performer/[^"]*"[^>]*>([^<]+)<', html)))
        area = self._field(text_flat, "制片国家")
        content = ""
        dm = re.search(r'class="desc"[^>]*>(.*?)</div>', html, re.S)
        if dm: content = re.sub(r'<[^>]+>', '', dm.group(1))
        content = re.sub(r'&\w+;', ' ', content).strip()[:500]
        vod = {"vod_id": vid, "vod_name": name, "vod_pic": self._fix(pic),
               "vod_year": year, "vod_area": area, "type_name": type_name,
               "vod_director": director, "vod_actor": actor,
               "vod_remarks": (rate_m.group(1) + "分") if rate_m else (self._field(text_flat, "集数") and ("共%s集" % self._field(text_flat, "集数"))),
               "vod_content": content}
        vod["vod_play_from"] = "雪落影视"
        vod["vod_play_url"] = self._regex_eps(vid, html)
        return {"list": [vod]}

    def _lines_url(self, pid, page=""):
        """获取取流地址：访问播放页（种 JSESSIONID 防抓取）后请求 /lines 拿 url3 直链。

        播放器视角：直接传播放页 URL（如 https://v.xl.in.ua/play/3046-0.htm），
        内部完成"访问播放页 → 取 var pid → 请求 /lines"，返回可播放的视频链接。
        url3 逗号分隔多线路：候选 0 常为站点 obj 代理（需跟随 302 拿真实 CDN），
        候选 1+ 为 CDN 直链（akamai/bytetos/byteimg 等，无需 cookie 直接可播）。
        """
        page = page or (self.host + "/play/%s-0.htm" % pid)
        if not page.startswith("http"): page = self._fix(page)
        self._get(page)
        # 播放页内嵌 var pid（内部ID）与 URL id 不同，取内嵌 pid
        inner = pid
        try:
            h = self.session.get(page, timeout=15)
            m = re.search(r'var\s+pid\s*=\s*(\d+)', h.text)
            if m: inner = m.group(1)
        except Exception:
            pass
        h = dict(self.headers)
        h["Referer"] = page
        h["X-Requested-With"] = "XMLHttpRequest"
        h["Accept"] = "application/json, text/javascript, */*; q=0.01"
        try:
            t_ms = int(time.time() * 1000)
            sg = _xlys_sign(inner, t_ms)
            r = self.session.get("%s/lines?t=%s&sg=%s&pid=%s" % (self.host, t_ms, sg, inner), headers=h, timeout=15)
            if r.status_code != 200: return ""
            j = r.json()
            if j.get("code") != 0: return ""
            data = j.get("data") or {}
            for cand in data.get("url3", "").split(","):
                u = cand.strip()
                if not u: continue
                # url3 硬编码旧镜像域名，替换为当前 host 避免跨镜像防盗链失败
                for old in ("https://v.xl01.eu.cc", "http://v.xl01.eu.cc", "https://v.xl.in.ua", "http://v.xl.in.ua"):
                    u = u.replace(old, self.host)
                # 站点 obj 代理（带 Referer 跟随 302 得真实 CDN，过滤防盗链跳转）
                if any(d in u for d in ("/obj/", "/ftn_handler/")):
                    try:
                        rr = self.session.get(u, headers={"Referer": page, "User-Agent": self.headers["User-Agent"]},
                                              timeout=25, allow_redirects=True, stream=True)
                        final = rr.url
                        rr.close()
                        if not (final and final.startswith("http")): continue
                        if any(b in final for b in ("baidu.com", "360.cn", "qq.com", "sohu.com")): continue
                        return final
                    except Exception:
                        continue
                return u
        except Exception as e:
            print("[ERROR] /lines 请求失败: %s" % str(e))
        return ""

    def playerContent(self, flag, id, vipFlags):
        # 提取真实 pid：兼容 "180734" / "180734-0" / "/play/180734-0.htm" / "https://v.xl01.eu.cc/play/180734-0.htm"
        m = re.search(r'/(\d+)-\d+\.htm', id) or re.search(r'^\s*(\d+)', id)
        pid = m.group(1) if m else id
        # 1) 优先调 /lines 接口抓 url3（播放页会发 /lines 请求，JSON 里取 url3）
        url = ""
        if re.fullmatch(r'\d+', pid):
            url = self._lines_url(pid, id if isinstance(id, str) and "play/" in id else "")
        if not url:
            page = pid if pid.startswith("http") else (self.host + "/play/" + pid + "-0.htm" if re.fullmatch(r'\d+', pid) else self._fix(pid))
            html = self._get(page) or ""
            # 2) 播放页内联 {"code":0,"data":{"url3":...}}（备选）
            jm = re.search(r'\{"code"\s*:\s*0[^{}]*"data"\s*:\s*(\{[^{}]*\})\}', html.replace("\\/", "/"))
            if jm:
                try:
                    data = json.loads(jm.group(1))
                    url3 = data.get("url3", "")
                    url = url3.split(",")[0].strip() if url3 else ""
                except Exception:
                    url = ""
            # 3) 通用正则兜底
            if not url:
                for p in [r'var\s+player_\w*\s*=\s*(\{.*?\})\s*[<;]', r'"url"\s*:\s*"([^"]+)"', r'var\s+now\s*=\s*["\']([^"\']+)["\']', r'url:\s*["\']([^"\']+\.(?:m3u8|mp4)[^"\']*)["\']', r'(https?://[^\s"\'\\<>]+\.(?:m3u8|mp4)[^\s"\'\\<>]*)']:
                    m = re.search(p, html.replace("\\/", "/"), re.S)
                    if not m: continue
                    val = m.group(1)
                    if val.startswith("{"):
                        try:
                            val = json.loads(val).get("url", "")
                        except Exception:
                            m2 = re.search(r'"url"\s*:\s*"([^"]+)"', val)
                            val = m2.group(1).replace("\\/", "/") if m2 else ""
                    if val: url = self._fix(val); break
        if not url: return {"parse": 1, "url": pid, "header": self.headers}
        return {"parse": 0, "url": url, "header": {"User-Agent": self.headers["User-Agent"], "Referer": self.host + "/"}}
