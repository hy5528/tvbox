#coding=utf-8
#!/usr/bin/python
import re
import sys
import json
import base64
import requests
from lxml import etree
from urllib.parse import quote

sys.path.append('..')
from base.spider import Spider

class Spider(Spider):
	def getName(self):
		return "爱看机器人"

	def init(self, extend):
		self.host = "https://www1.aikanbot.com"
		self.header = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36", "Referer": self.host + "/"}
		self.categories = [{"type_id": "1", "type_name": "电影"}, {"type_id": "2", "type_name": "剧集"}, {"type_id": "18", "type_name": "动漫"}, {"type_id": "19", "type_name": "综艺"}, {"type_id": "20", "type_name": "纪录片"}]
		self.embed = True

	def isVideoFormat(self, url):
		return False

	def manualVideoCheck(self):
		pass

	def _get(self, url):
		try:
			r = requests.get(url, headers=self.header, timeout=20)
			r.encoding = r.apparent_encoding or "utf-8"
			return r.text
		except:
			return None

	def _fix(self, u):
		if not u:
			return ""
		if u.startswith("//"):
			return "https:" + u
		if u.startswith("/"):
			return self.host + u
		return u

	def _img(self, vid, url):
		url = self._fix(url)
		if not url:
			return ""
		# 豆瓣图床防盗链,TVBox 加载不带 Referer 会 403,直接内嵌保证显示
		if self.embed and "doubanio.com" in url:
			try:
				r = requests.get(url, headers={"User-Agent": self.header["User-Agent"], "Referer": "https://movie.douban.com/"}, timeout=12)
				if r.status_code == 200 and r.headers.get("Content-Type", "").startswith("image/"):
					return "data:image/jpeg;base64," + base64.b64encode(r.content).decode()
			except:
				pass
		return url

	def _parse_list(self, html):
		if not html:
			return []
		tree = etree.HTML(html)
		result, seen = [], set()
		for a in tree.xpath('//a[contains(@href,"/play/")]'):
			try:
				href = a.get("href", "")
				m = re.search(r"/play/(\d+)", href)
				if not m or m.group(1) in seen:
					continue
				seen.add(m.group(1))
				img = a.xpath('.//img')
				title = img[0].get("alt", "") if img else ""
				if not title:
					title = "".join(a.xpath('.//text()')).strip()
				pic = ""
				if img:
					pic = self._img(m.group(1), img[0].get("data-src") or img[0].get("src", ""))
				result.append({"vod_id": m.group(1), "vod_name": title, "vod_pic": pic})
			except:
				continue
		return result

	def _token(self, vid, etok):
		out = []
		for ch in vid[-4:]:
			k = (ord(ch) - 48) % 3 + 1 if ch.isdigit() else 1
			out.append(etok[k:k + 8])
			etok = etok[k + 8:]
		return "".join(out)

	def _lines(self, vid):
		try:
			html = self._get(self.host + "/play/" + vid)
			if not html:
				return []
			etok = re.search(r'id="e_token"\s+value="([^"]+)', html)
			if not etok:
				return []
			tk = self._token(vid, etok.group(1))
			url = self.host + "/api/getResN"
			params = {"videoId": vid, "mtype": "1", "token": tk}
			r = requests.get(url, params=params, headers=self.header, timeout=20)
			data = r.json()
			if data.get("state") != 1:
				return []
			lines = []
			for it in data["data"]["list"]:
				eps = []
				try:
					for res in json.loads(it["resData"]):
						for ep in res["url"].split("#"):
							if ep and "$" in ep:
								name, link = ep.split("$", 1)
								if link.endswith(".m3u8"):
									eps.append(name + "$" + self._fix(link))
				except:
					pass
				if eps:
					lines.append("#".join(eps))
			return lines
		except:
			return []

	def homeContent(self, filter):
		html = self._get(self.host + "/")
		return {"class": self.categories, "list": self._parse_list(html), "filters": {}}

	def homeVideoContent(self):
		return {}

	def categoryContent(self, tid, pg, filter, extend):
		url = f"{self.host}/category/{tid}?p={pg}"
		if pg == "1":
			url = f"{self.host}/category/{tid}"
		html = self._get(url)
		return {"page": int(pg), "pagecount": 99, "limit": 24, "total": 999, "list": self._parse_list(html)}

	def detailContent(self, ids):
		result = {"list": []}
		for vid in ids:
			try:
				html = self._get(self.host + "/play/" + vid)
				if not html:
					continue
				tree = etree.HTML(html)
				name = "".join(tree.xpath('//h1//text()')).strip() or "".join(tree.xpath('//h2//text()')).strip()
				pic = ""
				img = tree.xpath('//img[contains(@class,"cover")]')
				if img:
					pic = self._img(vid, img[0].get("data-src") or img[0].get("src", ""))
				lines = self._lines(vid)
				froms = "$$$".join([f"线路{i+1}" for i in range(len(lines))]) if lines else "线路1"
				urls = "$$$".join(lines) if lines else ""
				result["list"].append({"vod_id": vid, "vod_name": name, "vod_pic": pic, "vod_play_from": froms, "vod_play_url": urls})
			except:
				continue
		return result

	def searchContent(self, key, quick, pg="1"):
		html = self._get(self.host + "/search?q=" + quote(key))
		return {"list": self._parse_list(html), "page": int(pg)}

	def playerContent(self, flag, id, vipFlags):
		url = self._fix(id)
		header = {"User-Agent": self.header["User-Agent"]}
		try:
			m = re.match(r'^https?://[^/]+', url)
			if m:
				header["Referer"] = m.group(0) + "/"
		except:
			header["Referer"] = self.host + "/"
		return {"parse": 0, "url": url, "header": json.dumps(header)}

	def localProxy(self, params):
		pass

	def destroy(self):
		return "正常进入"
