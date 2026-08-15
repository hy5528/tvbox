#!/usr/bin/python3
# -*- coding: utf-8 -*-
# @Author  : Doubebly
# @Time    : 2025/12/05 07:05
# @file    : 高清电影


from pyquery import PyQuery
import requests
import sys

sys.path.append('..')
from base.spider import Spider as BaseSpider


class Spider(BaseSpider):
    def __init__(self):
        super(Spider, self).__init__()
        self.debug = True
        self.baseUrl = "https://www.gaoqing888.com"
        self.siteUrl = self.baseUrl
        self.name = '高清电影',
        self.headers = {
            'User-Agent': "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36",
            'Referer': self.baseUrl + '/',
            'X-Requested-With': 'XMLHttpRequest',
        }

    def getName(self):
        return self.name

    def init(self, extend=""):
        pass

    def homeContent(self, filter):
        return {
            'class': [
                {'type_id': '1', 'type_name': '每日更新'},
                {'type_id': '2', 'type_name': '选电影'},
            ],
            'filters': {},
        }

    def homeVideoContent(self):
        return {'list': [], 'parse': 0, 'jx': 0}

    def categoryContent(self, tid, page, filter, extend):
        result = {'list': [], 'parse': 0, 'jx': 0}
        doc = None
        if tid == "1":
            url = f"{self.baseUrl}/?page={page}"
            try:
                headers = self.headers.copy()
                headers['Accept'] = 'application/json, text/javascript, */*; q=0.01'
                response = requests.get(url, headers=headers)
                ii = response.json()['content']
                doc = PyQuery(ii)
            except Exception as e:
                print(e)
        elif tid == "2":
            url = f"{self.baseUrl}/movie?sort=recommend&page={page}"
            try:
                headers = self.headers.copy()
                headers['Accept'] = 'text/html, */*; q=0.01'
                response = requests.get(url, headers=headers)
                doc = PyQuery(response.text)
            except Exception as e:
                print(e)
        if doc:
            for i in doc('a.video-item').items():
                result['list'].append({
                    "vod_id": i('a').attr('href').split("/")[-2],
                    "vod_name": i('img').attr('alt'),
                    "vod_pic": self.getProxyUrl() + '&img_url=' + i('img').attr('src'),
                    "vod_remarks": "评分:" + i('p strong').text(),
                })
        return result

    def detailContent(self, did):
        return_data = {'list': [], 'parse': 0, 'jx': 0}
        ids = did[0]
        url = self.baseUrl + f'/{ids}/detail'
        try:
            response = requests.get(url, headers=self.headers)
            doc = PyQuery(response.text)

            d = {
                'type_name': doc('div.info ul.list-unstyled li').eq(3).text().replace('\xa0', ''),
                'vod_id': ids,
                'vod_name': doc('div.info ul.list-unstyled li').eq(7).text().replace('\xa0', ''),
                'vod_remarks': doc('div.info ul.list-unstyled li').eq(6).text().replace('\xa0', ''),
                'vod_year': doc('div.info ul.list-unstyled li').eq(5).text().replace('\xa0', ''),
                'vod_area': doc('div.info ul.list-unstyled li').eq(4).text().replace('\xa0', ''),
                'vod_actor': doc('div.info ul.list-unstyled li').eq(2).text().replace('\xa0', ''),
                'vod_director': doc('div.info ul.list-unstyled li').eq(0).text().replace('\xa0', ''),
                'vod_content': doc('div.video-detail > p').text(),
                'vod_play_from': '',
                'vod_play_url': ''

            }
            d_from = ['原盘', '1080P', '720P', '标准', '未知']
            d['vod_play_from'] = '$$$'.join(d_from)
            d_url = ['download-list-blue-ray', 'download-list-1080p', 'download-list-720p', 'download-list-standard',
                     'download-list-unknown']
            d1 = []
            for i1 in d_url:
                d2 = []
                for i in doc(f'#{i1} ul li').items():
                    if bool(len(i('h6'))):
                        name = i('h6').text()
                        url = i('a').attr('href')
                        a = i('div.extra span').eq(1).text()
                        b = i('div.extra span').eq(3).text()
                        tag = f'[大小:{a} 清晰度:{b}]'
                        d2.append(f'{tag}{name}${url}')
                    else:
                        d2.append(
                            '呀，暂时还没有资源!$https://kjjsaas-sh.oss-cn-shanghai.aliyuncs.com/u/3401405881/20240818-936952-fc31b16575e80a7562cdb1f81a39c6b0.mp4')
                    # print(i)
                d1.append('#'.join(d2))
            d['vod_play_url'] = '$$$'.join(d1)
            return_data['list'].append(d)
        except Exception as e:
            print(e)

        return return_data

    def searchContent(self, key, quick, pg='1'):
        return_data = {'list': [], 'parse': 0, 'jx': 0}
        url = self.baseUrl + f'/search?kw={key}'
        if pg == '1':
            response = requests.get(url, headers=self.headers)
            doc = PyQuery(response.text)

            for i in doc('div.search-list div.video-row').items():
                return_data['list'].append({
                    "vod_id": i('a').attr('href').split("/")[-2],
                    "vod_name": i('img').attr('alt'),
                    "vod_pic": self.getProxyUrl() + '&img_url=' + i('img').attr('src'),
                    "vod_remarks": "评分:" + i('span.rate-num').text(),
                })
        return return_data

    def playerContent(self, flag, pid, vipFlags):
        return {'url': pid, 'parse': 0, 'jx': 0, "header": {}}

    def localProxy(self, params):
        img_url = params['img_url']
        return [200, 'application/octet-stream', self.proxy_img(img_url)]

    def proxy_img(self, url):
        try:
            response = requests.get(url, headers=self.headers)
            return response.content
        except Exception as e:
            print(e)
        return b''


if __name__ == '__main__':
    # sp = Spider()
    # sp.init()
    # print(sp.categoryContent('home','2','',''))
    # sp.detailContent(['27568'])
    # print(sp.searchContent('变形金刚','','1'))
    pass
