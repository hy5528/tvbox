"""
@header({
  searchable: 1,
  filterable: 1,
  quickSearch: 1,
  title: '独播库',
  lang: 'hipy'
})
"""

# -*- coding: utf-8 -*-
# 本资源来源于互联网公开渠道，仅可用于个人学习爬虫技术。
# 严禁将其用于任何商业用途，下载后请于 24 小时内删除，搜索结果均来自源站，本人不承担任何责任。

from base.spider import Spider
import sys,time,json,base64,random,urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
sys.path.append('..')

class Spider(Spider):
    headers,host = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
        'Connection': 'Keep-Alive',
        'Accept-Encoding': 'gzip',
        'Referer': 'https://www.dbku.tv/'
    }, 'https://api.dbokutv.com'

    def init(self, extend=""):
        pass

    filters = {
        1: [
            {'key': 'area', 'name': '地区', 'value': [
                {'n': '全部', 'v': ''}, {'n': '大陆', 'v': '大陆'}, {'n': '香港', 'v': '香港'},
                {'n': '台湾', 'v': '台湾'}, {'n': '韩国', 'v': '韩国'}, {'n': '日本', 'v': '日本'},
                {'n': '欧美', 'v': '欧美'}, {'n': '泰国', 'v': '泰国'}]},
            {'key': 'order', 'name': '排序', 'value': [
                {'n': '时间', 'v': ''}, {'n': '人气', 'v': '人气'}, {'n': '评分', 'v': '评分'}]},
            {'key': 'class', 'name': '剧情', 'value': [
                {'n': '全部', 'v': ''}, {'n': '喜剧', 'v': '喜剧'}, {'n': '爱情', 'v': '爱情'},
                {'n': '动作', 'v': '动作'}, {'n': '科幻', 'v': '科幻'}, {'n': '悬疑', 'v': '悬疑'},
                {'n': '惊悚', 'v': '惊悚'}, {'n': '恐怖', 'v': '恐怖'}, {'n': '战争', 'v': '战争'},
                {'n': '犯罪', 'v': '犯罪'}, {'n': '纪录片', 'v': '纪录片'}, {'n': '剧情', 'v': '剧情'},
                {'n': '歌舞', 'v': '歌舞'}, {'n': '家庭', 'v': '家庭'}, {'n': '历史', 'v': '历史'},
                {'n': '奇幻', 'v': '奇幻'}, {'n': '冒险', 'v': '冒险'}, {'n': '传记', 'v': '传记'},
                {'n': '动画', 'v': '动画'}, {'n': '短片', 'v': '短片'}]},
            {'key': 'lang', 'name': '语言', 'value': [
                {'n': '全部', 'v': ''}, {'n': '国语', 'v': '国语'}, {'n': '粤语', 'v': '粤语'},
                {'n': '英语', 'v': '英语'}, {'n': '韩语', 'v': '韩语'}, {'n': '日语', 'v': '日语'},
                {'n': '泰语', 'v': '泰语'}]},
            {'key': 'year', 'name': '年份', 'value': [
                {'n': '全部', 'v': ''}, {'n': '2026', 'v': '2026'}, {'n': '2025', 'v': '2025'},
                {'n': '2024', 'v': '2024'}, {'n': '2023', 'v': '2023'}, {'n': '2022', 'v': '2022'},
                {'n': '2021', 'v': '2021'}, {'n': '2020', 'v': '2020'}, {'n': '更早', 'v': '更早'}]},
        ],
        2: [
            {'key': 'area', 'name': '地区', 'value': [
                {'n': '全部', 'v': ''}, {'n': '大陆', 'v': '大陆'}, {'n': '香港', 'v': '香港'},
                {'n': '台湾', 'v': '台湾'}, {'n': '韩国', 'v': '韩国'}, {'n': '日本', 'v': '日本'},
                {'n': '新加坡', 'v': '新加坡'}, {'n': '泰国', 'v': '泰国'}]},
            {'key': 'order', 'name': '排序', 'value': [
                {'n': '时间', 'v': ''}, {'n': '人气', 'v': '人气'}, {'n': '评分', 'v': '评分'}]},
            {'key': 'class', 'name': '剧情', 'value': [
                {'n': '全部', 'v': ''}, {'n': '悬疑', 'v': '悬疑'}, {'n': '武侠', 'v': '武侠'},
                {'n': '科幻', 'v': '科幻'}, {'n': '都市', 'v': '都市'}, {'n': '爱情', 'v': '爱情'},
                {'n': '古装', 'v': '古装'}, {'n': '战争', 'v': '战争'}, {'n': '青春', 'v': '青春'},
                {'n': '偶像', 'v': '偶像'}, {'n': '喜剧', 'v': '喜剧'}, {'n': '家庭', 'v': '家庭'},
                {'n': '奇幻', 'v': '奇幻'}, {'n': '剧情', 'v': '剧情'}, {'n': '乡村', 'v': '乡村'},
                {'n': '年代', 'v': '年代'}, {'n': '警匪', 'v': '警匪'}, {'n': '谍战', 'v': '谍战'},
                {'n': '历险', 'v': '历险'}, {'n': '罪案', 'v': '罪案'}, {'n': '宫廷', 'v': '宫廷'},
                {'n': '经典', 'v': '经典'}, {'n': '动作', 'v': '动作'}, {'n': '惊悚', 'v': '惊悚'},
                {'n': '历史', 'v': '历史'}, {'n': '穿越', 'v': '穿越'}, {'n': '同性', 'v': '同性'}]},
            {'key': 'lang', 'name': '语言', 'value': [
                {'n': '全部', 'v': ''}, {'n': '国语', 'v': '国语'}, {'n': '粤语', 'v': '粤语'},
                {'n': '韩语', 'v': '韩语'}, {'n': '泰语', 'v': '泰语'}, {'n': '日语', 'v': '日语'}]},
            {'key': 'year', 'name': '年份', 'value': [
                {'n': '全部', 'v': ''}, {'n': '2026', 'v': '2026'}, {'n': '2025', 'v': '2025'},
                {'n': '2024', 'v': '2024'}, {'n': '2023', 'v': '2023'}, {'n': '2022', 'v': '2022'},
                {'n': '2021', 'v': '2021'}, {'n': '2020', 'v': '2020'}, {'n': '更早', 'v': '更早'}]},
        ],
        3: [
            {'key': 'area', 'name': '地区', 'value': [
                {'n': '全部', 'v': ''}, {'n': '大陆', 'v': '大陆'}, {'n': '香港', 'v': '香港'},
                {'n': '台湾', 'v': '台湾'}, {'n': '韩国', 'v': '韩国'}, {'n': '日本', 'v': '日本'},
                {'n': '欧美', 'v': '欧美'}]},
            {'key': 'order', 'name': '排序', 'value': [
                {'n': '时间', 'v': ''}, {'n': '人气', 'v': '人气'}, {'n': '评分', 'v': '评分'}]},
            {'key': 'year', 'name': '年份', 'value': [
                {'n': '全部', 'v': ''}, {'n': '2026', 'v': '2026'}, {'n': '2025', 'v': '2025'},
                {'n': '2024', 'v': '2024'}, {'n': '2023', 'v': '2023'}, {'n': '2022', 'v': '2022'},
                {'n': '2021', 'v': '2021'}, {'n': '更早', 'v': '更早'}]},
        ],
        4: [
            {'key': 'area', 'name': '地区', 'value': [
                {'n': '全部', 'v': ''}, {'n': '大陆', 'v': '大陆'}, {'n': '日本', 'v': '日本'},
                {'n': '欧美', 'v': '欧美'}, {'n': '韩国', 'v': '韩国'}]},
            {'key': 'order', 'name': '排序', 'value': [
                {'n': '时间', 'v': ''}, {'n': '人气', 'v': '人气'}, {'n': '评分', 'v': '评分'}]},
            {'key': 'year', 'name': '年份', 'value': [
                {'n': '全部', 'v': ''}, {'n': '2026', 'v': '2026'}, {'n': '2025', 'v': '2025'},
                {'n': '2024', 'v': '2024'}, {'n': '2023', 'v': '2023'}, {'n': '2022', 'v': '2022'},
                {'n': '2021', 'v': '2021'}, {'n': '更早', 'v': '更早'}]},
        ],
    }

    def homeContent(self, filter):
        if not self.host: return None
        result = {'class': [
            {'type_id': 1, 'type_name': '电影'},
            {'type_id': 2, 'type_name': '连续剧'},
            {'type_id': 3, 'type_name': '综艺'},
            {'type_id': 4, 'type_name': '动漫'}]}
        if filter:
            result['filters'] = self.filters
        return result

    def homeVideoContent(self):
        response = self.fetch(self.sign(f'{self.host}/home'), headers=self.headers, verify=False).json()
        videos = []
        for i in response:
            for j in i.get('VodList',[]):
                videos.append({
                    'vod_id': self.decode(j.get('DId', j.get('DuId'))),
                    'vod_name': j['Name'],
                    'vod_pic': self.decode(j['TnId']),
                    'vod_remarks': j['Tag']
                })
        return {'list': videos}

    def categoryContent(self, tid, pg, filter, extend):
        area  = extend.get('area', '')
        order = extend.get('order', '')
        cls   = extend.get('class', '')
        lang  = extend.get('lang', '')
        year  = extend.get('year', '')
        pg_str = '' if str(pg) == '1' else str(pg)
        # URL格式: /vodshow/{tid}-{area}-{order}-{class}-{lang}-{letter}-{?}-{?}-{pg}-{?}-{year}
        path = f"{self.host}/vodshow/{tid}-{area}-{order}-{cls}-{lang}----{pg_str}---{year}"
        response = self.fetch(self.sign(path), headers=self.headers, verify=False).json()
        videos,pagecount = [], 0
        for i in response['VodList']:
            videos.append({
                'vod_id': self.decode(i.get('DId',i.get('DuId'))),
                'vod_name': i['Name'],
                'vod_pic': self.decode(i['TnId']),
                'vod_remarks': i['Tag']
            })
        try:
            for j in response['PaginationList']:
                if j['Type'] == 'StartEnd':
                    pgcount = int(self.decode(j.get('PId',j.get('PuId'))).split('-')[8])
                    if pgcount: pagecount = pgcount
        except Exception:
            pass
        if pagecount == 0:
            try:
                for j in response['PaginationList']:
                    if j['Type'] == 'ShortPage':
                        pgcount = int(j['Name'].split('/')[1])
                        if pgcount: pagecount = pgcount
            except Exception:
                pagecount = 1
        return {'list': videos,'pagecount': pagecount, 'page': pg}

    def searchContent(self, key, quick, pg='1'):
        response = self.fetch(f"{self.sign(f'{self.host}/vodsearch')}&wd={key}", headers=self.headers, verify=False).json()
        videos = []
        for i in response:
            videos.append({
                'vod_id': self.decode(i.get('DId', i.get('DuId'))),
                'vod_name': i['Name'],
                'vod_pic': self.decode(i['TnId']),
                'vod_remarks': i['Tag'],
                'vod_actor': i['Actor'],
                'vod_score': i['Rating']
            })
        return {'list': videos, 'page': pg}

    def detailContent(self, ids):
        data = self.fetch(self.sign(f"{self.host}{ids[0]}"), headers=self.headers, verify=False).json()
        play_urls = [f"{i['EpisodeName']}${self.decode(i['VId'])}" for i in data['Playlist']]
        video = {
            'vod_id': ids[0],
            'vod_name': data['Name'],
            'vod_pic': self.decode(data['TnId']),
            'vod_remarks': f"评分：{data['Rating']}",
            'vod_year': data['ReleaseYear'],
            'vod_area': data['Region'],
            'vod_actor': ','.join(data['Actor']),
            'vod_director': data['Director'],
            'vod_content': data['Description'],
            'vod_play_from': '独播库',
            'vod_play_url': '#'.join(play_urls),
            'type_name': f"{data['Genre']},{data['Scenario']},{data['Language']}"
        }
        return {'list': [video]}

    def playerContent(self, flag, video_id, vip_flags):
        res = self.fetch(self.sign(f"{self.host}{video_id}"), headers=self.headers, verify=False).json()
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            'Accept-Encoding': 'gzip, deflate',
            'origin': 'https://w.duboku.io',
            'referer': 'https://w.duboku.io/',
            'priority': 'u=1, i'
        }
        return { 'jx': 0, 'parse': 0, 'url': self.decode(res['HId']), 'header': headers}

    def decode(self, data):
        if not data or not isinstance(data, str): return ''
        stripped_str = data.strip('\'"')
        if not stripped_str: return ''
        segment_length = 10
        try:
            reversed_segments = (stripped_str[i:i + segment_length][::-1] for i in range(0, len(stripped_str), segment_length))
            processed_base64 = ''.join(reversed_segments).replace('.', '=')
        except Exception:
            return ''
        try:
            padding_needed = 4 - len(processed_base64) % 4
            if padding_needed != 4:
                processed_base64 += '=' * padding_needed
            decoded_bytes = base64.b64decode(processed_base64, validate=True)
            return decoded_bytes.decode('utf-8')
        except Exception:
            return ''

    def sign(self,raw):
        random.seed(int(time.time()))
        random_number = random.randint(0, 800000000)
        value_a = random_number + 100000000
        value_b = 900000000 - random_number
        current_unix_timestamp = int(time.time())
        unix_timestamp_str = str(current_unix_timestamp)
        interleaved_str = self.interleave_strings(f'{value_a}{value_b}', unix_timestamp_str)
        ssid_base64_encoded = base64.b64encode(interleaved_str.encode()).decode().replace('=', '.')
        random_sign = self.random_string(60)
        random_token = self.random_string(38)
        return f"{raw}?sign={random_sign}&token={random_token}&ssid={ssid_base64_encoded}"

    def interleave_strings(self,first_str, second_str):
        interleaved_chars = []
        min_length = min(len(first_str), len(second_str))
        for i in range(min_length):
            interleaved_chars.append(first_str[i])
            interleaved_chars.append(second_str[i])
        interleaved_chars.append(first_str[min_length:])
        interleaved_chars.append(second_str[min_length:])
        return ''.join(interleaved_chars)


    def random_string(self, length):
        character = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
        random.seed(int(time.time()) + len(character))
        return ''.join(random.choice(character) for _ in range(length))

    def getName(self):
        pass

    def isVideoFormat(self, url):
        pass

    def manualVideoCheck(self):
        pass

    def destroy(self):
        pass

    def localProxy(self, param):
        pass
