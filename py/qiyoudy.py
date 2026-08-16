#coding=utf-8
#!/usr/bin/python
import re
import sys
import json
import requests
from lxml import etree
from urllib.parse import quote

sys.path.append('..')
from base.spider import Spider


class Spider(Spider):
	def getName(self):
		return "奇优影院"

	def init(self, extend):
		self.host = "http://www.qiyoudy2.com"
		self.spiderUA = "Mozilla/5.0 (compatible; Baiduspider/2.0; +http://www.baidu.com/search/spider.html)"
		self.site = {"User-Agent": self.spiderUA, "Referer": self.host + "/"}
		self.categories = [{"type_id": "1", "type_name": "电影"}, {"type_id": "2", "type_name": "电视剧"}, {"type_id": "3", "type_name": "动漫"}, {"type_id": "4", "type_name": "综艺"}]

	def isVideoFormat(self, url):
		return False

	def manualVideoCheck(self):
		pass

	def _get(self, url, referer=None):
		try:
			headers = {"User-Agent": self.spiderUA, "Referer": referer or self.host + "/"}
			r = requests.get(url, headers=headers, timeout=20)
			raw = r.content
			if raw.startswith(b"\xef\xbb\xbf"):
				raw = raw[3:]
			if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
				raw = raw.encode("utf-16", errors="ignore") if isinstance(raw, str) else raw.decode("utf-16", errors="ignore").encode("utf-8")
			text = raw.decode("utf-8", errors="ignore")
			text = re.sub(r"^\s*<\?xml[^>]*\?>", "", text)
			return text
		except:
			return None

	def _fix(self, u):
		if not u:
			return ""
		if u.startswith("//"):
			return "http:" + u
		if u.startswith("/"):
			return self.host + u
		return u

	def _parse_list(self, html):
		if not html:
			return []
		tree = etree.HTML(html.encode("utf-8", errors="ignore"))
		result, seen = [], set()
		for a in tree.xpath('//a[contains(@href,"/view/")]'):
			try:
				href = a.get("href", "")
				m = re.search(r"/view/(\d+)\.html", href)
				if not m or m.group(1) in seen:
					continue
				seen.add(m.group(1))
				title = a.get("title", "") or "".join(a.xpath('.//text()')).strip() or "".join(a.xpath('.//@title'))
				pic = a.get("data-original") or ""
				if not pic:
					img = a.xpath('.//img')
					if img:
						pic = img[0].get("data-original") or img[0].get("data-src") or img[0].get("src", "")
				pic = self._fix(pic)
				if not pic.startswith("http"):
					pic = ""
				result.append({"vod_id": m.group(1), "vod_name": title, "vod_pic": pic})
			except:
				continue
		return result

	def homeContent(self, filter):
		html = self._get(self.host + "/")
		return {"class": self.categories, "list": self._parse_list(html), "filters": {}}

	def homeVideoContent(self):
		return {}

	def categoryContent(self, tid, pg, filter, extend):
		url = f"{self.host}/list/{tid}.html" if str(pg) == "1" else f"{self.host}/list/{tid}_{pg}.html"
		html = self._get(url)
		return {"page": int(pg), "pagecount": 99, "limit": 36, "total": 999, "list": self._parse_list(html)}

	def detailContent(self, ids):
		result = {"list": []}
		for vid in ids:
			try:
				html = self._get(self.host + "/view/" + vid + ".html")
				if not html:
					continue
				tree = etree.HTML(html.encode("utf-8", errors="ignore"))
				name = "".join(tree.xpath('//h1//text()')).strip() or "".join(tree.xpath('//h2//text()')).strip()
				pic = "".join(tree.xpath('//div[contains(@class,"stui-content__thumb")]//img/@data-original')) or "".join(tree.xpath('//div[contains(@class,"stui-content__thumb")]//img/@src'))
				# 线路名: nav-tabs 里 #downN 对应的文本
				tab_map, sources = {}, []
				for li in tree.xpath('//ul[contains(@class,"nav-tabs")]/li/a[@data-toggle="tab"]'):
					href = li.get("href", "")
					txt = "".join(li.xpath('.//text()')).strip()
					if href.startswith("#") and txt:
						tab_map[href[1:]] = txt
						sources.append(txt)
				panels = tree.xpath('//div[contains(@class,"tab-pane") and starts-with(@id,"down")]')
				episodes = []
				for pane in panels:
					eps = []
					for a in pane.xpath('.//a[contains(@href,"/play/")]'):
						t = a.get("title", "") or "".join(a.xpath('.//text()')).strip()
						eps.append(f"{t}${self._fix(a.get('href',''))}")
					if eps:
						episodes.append("#".join(eps))
				if not sources:
					sources = [f"线路{i+1}" for i in range(len(episodes))]
				if not episodes:
					fr = "".join(tree.xpath('//div[contains(@class,"play-btn")]//a/@href'))
					episodes = [f"正片${self._fix(fr)}"] if fr else []
					sources = ["线路1"] if fr else []
				result["list"].append({"vod_id": vid, "vod_name": name, "vod_pic": self._fix(pic), "vod_play_from": "$$$".join(sources), "vod_play_url": "$$$".join(episodes)})
			except:
				continue
		return result

	def _parse_play(self, url):
		html = self._get(url)
		if not html:
			return ""
		d = re.search(r'videoUrl\s*=\s*"([^"]+)"', html)
		if d:
			return d.group(1)
		m = re.search(r'<iframe[^>]*src="([^"]+)"', html)
		if not m:
			return ""
		fsrc = m.group(1)
		if fsrc.startswith("//"):
			fsrc = "http:" + fsrc
		elif fsrc.startswith("/"):
			fsrc = self.host + fsrc
		fhtml = self._get(fsrc, referer=self.host)
		if fhtml:
			d = re.search(r'videoUrl\s*=\s*"([^"]+)"', fhtml)
			if d:
				return d.group(1)
			# api.php 二次接口
			Url = re.search(r'const Url = "([^"]+)"', fhtml)
			Sign = re.search(r'const Sign = "([^"]+)"', fhtml)
			From = re.search(r'const From = "([^"]+)"', fhtml)
			if Url and Sign:
				try:
					mh = re.match(r'^(https?://[^/]+)', fsrc)
					api = (mh.group(1) if mh else self.host) + "/player/api.php"
					params = {"url": Url.group(1), "sign": Sign.group(1), "t": From.group(1) if From else "m3u8"}
					r = requests.get(api, params=params, headers={"User-Agent": self.spiderUA, "Referer": self.host + "/"}, timeout=20)
					j = r.json()
					if j.get("code") == 200 and j.get("url"):
						return j["url"]
				except:
					pass
		return ""

	def searchContent(self, key, quick, pg="1"):
		html = self._get(self.host + "/search.php?searchword=" + quote(key))
		return {"list": self._parse_list(html), "page": int(pg)}

	def playerContent(self, flag, id, vipFlags):
		url = self._parse_play(self._fix(id))
		header = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"}
		try:
			m = re.match(r'^https?://[^/]+', url)
			if m:
				header["Referer"] = m.group(0) + "/"
		except:
			pass
		return {"parse": 0, "url": url, "header": json.dumps(header)}

	def localProxy(self, params):
		pass

	def destroy(self):
		return "正常进入"