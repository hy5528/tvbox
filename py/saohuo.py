# -*- coding: utf-8 -*-
import re, json, time
from urllib.parse import quote
from lxml import etree
from base.spider import Spider

class Spider(Spider):
	def getName(self): return "骚火电影"
# 最新备用域名：https://shdy2.com，请及时收藏网址发布页 http://shapp.us
	def init(self, extend=""):
		self.host = "https://shdy5.us"
		self.headers = {"User-Agent": "Mozilla/5.0", "Accept-Language": "zh-CN,zh;q=0.9", "Referer": "https://www.baidu.com/"}
		self.categories = [
			{"type_id": "1", "type_name": "电影"},
			{"type_id": "10", "type_name": "科幻"},
			{"type_id": "11", "type_name": "战争"},
			{"type_id": "12", "type_name": "犯罪"},
			{"type_id": "13", "type_name": "动画"},
			{"type_id": "14", "type_name": "奇幻"},
			{"type_id": "15", "type_name": "剧情"},
			{"type_id": "16", "type_name": "冒险"},
			{"type_id": "17", "type_name": "悬疑"},
			{"type_id": "18", "type_name": "惊悚"},
			{"type_id": "19", "type_name": "其它"},
			{"type_id": "2", "type_name": "电视剧"},
			{"type_id": "20", "type_name": "大陆剧"},
			{"type_id": "21", "type_name": "港剧"},
			{"type_id": "22", "type_name": "韩剧"},
			{"type_id": "23", "type_name": "美剧"},
			{"type_id": "24", "type_name": "日剧"},
			{"type_id": "25", "type_name": "英剧"},
			{"type_id": "26", "type_name": "台剧"},
			{"type_id": "27", "type_name": "其它剧"},
			{"type_id": "top", "type_name": "排行榜"},
			{"type_id": "new", "type_name": "最近更新"},
		]

	def _get(self, url, referer=None, asjson=False):
		headers = dict(self.headers)
		if referer: headers["Referer"] = referer
		for i in range(3):
			try:
				r = self.fetch(url, headers=headers, timeout=15, verify=False)
				if not asjson:
					return r.text
				try: return r.json()
				except Exception: return {}
			except Exception as e:
				if i == 2: break
				time.sleep(1.5)
		return {} if asjson else ""

	def _post(self, url, payload, referer):
		for i in range(3):
			try:
				r = self.post(url, json=payload, headers={"Content-Type": "application/json", "Referer": referer}, timeout=20, verify=False)
				if r.status_code == 200:
					try: return r.json()
					except Exception: return {}
			except Exception:
				pass
			if i == 2: break
			time.sleep(1.5)
		return {}

	def _fix(self, u):
		if not u: return ""
		if u.startswith("//"): return "https:" + u
		if u.startswith("/"): return self.host + u
		return u

	def _cards(self, html):
		if not html: return []
		tree = etree.HTML(html)
		out, seen = [], set()
		for li in tree.xpath('//ul[contains(@class,"v_list")]//li'):
			try:
				a = li.xpath('.//a[contains(@href,"/movie/")]')
				if not a: continue
				a = a[0]
				m = re.search(r'/movie/(\d+)\.html', a.get("href", ""))
				if not m or m.group(1) in seen: continue
				seen.add(m.group(1))
				pic = (a.xpath('.//img/@data-original') or a.xpath('.//img/@src') or ["", ])[0]
				title = a.get("title", "").strip() or "".join(a.xpath('.//img/@alt')).strip()
				if not title: continue
				rem = "".join(li.xpath('.//*[contains(@class,"v_note")]//text()')).strip()
				out.append({"vod_id": m.group(1), "vod_name": title, "vod_pic": self._fix(pic), "vod_remarks": rem})
			except Exception:
				continue
		return out

	def homeContent(self, filter):
		return {"class": self.categories, "list": self._cards(self._get(self.host)), "filters": {}}

	def homeVideoContent(self):
		return {"list": self._cards(self._get(self.host))}

	def categoryContent(self, tid, pg, filter, extend):
		pg = int(pg or 1)
		if tid in ("top", "new"):
			url = f"{self.host}/{tid}.html"
			return {"page": pg, "pagecount": 9999, "limit": 24, "total": 999999, "list": self._text_top(self._get(url))}
		url = f"{self.host}/list/{tid}.html" if pg == 1 else f"{self.host}/list/{tid}-{pg}.html"
		return {"page": pg, "pagecount": 9999, "limit": 24, "total": 999999, "list": self._cards(self._get(url))}

	def _text_top(self, html):
		if not html: return []
		tree = etree.HTML(html)
		out, seen = [], set()
		for li in tree.xpath('//*[contains(@class,"text_list")]//li'):
			try:
				a = li.xpath('.//a[contains(@href,"/movie/")]')
				if not a: continue
				a = a[0]
				m = re.search(r'/movie/(\d+)\.html', a.get("href", ""))
				if not m or m.group(1) in seen: continue
				seen.add(m.group(1))
				title = "".join(a.xpath(".//text()")).strip() or a.get("title", "").strip()
				if not title: continue
				out.append({"vod_id": m.group(1), "vod_name": title, "vod_pic": "", "vod_remarks": "".join(li.xpath('.//*[contains(@class,"v_note")]//text()')).strip()})
			except Exception:
				continue
		return out

	def detailContent(self, ids):
		vid = ids[0]
		html = self._get(f"{self.host}/movie/{vid}.html")
		result = {"list": []}
		if not html: return result
		tree = etree.HTML(html)
		name = "".join(tree.xpath('//h1[contains(@class,"v_title")]//a/text() | //h1[contains(@class,"v_title")]/text()')).strip()
		pic = "".join(tree.xpath('//*[contains(@class,"m_background")]/@style'))
		pm = re.search(r'url\(["\']?([^"\')]+)', pic)
		pic = pm.group(1) if pm else "".join(tree.xpath('//*[contains(@class,"v_info")]//img/@data-original | //*[contains(@class,"v_info")]//img/@src'))
		froms = [x for x in ["".join(x.xpath(".//text()")).strip() for x in tree.xpath('//*[contains(@class,"from_list")]//li')] if x]
		li_blocks = []
		for li in tree.xpath('//*[@id="play_link"]/li | //*[contains(@class,"play_list")]/li'):
			eps = []
			for a in li.xpath('.//a[contains(@href,"/play/")]'):
				nm = "".join(a.xpath(".//text()")).strip() or "播放"
				eps.append(f'{nm}${self._fix(a.get("href",""))}')
			if eps: li_blocks.append("#".join(eps))
		if not li_blocks:
			eps = [f'{"".join(a.xpath(".//text()")).strip() or "0"}${self._fix(a.get("href",""))}' for a in tree.xpath('//*[contains(@class,"play_list")]//a[contains(@href,"/play/")]')]
			if eps: li_blocks.append("#".join(eps))
		if not li_blocks: return result
		if len(li_blocks) == 1 and len(froms) > 1:
			froms = ["线路1"]
		sources = froms if froms else ["线路1"]
		info = {"vod_id": vid, "vod_name": name, "vod_pic": self._fix(pic),
				"vod_play_from": "$$$".join(sources), "vod_play_url": "$$$".join(li_blocks)}
		meta = re.search(r'</h1>.*?<p>(.*?)</p>', html, re.S)
		if meta:
			txt = re.sub(r'<[^>]+>', '', meta.group(1))
			txt = re.sub(r'\s*剧情[简繁]?介.*$', '', txt)
			def _fac(ck):
				m2 = re.search(ck + r'\s*[:：]\s*([^/|<]+)', txt)
				return m2.group(1).strip() if m2 else ""
			info["vod_director"] = _fac("导演")
			info["vod_actor"] = _fac("主演")
			info["vod_remarks"] = _fac("状态")
			segs = [s.strip() for s in re.split(r'[/|]', txt) if s.strip()]
			segs = [s for s in segs if not re.match(r'^[\d.]+分$', s)]
			year = next((s for s in segs if re.fullmatch(r'(19|20)\d{2}', s)), "")
			rest = [s for s in segs if s != year and "导演" not in s and "主演" not in s and "状态" not in s]
			if len(segs) > 0:
				info["vod_area"] = rest[0] if rest else info.get("vod_area", "")
				info["vod_class"] = rest[1] if len(rest) > 1 else info.get("vod_class", "")
				info["vod_year"] = year
		result["list"].append(info)
		return result

	def searchContent(self, key, quick, pg="1"):
		url = f"{self.host}/s/{quote(key)}----------.html"
		return {"list": self._cards(self._get(url)), "page": int(pg)}

	def playerContent(self, flag, id, vipFlags):
		url = self._fix(id)
		html = self._get(url)
		play = self._grab_m3u8(html) if html else ""
		if not play:
			fr = re.search(r'<iframe[^>]+src=["\']?([^>"\'\s]+)', html or "")
			if fr:
				fsrc = self._fix(str(fr.group(1)))
				play = fsrc if ".m3u8" in fsrc else ""
				if not play and "hhjx.hhplayer.com" in fsrc:
					play = self._hhjx_resolve(fsrc, referer=url)
				if not play:
					h2 = self._get(fsrc, referer=url)
					play = self._grab_m3u8(h2) if h2 else ""
				if not play:
					h2 = h2 or self._get(fsrc, referer=url)
					mm = re.search(r'["\']?(https?://[^\s"\']+\.(?:mp4|mkv|flv)[^\s"\']*)["\']', h2)
					play = mm.group(1) if mm else ""
		if play and ("http://" not in play and "https://" not in play):
			play = ""
		if play and not play.startswith("http"):
			mm = re.search(r'(https?://[^\s"\']+)', play)
			play = mm.group(1) if mm else play
		header = {"User-Agent": "Mozilla/5.0"}
		if play:
			hm = re.search(r'https?://([^/]+)', play)
			header["Referer"] = f"https://{hm.group(1)}/" if hm else self.host
		return {"parse": 0, "url": play, "header": json.dumps(header)}

	def _hhjx_resolve(self, pgsrc, referer=""):
		try:
			import json
			html = self._get(pgsrc, referer=referer)
			bs = re.search(r'__HHJX_BOOTSTRAP__=(\{.*?\});', html or "", re.S)
			if not bs: return ""
			cfg = json.loads(bs.group(1))
			host = re.match(r'(https?://[^/]+)', pgsrc).group(1)
			payload = {"url": cfg["url"], "t": cfg["t"], "key": cfg["key"], "client_fallback": False}
			j = self._post(host + "/api/parse", payload, pgsrc)
			if j.get("ext") == "youku": return ""
			return j.get("url", "") if j.get("ok") or j.get("code") == 200 else ""
		except Exception:
			return ""

	def _grab_m3u8(self, html):
		if not html: return ""
		for pat in [r'(https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*)',
					r'["\'](https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*)["\']',
					r'(?:player_?\w+|url)\s*[:=]\s*["\']([^"\']+\.m3u8[^"\']*)["\']',
					r'var\s+\w+\s*=\s*["\']([^"\']+\.m3u8[^"\']*)["\']']:
			m = re.search(pat, html, re.I)
			if m:
				u = m.group(1)
				if u.startswith("//"): return "https:" + u
				if u.startswith("http"): return u
		return ""

	def isVideoFormat(self, url): return ".m3u8" in url or ".mp4" in url

	def manualVideoCheck(self): return False

	def localProxy(self, param): return None

	def destroy(self): return None