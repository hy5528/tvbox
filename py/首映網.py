# -*- coding: utf-8 -*-
import requests
import re
import urllib.parse

class Spider:
    def __init__(self):
        self.host = 'https://www.yingbas.com'
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        self.type_map = {
            '1': '电影', '2': '电视剧', '3': '动漫',
            '4': '综艺', '29': '短剧'
        }
    
    def getDependence(self):
        return []
    
    def init(self, extend=""):
        return {}
    
    def getName(self):
        return "首映网"
    
    def homeContent(self, filter):
        try:
            classes = [{'type_id': tid, 'type_name': name} for tid, name in self.type_map.items()]
            r = requests.get(self.host, headers=self.headers, timeout=10)
            r.encoding = 'utf-8'
            
            videos = []
            items = re.findall(r'<a class="stui-vodlist__thumb lazyload" href="/yingba/(\d+)\.html" title="([^"]+)" data-original="([^"]+)"', r.text)
            
            seen = set()
            for vod_id, title, pic in items:
                if vod_id not in seen and len(videos) < 20:
                    seen.add(vod_id)
                    remark = ''
                    remark_match = re.search(r'<span class="pic-text text-right">([^<]+)</span>', r.text[r.text.find(vod_id):r.text.find(vod_id)+200])
                    if remark_match:
                        remark = remark_match.group(1)
                    
                    videos.append({
                        'vod_id': vod_id,
                        'vod_name': title,
                        'vod_pic': pic,
                        'vod_remarks': remark
                    })
            
            return {'class': classes, 'list': videos}
        except:
            return {'class': [], 'list': []}
    
    def homeVideoContent(self):
        result = self.homeContent(True)
        return {'list': result.get('list', [])}
    
    def categoryContent(self, tid, pg, filter, extend):
        try:
            if pg == 1:
                url = f'{self.host}/fenlei/{tid}.html'
            else:
                url = f'{self.host}/class/{tid}--------{pg}---.html'
            
            r = requests.get(url, headers=self.headers, timeout=10)
            r.encoding = 'utf-8'
            
            videos = []
            items = re.findall(r'<a class="stui-vodlist__thumb lazyload" href="/yingba/(\d+)\.html" title="([^"]+)" data-original="([^"]+)"', r.text)
            
            seen = set()
            for vod_id, title, pic in items:
                if vod_id in seen:
                    continue
                seen.add(vod_id)
                
                remark = ''
                remark_match = re.search(r'<span class="pic-text text-right">([^<]+)</span>', r.text[r.text.find(vod_id):r.text.find(vod_id)+200])
                if remark_match:
                    remark = remark_match.group(1)
                
                videos.append({
                    'vod_id': vod_id,
                    'vod_name': title,
                    'vod_pic': pic,
                    'vod_remarks': remark
                })
            
            # 获取总页数
            pagecount = 1
            page_match = re.search(r'<li class="active num"><a>(\d+)/(\d+)</a></li>', r.text)
            if page_match:
                pagecount = int(page_match.group(2))
            
            return {
                'list': videos,
                'page': pg,
                'pagecount': pagecount,
                'limit': 20,
                'total': len(videos)
            }
        except:
            return {'list': [], 'page': pg, 'pagecount': 1, 'limit': 20, 'total': 0}
    
    def detailContent(self, ids):
        try:
            url = f'{self.host}/yingba/{ids[0]}.html'
            r = requests.get(url, headers=self.headers, timeout=10)
            r.encoding = 'utf-8'
            
            # 提取标题
            title = ''
            title_match = re.search(r'<h1[^>]*>([^<]+)</h1>', r.text)
            if title_match:
                title = title_match.group(1)
            
            # 提取海报
            pic = ''
            pic_match = re.search(r'data-original="([^"]+)"', r.text)
            if pic_match:
                pic = pic_match.group(1)
            
            # 提取简介
            desc = ''
            desc_match = re.search(r'剧情[：:]([^<]+)', r.text)
            if desc_match:
                desc = desc_match.group(1).strip()
            
            # 提取导演
            director = ''
            director_match = re.search(r'导演[：:]([^<]+)', r.text)
            if director_match:
                director = director_match.group(1).strip()
            
            # 提取演员
            actor = ''
            actor_match = re.search(r'主演[：:]([^<]+)', r.text)
            if actor_match:
                actor = actor_match.group(1).strip()
            
            # 提取年份
            year = ''
            year_match = re.search(r'年份[：:]([^<]+)', r.text)
            if year_match:
                year = year_match.group(1).strip()
            
            # 提取地区
            area = ''
            area_match = re.search(r'地区[：:]([^<]+)', r.text)
            if area_match:
                area = area_match.group(1).strip()
            
            # 提取类型
            type_name = ''
            type_match = re.search(r'类型[：:]([^<]+)', r.text)
            if type_match:
                type_name = type_match.group(1).strip()
            
            # 提取播放列表（多线路）
            play_from = []
            play_url = []
            
            # 查找所有播放源
            source_blocks = re.findall(r'<div class="stui-vodlist__head">.*?<span class="pull-right1">([^<]+)</span>.*?<ul class="stui-content__playlist clearfix">(.*?)</ul>', r.text, re.S)
            
            for source_name, episode_html in source_blocks:
                play_from.append(source_name)
                
                # 提取该线路的剧集
                episodes = []
                episode_links = re.findall(r'<a href="(/bofang/\d+-\d+-\d+\.html)">([^<]+)</a>', episode_html)
                for href, name in episode_links:
                    episodes.append(f"{name}${self.host}{href}")
                
                play_url.append('#'.join(episodes))
            
            vod = {
                'vod_id': ids[0],
                'vod_name': title,
                'vod_pic': pic,
                'vod_content': desc,
                'vod_actor': actor,
                'vod_director': director,
                'vod_year': year,
                'vod_area': area,
                'type_name': type_name,
                'vod_play_from': '$$$'.join(play_from),
                'vod_play_url': '$$$'.join(play_url)
            }
            return {'list': [vod]}
        except:
            return {'list': []}
    
    def searchContent(self, key, quick, pg=1):
        try:
            encoded_key = urllib.parse.quote(key)
            url = f"{self.host}/sousuo/{encoded_key}----------{pg}---.html"
            
            r = requests.get(url, headers=self.headers, timeout=10)
            r.encoding = 'utf-8'
            
            videos = []
            items = re.findall(r'<a class="stui-vodlist__thumb lazyload" href="/yingba/(\d+)\.html" title="([^"]+)" data-original="([^"]+)"', r.text)
            
            seen = set()
            for vod_id, title, pic in items:
                if vod_id in seen:
                    continue
                seen.add(vod_id)
                
                remark = ''
                remark_match = re.search(r'<span class="pic-text text-right">([^<]+)</span>', r.text[r.text.find(vod_id):r.text.find(vod_id)+200])
                if remark_match:
                    remark = remark_match.group(1)
                
                videos.append({
                    'vod_id': vod_id,
                    'vod_name': title,
                    'vod_pic': pic,
                    'vod_remarks': remark
                })
            
            # 获取搜索结果总页数
            pagecount = 1
            page_match = re.search(r'<li class="active num"><a>(\d+)/(\d+)</a></li>', r.text)
            if page_match:
                pagecount = int(page_match.group(2))
            
            return {
                'list': videos,
                'page': pg,
                'pagecount': pagecount,
                'limit': 20,
                'total': len(videos)
            }
        except:
            return {'list': [], 'page': pg, 'pagecount': 1, 'limit': 20, 'total': 0}
    
    def playerContent(self, flag, id, vipFlags):
        try:
            # 构建播放页URL
            if id.startswith('http'):
                play_url = id
            else:
                play_url = f'{self.host}{id}'
            
            # 获取播放页面
            r = requests.get(play_url, headers=self.headers, timeout=10)
            r.encoding = 'utf-8'
            
            # 方法1: 查找 player_data 变量
            player_data_match = re.search(r'var player_data=({.*?});', r.text, re.S)
            if player_data_match:
                player_data = player_data_match.group(1)
                # 提取 url 字段
                url_match = re.search(r'"url":"([^"]+)"', player_data)
                if url_match:
                    video_url = url_match.group(1).replace('\\/', '/')
                    return {'parse': 0, 'playUrl': '', 'url': video_url}
            
            # 方法2: 查找直接的视频链接
            video_match = re.search(r'(https?://[^"\']+\.m3u8[^"\']*)', r.text)
            if video_match:
                video_url = video_match.group(1)
                return {'parse': 0, 'playUrl': '', 'url': video_url}
            
            # 方法3: 查找 mp4 链接
            mp4_match = re.search(r'(https?://[^"\']+\.mp4[^"\']*)', r.text)
            if mp4_match:
                video_url = mp4_match.group(1)
                return {'parse': 0, 'playUrl': '', 'url': video_url}
            
            # 方法4: 查找 iframe
            iframe_match = re.search(r'<iframe[^>]+src="([^"]+)"', r.text)
            if iframe_match:
                iframe_url = iframe_match.group(1)
                if not iframe_url.startswith('http'):
                    iframe_url = self.host + iframe_url
                return {'parse': 1, 'playUrl': '', 'url': iframe_url}
            
            return {'parse': 0, 'playUrl': '', 'url': play_url}
        except:
            return {'parse': 0, 'playUrl': '', 'url': id}
    
    def isVideoFormat(self, url):
        video_formats = ['.mp4', '.m3u8', '.flv', '.mkv', '.avi', '.mov', '.wmv']
        return any(fmt in url.lower() for fmt in video_formats)
    
    def localProxy(self, params):
        return []