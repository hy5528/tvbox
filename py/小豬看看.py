# coding=utf-8
import sys
import os
import re
import json
import urllib.parse
from bs4 import BeautifulSoup

try:
    from base.spider import Spider
except ImportError:
    class Spider:
        def fetch(self, url, headers=None):
            import requests
            return requests.get(url, headers=headers, timeout=15)
        def getDependence(self):
            return ["bs4"]

class Spider(Spider):
    def getName(self):
        return "小豬看看"
    
    def init(self, extend=""):
        self.host = "https://xiaozhukankan.com"
    
    def getDependence(self):
        return ["bs4"]
    
    def header(self):
        return {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": self.host,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }
    
    def build_full_url(self, url):
        if not url or not isinstance(url, str):
            return ""
        url = url.strip()
        if url.startswith("http://") or url.startswith("https://"):
            return url
        if not url or url in ["null", "undefined", ""]:
            return ""
        if url.startswith("//"):
            return "https:" + url
        if url.startswith("/"):
            return self.host + url
        return self.host + "/" + url
    
    def extract_pic(self, element):
        pic = ""
        if hasattr(element, "find"):
            img = element.find("img")
            if img:
                pic = img.get("data-src", "") or img.get("data-original", "") or img.get("src", "")
        if not pic:
            pic = element.get("data-src", "") or element.get("data-original", "")
        if not pic:
            pic = element.get("src", "")
        if not pic and hasattr(element, "get"):
            style = element.get("style", "")
            match = re.search(r"url\(['\"]?(.*?)['\"]?\)", style)
            if match:
                pic = match.group(1)
        return self.build_full_url(pic) if pic else ""
    
    def parse_video_items(self, soup):
        videos = []
        items = soup.select(".w4-item")
        for item in items:
            link = item if item.name == "a" else item.find("a")
            if not link or not link.get("href"):
                continue
            href = link.get("href", "")
            if not href or not href.startswith("/v/"):
                continue
            vod_id = href.replace("/v/", "").replace(".html", "")
            title = link.get("title", "")
            if not title:
                title_el = link.select_one(".t")
                if title_el:
                    title = title_el.text.strip()
            if not title:
                img = link.find("img")
                if img and img.get("alt"):
                    title = img.get("alt")
            pic = self.extract_pic(link)
            remark = ""
            remark_el = link.select_one(".i")
            if remark_el:
                remark = remark_el.text.strip()
            if title:
                videos.append({"vod_id": vod_id, "vod_name": title, "vod_pic": pic, "vod_remarks": remark})
        return videos
    
    def homeContent(self, filter):
        classes = [
            {"type_id": "10", "type_name": "電影"},
            {"type_id": "11", "type_name": "連續劇"},
            {"type_id": "12", "type_name": "綜藝"},
            {"type_id": "13", "type_name": "動漫"},
        ]
        filters = {
            "10": [{"key": "tid", "name": "類型", "value": [{"n": "全部電影", "v": "10"},{"n": "動作片", "v": "1001"},{"n": "喜劇片", "v": "1002"},{"n": "愛情片", "v": "1003"},{"n": "科幻片", "v": "1004"},{"n": "恐怖片", "v": "1005"},{"n": "劇情片", "v": "1006"},{"n": "戰爭片", "v": "1007"},{"n": "紀錄片", "v": "1008"},{"n": "動漫電影", "v": "1010"},{"n": "奇幻片", "v": "1011"},{"n": "動畫片", "v": "1013"},{"n": "犯罪片", "v": "1014"},{"n": "懸疑片", "v": "1016"},{"n": "邵氏電影", "v": "1019"},{"n": "歌舞片", "v": "1022"},{"n": "家庭片", "v": "1024"},{"n": "古裝片", "v": "1025"},{"n": "曆史片", "v": "1026"},{"n": "4K電影", "v": "1027"}]}],
            "11": [{"key": "tid", "name": "類型", "value": [{"n": "全部連續劇", "v": "11"},{"n": "國產劇", "v": "1101"},{"n": "香港劇", "v": "1102"},{"n": "台灣劇", "v": "1105"},{"n": "韓國劇", "v": "1103"},{"n": "歐美劇", "v": "1104"},{"n": "日本劇", "v": "1106"},{"n": "泰國劇", "v": "1108"},{"n": "港台劇", "v": "1110"},{"n": "日韓劇", "v": "1111"},{"n": "海外劇", "v": "1107"}]}],
            "12": [{"key": "tid", "name": "類型", "value": [{"n": "全部綜藝", "v": "12"},{"n": "內地綜藝", "v": "1201"},{"n": "港台綜藝", "v": "1202"},{"n": "日韓綜藝", "v": "1203"},{"n": "歐美綜藝", "v": "1204"},{"n": "國外綜藝", "v": "1205"}]}],
            "13": [{"key": "tid", "name": "類型", "value": [{"n": "全部動漫", "v": "13"},{"n": "國產動漫", "v": "1301"},{"n": "日韓動漫", "v": "1302"},{"n": "歐美動漫", "v": "1303"},{"n": "海外動漫", "v": "1305"},{"n": "裏番", "v": "1307"}]}],
        }
        try:
            rsp = self.fetch(self.host, headers=self.header())
            soup = BeautifulSoup(rsp.text, "html.parser")
            videos = self.parse_video_items(soup)
            seen = set()
            unique = []
            for v in videos:
                if v["vod_id"] not in seen:
                    seen.add(v["vod_id"])
                    unique.append(v)
            return {"class": classes, "list": unique[:20], "filters": filters}
        except Exception as e:
            print(f"homeContent error: {e}")
            return {"class": classes, "list": [], "filters": filters}
    
    def homeVideoContent(self):
        return self.homeContent(False)
    
    def categoryContent(self, tid, pg, filter, extend):
        try:
            actual_tid = tid
            if extend and isinstance(extend, dict) and "tid" in extend:
                actual_tid = extend["tid"]
            if pg == 1:
                url = f"{self.host}/t/{actual_tid}.html"
            else:
                url = f"{self.host}/t/{actual_tid}/p{pg}.html"
            rsp = self.fetch(url, headers=self.header())
            soup = BeautifulSoup(rsp.text, "html.parser")
            videos = self.parse_video_items(soup)
            max_page = 1
            page_links = soup.select(".w4-page .pager a, .w4-page .next a")
            for a in page_links:
                href = a.get("href", "")
                match = re.search(r"/p(\d+)\.html", href)
                if match:
                    p = int(match.group(1))
                    if p > max_page:
                        max_page = p
            return {"list": videos, "pagecount": max_page, "page": pg, "limit": len(videos)}
        except Exception as e:
            print(f"categoryContent error: {e}")
            return {"list": [], "pagecount": 1, "page": pg, "limit": 0}
    
    def detailContent(self, ids):
        try:
            if isinstance(ids, list):
                vid = ids[0]
            else:
                vid = ids
            url = f"{self.host}/v/{vid}.html"
            rsp = self.fetch(url, headers=self.header())
            html = rsp.text
            soup = BeautifulSoup(html, "html.parser")
            vod = {"vod_id": vid, "vod_name": "", "vod_pic": "", "vod_actor": "", "vod_director": "", "vod_content": "", "vod_area": "", "vod_year": "", "vod_remarks": "", "vod_play_from": "", "vod_play_url": ""}
            title_tag = soup.find("h1")
            if title_tag:
                vod["vod_name"] = title_tag.text.strip()
            else:
                bread = soup.select(".w4-bread li:last-child")
                if bread:
                    vod["vod_name"] = bread[0].text.strip()
            pic = soup.find("meta", property="og:image")
            if pic and pic.get("content"):
                vod["vod_pic"] = self.build_full_url(pic.get("content"))
            if not vod["vod_pic"]:
                player = soup.select_one(".w4-player img")
                if player:
                    vod["vod_pic"] = self.extract_pic(player)
            desc = soup.find("meta", property="og:description")
            if desc and desc.get("content"):
                vod["vod_content"] = desc.get("content")
            play_froms = []
            play_urls = []
            pp_match = re.search(r'var pp=(\{.*?\});', html, re.DOTALL)
            if pp_match:
                try:
                    pp_data = json.loads(pp_match.group(1))
                    la = pp_data.get("la", [])
                    for item in la:
                        if len(item) >= 5:
                            line_name = item[1]
                            base_url = item[4]
                            if base_url:
                                ep_count = 1
                                if len(item) >= 3 and isinstance(item[2], int):
                                    ep_count = item[2]
                                episodes = []
                                for i in range(1, ep_count + 1):
                                    ep_name = f"第{i:02d}集"
                                    ep_url = base_url.replace("第01集", f"第{i:02d}集")
                                    episodes.append(f"{ep_name}${ep_url}")
                                if episodes:
                                    play_froms.append(line_name)
                                    play_urls.append("#".join(episodes))
                except:
                    pass
            if not play_urls:
                awp = soup.select_one("#awp1")
                current_play_url = awp.get("data-src") if awp else ""
                ep_links = soup.select(".w4-episode-list .w a")
                if ep_links and current_play_url:
                    episodes = []
                    for a in ep_links:
                        ep_name = a.text.strip() or "播放"
                        href = a.get("href", "")
                        if href:
                            ep_url = self.build_full_url(href)
                            episodes.append(f"{ep_name}${ep_url}")
                    if episodes:
                        play_froms.append("线路1")
                        play_urls.append("#".join(episodes))
            if not play_urls:
                awp = soup.select_one("#awp1")
                if awp and awp.get("data-src"):
                    play_froms.append("线路1")
                    play_urls.append(f"播放${awp.get('data-src')}")
            vod["vod_play_from"] = "$$$".join(play_froms) if play_froms else ""
            vod["vod_play_url"] = "$$$".join(play_urls) if play_urls else ""
            return {"list": [vod]}
        except Exception as e:
            print(f"detailContent error: {e}")
            return {"list": []}
    
    def searchContent(self, key, quick, pg=1):
        try:
            import urllib.parse
            encoded_key = urllib.parse.quote(key)
            if pg == 1:
                search_url = f"{self.host}/s/{encoded_key}.html"
            else:
                search_url = f"{self.host}/s/{encoded_key}/p{pg}.html"
            rsp = self.fetch(search_url, headers=self.header())
            soup = BeautifulSoup(rsp.text, "html.parser")
            videos = self.parse_video_items(soup)
            return {"list": videos, "pagecount": 1, "page": pg, "limit": len(videos)}
        except Exception as e:
            print(f"searchContent error: {e}")
            return {"list": [], "pagecount": 1, "page": pg, "limit": 0}
    
    def playerContent(self, flag, id, vipFlags):
        try:
            if id and (".m3u8" in id or ".mp4" in id):
                return {"parse": 0, "url": id, "header": json.dumps(self.header())}
            play_url = self.build_full_url(id)
            rsp = self.fetch(play_url, headers=self.header())
            soup = BeautifulSoup(rsp.text, "html.parser")
            awp = soup.select_one("#awp1")
            if awp and awp.get("data-src"):
                return {"parse": 0, "url": awp.get("data-src"), "header": json.dumps(self.header())}
            return {"parse": 1, "url": play_url, "header": json.dumps(self.header())}
        except Exception as e:
            print(f"playerContent error: {e}")
            return {"parse": 1, "url": id, "header": json.dumps(self.header())}
    
    def isVideoFormat(self, url):
        if not url:
            return False
        video_exts = [".mp4", ".m3u8", ".flv"]
        return any(ext in url.lower() for ext in video_exts)
    
    def manualVideoCheck(self):
        pass
    
    def destroy(self):
        pass
