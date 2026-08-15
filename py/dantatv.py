# -*- coding: utf-8 -*-
"""
tvbox 插件 - 蛋挞TV（兼容基类修正版）
站点: https://www.dantatv.cc
"""
import json
import sys
from base64 import b64encode, b64decode

sys.path.append('..')
from base.spider import Spider


class Spider(Spider):

    def init(self, extend=""):
        self.host = "https://www.dantatv.cc"
        pass

    def getName(self):
        return "蛋挞TV"

    def isVideoFormat(self, url):
        pass

    def manualVideoCheck(self):
        pass

    def localProxy(self, param):
        pass

    def destroy(self):
        pass

    def fetch(self, url, params=None, cookies=None, headers=None, timeout=5, verify=False, stream=False, allow_redirects=True):
        import requests as _r
        import urllib3 as _u
        _u.disable_warnings()
        rsp = _r.get(url, params=params, cookies=cookies, headers=headers, timeout=timeout, verify=verify, stream=stream, allow_redirects=allow_redirects)
        rsp.encoding = 'utf-8'
        return rsp

    def post(self, url, params=None, data=None, json=None, cookies=None, headers=None, timeout=5, verify=False, stream=False, allow_redirects=True):
        import requests as _r
        import urllib3 as _u
        _u.disable_warnings()
        rsp = _r.post(url, params=params, data=data, json=json, headers=headers, timeout=timeout, verify=verify, stream=stream, allow_redirects=allow_redirects)
        rsp.encoding = 'utf-8'
        return rsp

    # ---------- 辅助函数 ----------
    def getheader(self, content_type=None):
        headers = {
            'Unique-Origin': 'B9A378A8C39BDA1277D2D6185FCE2695',
            'User-Agent': 'okhttp/4.1.0/luob.app',
            'Connection': 'Keep-Alive',
            'Accept-Encoding': 'gzip',
        }
        if content_type:
            headers['Content-Type'] = content_type
        return headers

    def e64(self, text):
        try:
            text_bytes = text.encode('utf-8')
            encoded_bytes = b64encode(text_bytes)
            return encoded_bytes.decode('utf-8')
        except Exception as e:
            print(f"Base64编码错误: {str(e)}")
            return ""

    def d64(self, encoded_text):
        try:
            encoded_bytes = encoded_text.encode('utf-8')
            decoded_bytes = b64decode(encoded_bytes)
            return decoded_bytes.decode('utf-8')
        except Exception as e:
            print(f"Base64解码错误: {str(e)}")
            return ""

    # ---------- 首页（固定分类） ----------
    def homeContent(self, filter):
        classes = [
            {"type_name": "剧集","type_id": "1"},
            {"type_name": "电影","type_id": "2"},
            {"type_name": "动漫","type_id": "3"},
            {"type_name": "短剧","type_id": "4"},
            {"type_name": "综艺","type_id": "5"},
            {"type_name": "少儿", "type_id": "30"},
        ]
        return {"class": classes, "filters": {}}

    # ---------- 首页推荐视频 ----------
    def homeVideoContent(self):
        url = f"{self.host}/api/index"
        headers = self.getheader()
        try:
            resp = self.fetch(url, headers=headers)
            data = resp.json()
            vod_list = []
            seen = set()
            for group in data.get('data', []) or []:
                for item in group.get('vodList', []) or []:
                    vid = str(item.get('vodId', ''))
                    if not vid or vid in seen:
                        continue
                    seen.add(vid)
                    vod_list.append(self._vod_to_common(item))
        except Exception as e:
            print(f"首页推荐请求失败: {e}")
            vod_list = []
        return {'list': vod_list}

    # ---------- 分类页（POST请求改用 self.post） ----------
    def categoryContent(self, tid, pg, filter, extend=None):
        if extend is None:
            extend = {}
        body = {
            "typeId1": int(tid),
            "pageNum": int(pg),
            "pageSize": 12,
            "sortField": "vod_time",
            "vodClass": extend.get('class', ''),
            "vodArea": extend.get('area', ''),
            "vodYear": extend.get('year', '')
        }
        url = f"{self.host}/api/search/type"
        headers = self.getheader(content_type='application/json')
        try:
            # 使用基类的 post 方法（若基类无 post，可改为 requests.post 自行实现）
            resp = self.post(url, headers=headers, data=json.dumps(body).encode('utf-8'))
            data = resp.json()
            vod_list = [self._vod_to_common(item) for item in data.get('data', [])]
        except Exception as e:
            print(f"分类页请求失败: {e}")
            vod_list = []
        return {
            'list': vod_list,
            'page': pg,
            'pagecount': 9999,
            'limit': 12,
            'total': 999999
        }

    # ---------- 详情页 ----------
    def detailContent(self, ids):
        vod_id = ids[0]
        url = f"{self.host}/api/vod/play?vodId={vod_id}"
        headers = self.getheader()
        try:
            resp = self.fetch(url, headers=headers)
            data = resp.json()
            vod = data.get('data', {}).get('dantaVod', {})
        except Exception as e:
            print(f"详情请求失败: {e}")
            return {'list': []}

        if not vod:
            return {'list': []}

        info = {
            'vod_id': vod.get('vodId'),
            'vod_name': vod.get('vodName'),
            'vod_pic': self._fix_pic(vod.get('vodPic')),
            'vod_actor': vod.get('vodActor'),
            'vod_director': vod.get('vodDirector'),
            'vod_blurb': vod.get('vodContent') or vod.get('vodBlurb'),
            'vod_area': vod.get('vodArea'),
            'vod_year': vod.get('vodYear'),
            'vod_remarks': vod.get('vodRemarks'),
            'vod_lang': vod.get('vodLang'),
            'vod_class': vod.get('vodClass'),
        }

        sources = vod.get('sources', [])
        vod_play_from = []
        vod_play_url = []
        for idx, src in enumerate(sources):
            collect_id = src.get('collectId')
            raw_url = src.get('vodPlayUrl', '')
            if not raw_url:
                continue

            items = raw_url.split('#')
            encoded_items = []
            for part in items:
                if '$' not in part:
                    continue
                name, link = part.split('$', 1)
                payload = {"collectId": collect_id, "url": link}
                enc = self.e64(json.dumps(payload, ensure_ascii=False))
                encoded_items.append(f"{name}${enc}")

            if encoded_items:
                line_name = src.get('collectName') or src.get('vodPlayFrom') or f"线路{idx+1}"
                vod_play_from.append(line_name)
                vod_play_url.append('#'.join(encoded_items))

        info['vod_play_from'] = '$$$'.join(vod_play_from)
        info['vod_play_url'] = '$$$'.join(vod_play_url)
        return {'list': [info]}

    # ---------- 搜索 ----------
    def searchContent(self, key, quick, pg="1"):
        url = f"{self.host}/api/search/keyword"
        params = {"keyword": key, "pageNum": pg, "pageSize": 10}
        headers = self.getheader()
        try:
            resp = self.fetch(url, headers=headers, params=params)
            data = resp.json()
            vod_list = [self._vod_to_common(item) for item in data.get('data', [])]
        except Exception as e:
            print(f"搜索失败: {e}")
            vod_list = []
        return {'list': vod_list, 'page': pg}

    # ---------- 播放解析 ----------
    def playerContent(self, flag, id, vipFlags):
        try:
            payload = json.loads(self.d64(id))
            collect_id = payload.get('collectId')
            raw_url = payload.get('url')
            if not collect_id or not raw_url:
                raise ValueError("缺少参数")
        except:
            return {
                'parse': 1,
                'url': '',
                'header': {'User-Agent': 'okhttp/4.1.0/luob.app'}
            }

        # 已是一条可直接播放的音视频直链(m3u8/mp4 等)时, 直接返回, 无需再次解析
        if self.is_direct(raw_url):
            return {
                'parse': 0,
                'url': raw_url,
                'header': {'User-Agent': 'okhttp/4.1.0/luob.app'}
            }

        parse_url = f"{self.host}/api/vod/parse"
        params = {"collectId": collect_id, "url": raw_url}
        headers = self.getheader()
        try:
            resp = self.fetch(parse_url, headers=headers, params=params)
            if resp.status_code == 200:
                result = resp.json()
                if result.get('code') == 200:
                    final_url = result.get('data') or result.get('url')
                    if final_url:
                        return {
                            'parse': 0,
                            'url': final_url,
                            'header': {'User-Agent': 'okhttp/4.1.0/luob.app'}
                        }
        except Exception as e:
            print(f"解析失败: {e}")

        return {
            'parse': 1,
            'url': raw_url,
            'header': {'User-Agent': 'okhttp/4.1.0/luob.app'}
        }

    def is_direct(self, url):
        low = (url or '').lower()
        for ext in ('.m3u8', '.mp4', '.flv', '.mkv', '.ts', '.mp3'):
            if ext in low:
                return True
        return False

    # ---------- 内部辅助：字段映射 ----------
    def _vod_to_common(self, item):
        remark = item.get('vodRemarks', '')
        color = item.get('vodColor')
        if color:
            remark = f"[{color}] {remark}" if remark else color

        return {
            'vod_id': item.get('vodId'),
            'vod_name': item.get('vodName'),
            'vod_pic': self._fix_pic(item.get('vodPic')),
            'vod_remarks': remark,
            'vod_year': item.get('vodYear'),
            'vod_area': item.get('vodArea'),
            'vod_actor': item.get('vodActor'),
            'vod_director': item.get('vodDirector'),
            'vod_lang': item.get('vodLang'),
            'vod_class': item.get('vodClass'),
        }

    def _fix_pic(self, pic):
        """补全相对路径图片"""
        if pic and pic.startswith('/'):
            return self.host + pic
        return pic