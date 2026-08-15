# -*- coding: utf-8 -*-
import re
import sys
import json
from urllib.parse import quote
from lxml import etree

try:
    import urllib3
    urllib3.disable_warnings()
except Exception:
    pass

sys.path.append('..')
from base.spider import Spider

class Spider(Spider):
	def getName(self): return "可可影视"

	def init(self, extend=""):
		self.host = "https://www.kkys20.com"
		self.image_host = "https://vres.cyscyy.com"
		self.headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36", "Referer": self.host + "/"}
		self.categories = [
			{"type_id": "1", "type_name": "电影"},
			{"type_id": "2", "type_name": "连续剧"},
			{"type_id": "3", "type_name": "动漫"},
			{"type_id": "4", "type_name": "综艺"},
			{"type_id": "6", "type_name": "短剧"},
		]
		self.filters = self._build_filters()

	def _build_filters(self):
		types = {
			"1": ["剧情", "喜剧", "动作", "爱情", "恐怖", "惊悚", "犯罪", "科幻", "悬疑", "奇幻", "冒险", "战争", "历史", "古装", "家庭", "传记", "武侠", "歌舞", "短片", "动画", "儿童", "职场"],
			"2": ["剧情", "爱情", "喜剧", "犯罪", "悬疑", "古装", "动作", "家庭", "惊悚", "奇幻", "美剧", "科幻", "历史", "战争", "韩剧", "武侠", "言情", "恐怖", "冒险", "都市", "职场"],
			"3": ["动态漫画", "剧情", "动画", "喜剧", "冒险", "动作", "奇幻", "科幻", "儿童", "搞笑", "爱情", "家庭", "短片", "热血", "益智", "悬疑", "经典", "校园", "Anime", "运动", "亲子", "青春", "恋爱", "武侠", "惊悚"],
			"4": ["纪录", "真人秀", "记录", "脱口秀", "剧情", "历史", "喜剧", "传记", "相声", "节目", "歌舞", "冒险", "运动", "Season", "犯罪", "短片", "搞笑", "晚会"],
			"6": ["王爷太子", "霸道总裁", "屌丝逆袭", "赘婿系列", "重生系列", "穿越短剧", "美女总裁", "娇妻系列", "龙王系列", "都市言情", "逆袭", "甜宠", "虐恋", "穿越", "重生", "剧情", "科幻", "武侠", "爱情", "动作", "战争", "冒险", "其它"],
		}
		areas = {
			"1": [("大陆", "中国大陆"), ("香港", "中国香港"), ("台湾", "中国台湾"), ("美国", "美国"), ("日本", "日本"), ("韩国", "韩国"), ("英国", "英国"), ("法国", "法国"), ("德国", "德国"), ("印度", "印度"), ("泰国", "泰国"), ("丹麦", "丹麦"), ("瑞典", "瑞典"), ("巴西", "巴西"), ("加拿大", "加拿大"), ("俄罗斯", "俄罗斯"), ("意大利", "意大利"), ("比利时", "比利时"), ("爱尔兰", "爱尔兰"), ("西班牙", "西班牙"), ("澳大利亚", "澳大利亚"), ("其他", "其他")],
			"2": [("大陆", "中国大陆"), ("香港", "中国香港"), ("韩国", "韩国"), ("美国", "美国"), ("日本", "日本"), ("法国", "法国"), ("英国", "英国"), ("德国", "德国"), ("台湾", "中国台湾"), ("泰国", "泰国"), ("印度", "印度"), ("其他", "其他")],
			"3": [("日本", "日本"), ("大陆", "中国大陆"), ("台湾", "中国台湾"), ("美国", "美国"), ("香港", "中国香港"), ("韩国", "韩国"), ("英国", "英国"), ("法国", "法国"), ("德国", "德国"), ("印度", "印度"), ("泰国", "泰国"), ("丹麦", "丹麦"), ("瑞典", "瑞典"), ("巴西", "巴西"), ("加拿大", "加拿大"), ("俄罗斯", "俄罗斯"), ("意大利", "意大利"), ("比利时", "比利时"), ("爱尔兰", "爱尔兰"), ("西班牙", "西班牙"), ("澳大利亚", "澳大利亚"), ("其他", "其他")],
			"4": [("大陆", "中国大陆"), ("香港", "中国香港"), ("台湾", "中国台湾"), ("美国", "美国"), ("日本", "日本"), ("韩国", "韩国"), ("其他", "其他")],
		}
		langs = ["国语", "粤语", "英语", "日语", "韩语", "法语", "其他"]
		years = [("2026", "2026"), ("2025", "2025"), ("2024", "2024"), ("2023", "2023"), ("2022", "2022"), ("2021", "2021"), ("2020", "2020"), ("10年代", "2010_2019"), ("00年代", "2000_2009"), ("90年代", "1990_1999"), ("80年代", "1980_1989"), ("更早", "0_1979")]
		sorts = {"1": [("综合", "1"), ("最新", "2"), ("最热", "3"), ("评分", "4")], "2": [("综合", "1"), ("最新", "2"), ("最热", "3"), ("评分", "4")], "3": [("综合", "1"), ("最新", "2"), ("最热", "3"), ("评分", "4")], "4": [("综合", "1"), ("最新", "2"), ("最热", "3"), ("评分", "4")], "6": [("综合", "1"), ("最新", "2"), ("最热", "3")]}
		result = {}
		for c in self.categories:
			tid = c["type_id"]
			items = [{"key": "type", "name": "类型", "value": [{"n": "全部", "v": ""}] + [{"n": t, "v": t} for t in types.get(tid, [])]}]
			if tid != "6":
				items += [
					{"key": "area", "name": "地区", "value": [{"n": "全部", "v": ""}] + [{"n": n, "v": v} for n, v in areas.get(tid, [])]},
					{"key": "lang", "name": "语言", "value": [{"n": "全部", "v": ""}] + [{"n": l, "v": l} for l in langs]},
					{"key": "year", "name": "年份", "value": [{"n": "全部", "v": ""}] + [{"n": n, "v": v} for n, v in years]},
				]
			items.append({"key": "sort", "name": "排序", "value": [{"n": n, "v": v} for n, v in sorts.get(tid, sorts["1"])]})
			result[tid] = items
		return result

	def _get(self, url):
		try:
			r = self.fetch(url, headers=self.headers, timeout=15, verify=False)
			r.encoding = "utf-8"  # 站点固定 UTF-8;apparent_encoding 探测很慢且多余
			return r.text
		except Exception:
			return None

	def _fix(self, u):
		if not u: return ""
		if u.startswith("//"): return "https:" + u
		if u.startswith("/"): return self.host + u
		return u

	def _pic(self, u):
		if not u: return ""
		if u.startswith("//"): return "https:" + u
		if u.startswith("/"): return self.image_host + u
		return u

	def _html(self, content):
		# Chaquopy(UCS-4)下 etree.HTML(str) 遇数学字母等增补平面字符会报
		# "encoding not supported USC4 little endian",统一走 bytes 路径
		if not content: return None
		return etree.HTML(content.encode('utf-8'))

	def _playable(self, url):
		# 播放页是否内嵌可直接播放的 m3u8/mp4(否则为 APP 专属线路)。
		# 光有 URL 不够——部分 CDN(如 vip.ffzy-plays.com)会 403,需带播放器同款 headers 实测出流
		h = self._get(url)
		if not h: return False
		m = re.search(r'playSource\s*=\s*\{[^}]*?src:\s*"([^"]+)"', h) or \
			re.search(r'https?://[^\s"\'<>]+\.(?:m3u8|mp4|flv|mkv|webm)[^\s"\'<>]*', h)
		if not m: return False
		u = self._fix(m.group(1))
		header = {"User-Agent": self.headers["User-Agent"], "Referer": self._referer(u)}
		try:
			r = self.fetch(u, headers=header, timeout=8, verify=False, stream=True)
			head = r.raw.read(16).decode('utf-8', 'ignore').lstrip().lower()
			r.close()
			return r.status_code == 200 and bool(head) and not head.startswith('<')
		except Exception:
			return False

	def _referer(self, url):
		# ts 分片防盗链要求 Referer 精确等于 m3u8 去 query 的地址,域名根会返回 3 字节 "OK\n"
		u = url or ""
		hm = re.match(r'(https?://[^/]+/[^\s?]+\.m3u8)', u)
		if hm:
			return hm.group(1)
		hm = re.match(r'(https?://[^/]+)', u)
		return hm.group(1) + "/" if hm else self.host + "/"

	def _play_lines(self, tree):
		# 详情页“切换线路”与“选集播放”通过索引一一对应,这里成对提取。
		sources = []
		for a in tree.xpath('//div[contains(@class,"source-list-box-main")]//a[contains(@class,"source-item")]'):
			name = "".join(a.xpath('.//span[contains(@class,"source-item-label")]//text()')).strip()
			if name:
				sources.append(name)
		lines = []
		for li in tree.xpath('//div[contains(@class,"episode-list-box-main")]/div[contains(@class,"episode-list")]'):
			eps = [f'{"".join(a.xpath(".//text()")).strip() or "播放"}${self._fix(a.get("href", ""))}' for a in li.xpath('.//a[contains(@href,"/play/")]')]
			if eps:
				lines.append(eps)
		if not lines:
			return []
		if not sources:
			sources = [f"线路{i + 1}" for i in range(len(lines))]
		while len(lines) > len(sources):
			sources.append(f"线路{len(sources) + 1}")
		pairs = list(zip(sources[:len(lines)], lines))
		return [(name, eps) for name, eps in pairs if "4k" not in name.lower()]

	def _parse_list(self, html):
		if not html: return []
		tree = self._html(html)
		if tree is None: return []
		out, seen = [], set()
		for a in tree.xpath('//div[contains(@class,"module-item")]//a[contains(@class,"v-item")]'):
			href = a.get("href", "")
			m = re.search(r'/detail/(\d+)\.html', href)
			if not m or m.group(1) in seen: continue
			seen.add(m.group(1))
			name = "".join(a.xpath('.//div[contains(@class,"v-item-title")][not(@style)]//text()')).strip()
			if not name: continue
			pic = (a.xpath('.//img[not(contains(@data-original,"logo_placeholder"))]/@data-original') or [""])[0]
			rem = "".join(a.xpath('.//div[contains(@class,"v-item-bottom")]//text()')).strip()
			out.append({"vod_id": m.group(1), "vod_name": name, "vod_pic": self._pic(pic), "vod_remarks": rem})
		return out

	def homeContent(self, filter):
		return {"class": self.categories, "list": self._parse_list(self._get(self.host + "/")), "filters": self.filters}

	def homeVideoContent(self):
		return {"list": self._parse_list(self._get(self.host + "/"))}

	def categoryContent(self, tid, pg, filter, extend):
		extend = extend or {}
		typ = quote(str(extend.get("type", "")))
		area = quote(str(extend.get("area", "")))
		lang = quote(str(extend.get("lang", "")))
		year = quote(str(extend.get("year", "")))
		sort = str(extend.get("sort", "3") or "3")
		page = int(pg or 1)
		html = self._get(f"{self.host}/show/{tid}-{typ}-{area}-{lang}-{year}-{sort}-{page}.html")
		items = self._parse_list(html)
		pagecount = page + 1 if html and "page-item-next" in html else page
		return {"page": page, "pagecount": pagecount, "limit": len(items), "total": len(items), "list": items}

	def _names(self, txt):
		txt = re.sub(r'\s*/\s*', '/', txt)
		return re.sub(r'\s+', ' ', txt).strip(' /')

	def detailContent(self, ids):
		vid = ids[0]
		html = self._get(f"{self.host}/detail/{vid}.html")
		result = {"list": []}
		if not html: return result
		tree = self._html(html)
		if tree is None: return result
		# 站点用 CSS 隐藏奇数位 strong(水印),可见标题为偶数位;无水印时退化为 strong[1]
		name = "".join(tree.xpath('//div[contains(@class,"detail-title")]//strong[position() mod 2 = 0]/text()')).strip()
		if not name: name = "".join(tree.xpath('//div[contains(@class,"detail-title")]//strong[1]/text()')).strip()
		pic = (tree.xpath('//div[contains(@class,"detail-pic")]//img[not(contains(@data-original,"logo_placeholder"))]/@data-original') or [""])[0]
		desc = "".join(tree.xpath('//div[contains(@class,"detail-desc")]//text()')).strip()
		vod = {"vod_id": vid, "vod_name": name, "vod_pic": self._pic(pic), "vod_content": desc}
		rows = {}
		for r in tree.xpath('//div[contains(@class,"detail-info-row")]'):
			k = "".join(r.xpath('.//*[contains(@class,"detail-info-row-side")]//text()')).strip().rstrip(":")
			v = "".join(r.xpath('.//*[contains(@class,"detail-info-row-main")]//text()')).strip()
			if k and v: rows[k] = v
		if "导演" in rows: vod["vod_director"] = self._names(rows["导演"])
		if "演员" in rows: vod["vod_actor"] = self._names(rows["演员"])
		if "首映" in rows:
			ym = re.search(r'(19|20)\d{2}', rows["首映"])
			if ym: vod["vod_year"] = ym.group(0)
		if "备注" in rows: vod["vod_remarks"] = rows["备注"]
		# detail-tags 形如 [年份, 地区, 类型...]
		tags = ["".join(a.xpath('.//text()')).strip() for a in tree.xpath('//a[contains(@class,"detail-tags-item")]')]
		tags = [t for t in tags if t]
		if tags:
			ym = re.search(r'(19|20)\d{2}', tags[0])
			if "vod_year" not in vod and ym: vod["vod_year"] = ym.group(0)
			if len(tags) > 1: vod["vod_area"] = tags[1]
			if len(tags) > 2: vod["vod_type"] = "/".join(tags[2:])
		lines = self._play_lines(tree)
		if not lines: return result
		# 只探测少量线路的首集;非直连线路仍保留给 App 手动切换,不放过多网络请求。
		if not self._playable(lines[0][1][0].split('$', 1)[1]):
			for i in range(1, min(len(lines), 8)):
				if self._playable(lines[i][1][0].split('$', 1)[1]):
					lines.insert(0, lines.pop(i))
					break
		vod["vod_play_from"] = "$$$".join(name for name, _ in lines)
		vod["vod_play_url"] = "$$$".join("#".join(eps) for _, eps in lines)
		result["list"].append(vod)
		return result

	def searchContent(self, key, quick, pg="1"):
		k = quote(key)
		items = []
		h = self._get(f"{self.host}/search?k={k}")
		m = re.search(r'name="t"\s+value="([^"]+)"', h or "")
		if m:
			url = f"{self.host}/search?k={k}&t={quote(m.group(1))}"
			if pg and pg != "1": url += f"&page={pg}"
			h2 = self._get(url)
			if h2:
				tree = self._html(h2)
				if tree is not None:
					for a in tree.xpath('//a[contains(@class,"search-result-item")]'):
						m2 = re.search(r'/detail/(\d+)\.html', a.get("href", ""))
						if not m2: continue
						name = "".join(a.xpath('.//*[contains(@class,"title")]//text()')).strip()
						if not name: continue
						pic = (a.xpath('.//img[not(contains(@data-original,"logo_placeholder"))]/@data-original') or [""])[0]
						items.append({"vod_id": m2.group(1), "vod_name": name, "vod_pic": self._pic(pic)})
		return {"list": items, "page": int(pg or 1)}

	def playerContent(self, flag, id, vipFlags):
		url = self._fix(id)
		play = ""
		html = self._get(url)
		if html:
			for pat in [r'playSource\s*=\s*\{[^}]*?src:\s*"([^"]+)"',
						r'(https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*)',
						r'(https?://[^\s"\'<>]+\.(?:mp4|flv|mkv|webm)[^\s"\'<>]*)']:
				m = re.search(pat, html)
				if m:
					play = m.group(1)
					break
		play = self._fix(play)
		if not play:
			return {"parse": 1, "url": url, "header": json.dumps(self.headers)}
		header = {"User-Agent": self.headers["User-Agent"]}
		header["Referer"] = self._referer(play)
		return {"parse": 0, "url": play, "header": json.dumps(header)}

	def isVideoFormat(self, url): return ".m3u8" in url or ".mp4" in url

	def manualVideoCheck(self): return False

	def localProxy(self, param): return None

	def destroy(self): return None
