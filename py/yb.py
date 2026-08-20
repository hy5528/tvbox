# -*- coding: utf-8 -*-
"""
歪比巴卜 Spider - 适配 wbbb1.com
兼容 FongMi/TV (T3) 和 WebHomeTV/PeekPro (T4)

来源: 歪比.html 中的 WebHome 脚本逻辑
- 域名: wbbb1.com
- 播放器页面: xn--qvr2v.850088.xyz (歪比.850088.xyz)
- 播放API: xn--qvr2v.850088.xyz/player/api.php (RC4+AES)
- 解析: 纯Python AES-128-CBC, 无外部依赖

修复 (抓包验证 2026-08-15):
1. 分类对齐JS源码 (首页/电影/剧集/动漫/综艺)
2. 移除热搜榜 (纯文字排名无封面) 和今日更新
3. 播放永不返回parse:1嗅探 (防推荐/蓝光E/蓝光B线路卡死)
4. directResolve失败时返回parse:0空URL (优雅失败)
5. 所有m3u8统一用 Origin: PLAYER_HOST + X-Requested-With: mark.via
6. UA对齐抓包: Chrome/149 Android 11 KB2000
7. 429/403重试逻辑 (修复子分类不稳定)
8. 筛选器URL改为 /show/ 12段格式 (修复筛选无效)
9. 筛选值对齐网站实际值 (地区/类型/年份)
"""
import sys
import json
import re
import hashlib
import base64
import time
import struct
import urllib.request
import urllib.parse
import ssl

sys.path.append('..')

# ===== 兼容导入 =====
try:
    from base.spider import Spider
except ImportError:
    import requests as rq
    class Spider:
        def fetch(self, url, headers=None, **kw):
            kw.pop('timeout', None)
            r = rq.get(url, headers=headers, timeout=15, **kw)
            r.encoding = 'utf-8'
            return r

try:
    from urllib.parse import quote
except ImportError:
    from urllib import quote


# ===== 纯Python AES-128-CBC 实现 (无外部依赖) =====
class _AES:
    """AES-128 CBC 模式, 仅实现解密"""
    SBOX = [
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
        0x8c,0xa1,0x89,0x0d,0xbf,0xe6,0x42,0x68,0x41,0x99,0x2d,0x0f,0xb0,0x54,0xbb,0x16,
    ]
    RCON = [0x01,0x02,0x04,0x08,0x10,0x20,0x40,0x80,0x1b,0x36]

    @staticmethod
    def _xtime(a):
        return (((a << 1) ^ 0x1b) & 0xff) if (a & 0x80) else (a << 1)

    @staticmethod
    def _mul(a, b):
        r = 0
        for _ in range(8):
            if b & 1:
                r ^= a
            a = _AES._xtime(a)
            b >>= 1
        return r

    @staticmethod
    def _key_expansion(key):
        w = []
        for i in range(4):
            w.append(list(key[4*i:4*i+4]))
        for i in range(4, 44):
            temp = list(w[i-1])
            if i % 4 == 0:
                temp = temp[1:] + temp[:1]
                temp = [_AES.SBOX[b] for b in temp]
                temp[0] ^= _AES.RCON[i//4 - 1]
            w.append([w[i-4][j] ^ temp[j] for j in range(4)])
        return w

    @staticmethod
    def _inv_sub_bytes(state):
        for i in range(16):
            state[i] = _AES.SBOX.index(state[i])

    @staticmethod
    def _inv_shift_rows(state):
        state[1], state[5], state[9], state[13] = state[13], state[1], state[5], state[9]
        state[2], state[6], state[10], state[14] = state[10], state[14], state[2], state[6]
        state[3], state[7], state[11], state[15] = state[7], state[11], state[15], state[3]

    @staticmethod
    def _inv_mix_columns(state):
        for c in range(4):
            i = c * 4
            a0, a1, a2, a3 = state[i], state[i+1], state[i+2], state[i+3]
            state[i]   = _AES._mul(a0,0x0e) ^ _AES._mul(a1,0x0b) ^ _AES._mul(a2,0x0d) ^ _AES._mul(a3,0x09)
            state[i+1] = _AES._mul(a0,0x09) ^ _AES._mul(a1,0x0e) ^ _AES._mul(a2,0x0b) ^ _AES._mul(a3,0x0d)
            state[i+2] = _AES._mul(a0,0x0d) ^ _AES._mul(a1,0x09) ^ _AES._mul(a2,0x0e) ^ _AES._mul(a3,0x0b)
            state[i+3] = _AES._mul(a0,0x0b) ^ _AES._mul(a1,0x0d) ^ _AES._mul(a2,0x09) ^ _AES._mul(a3,0x0e)

    @staticmethod
    def _add_round_key(state, w, rnd):
        for c in range(4):
            i = c * 4
            rk = w[rnd * 4 + c]
            state[i] ^= rk[0]; state[i+1] ^= rk[1]; state[i+2] ^= rk[2]; state[i+3] ^= rk[3]

    @staticmethod
    def decrypt_block(block, w):
        state = list(block)
        _AES._add_round_key(state, w, 10)
        for rnd in range(9, 0, -1):
            _AES._inv_shift_rows(state)
            _AES._inv_sub_bytes(state)
            _AES._add_round_key(state, w, rnd)
            _AES._inv_mix_columns(state)
        _AES._inv_shift_rows(state)
        _AES._inv_sub_bytes(state)
        _AES._add_round_key(state, w, 0)
        return bytes(state)

    @staticmethod
    def cbc_decrypt(data, key, iv):
        w = _AES._key_expansion(key)
        result = b''
        for i in range(0, len(data), 16):
            block = data[i:i+16]
            decrypted = _AES.decrypt_block(block, w)
            result += bytes(a ^ b for a, b in zip(decrypted, iv))
            iv = block
        if result:
            pad_len = result[-1]
            if 1 <= pad_len <= 16 and all(b == pad_len for b in result[-pad_len:]):
                result = result[:-pad_len]
        return result


class Spider(Spider):

    HOSTS = [
        "https://wbbb1.com",
        "https://wbbb2.com",
        "https://wbbb3.com",
    ]
    HOST = HOSTS[0]
    PLAYER_HOST = "https://xn--qvr2v.850088.xyz"

    MOBILE_UA = 'Mozilla/5.0 (Linux; Android 11; KB2000 Build/RP1A.201005.001; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/149.0.7827.91 Mobile Safari/537.36'

    AES_KEY = b'OddfJktEbGu7gCv9'
    AES_IV = b'okjutU3RjGpWqB8Z'

    # ===== 分类 (移除热搜榜和今日更新) =====
    CATEGORIES = [
        {'type_id': 'home',    'type_name': '首页'},
        {'type_id': '1',       'type_name': '电影'},
        {'type_id': '2',       'type_name': '剧集'},
        {'type_id': '3',       'type_name': '动漫'},
        {'type_id': '4',       'type_name': '综艺'},
    ]

    def getName(self):
        return "歪比巴卜"

    def init(self, extend=""):
        if isinstance(extend, list):
            self.extend = ''
        else:
            self.extend = extend or ''
        self.header = {
            'User-Agent': self.MOBILE_UA,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7',
            'Cache-Control': 'no-cache',
            'Referer': self.HOST + '/',
            'X-Requested-With': 'mark.via',
        }
        self._session = None
        self._ensure_session()
        self._ssl_ctx = ssl.create_default_context()
        self._ssl_ctx.check_hostname = False
        self._ssl_ctx.verify_mode = ssl.CERT_NONE
        self._cookie_ok = False

        # ===== MacCMS 筛选器定义 (对齐 wbbb1.com 实际值) =====
        # URL格式: /show/{id}-{area}-{by}-{class}-{lang}-{letter}-{ver}-{state}-{page}-{?}-{?}-{year}.html
        # 12段, 按位置填入
        area_all = [
            {'n': '全部', 'v': ''}, {'n': '大陆', 'v': '大陆'}, {'n': '港台', 'v': '港台'},
            {'n': '美国', 'v': '美国'}, {'n': '韩国', 'v': '韩国'}, {'n': '日本', 'v': '日本'},
            {'n': '泰国', 'v': '泰国'}, {'n': '印度', 'v': '印度'}, {'n': '法国', 'v': '法国'},
            {'n': '英国', 'v': '英国'},
        ]
        year_opts = [
            {'n': '全部', 'v': ''}, {'n': '2026', 'v': '2026'}, {'n': '2025', 'v': '2025'},
            {'n': '2024', 'v': '2024'}, {'n': '2023', 'v': '2023'}, {'n': '2022', 'v': '2022'},
            {'n': '2021', 'v': '2021'}, {'n': '2020', 'v': '2020'}, {'n': '2019', 'v': '2019'},
            {'n': '2018', 'v': '2018'}, {'n': '2017', 'v': '2017'}, {'n': '2016', 'v': '2016'},
            {'n': '2015', 'v': '2015'}, {'n': '2014', 'v': '2014'}, {'n': '2013', 'v': '2013'},
            {'n': '2012', 'v': '2012'}, {'n': '2011', 'v': '2011'}, {'n': '2010', 'v': '2010'},
        ]
        class_movie = [
            {'n': '全部', 'v': ''}, {'n': '动作', 'v': '动作'}, {'n': '喜剧', 'v': '喜剧'},
            {'n': '爱情', 'v': '爱情'}, {'n': '科幻', 'v': '科幻'}, {'n': '剧情', 'v': '剧情'},
            {'n': '战争', 'v': '战争'}, {'n': '警匪', 'v': '警匪'}, {'n': '犯罪', 'v': '犯罪'},
            {'n': '动画', 'v': '动画'}, {'n': '奇幻', 'v': '奇幻'}, {'n': '武侠', 'v': '武侠'},
            {'n': '冒险', 'v': '冒险'}, {'n': '恐怖', 'v': '恐怖'},
        ]
        class_tv = [
            {'n': '全部', 'v': ''}, {'n': '古装', 'v': '古装'}, {'n': '言情', 'v': '言情'},
            {'n': '武侠', 'v': '武侠'}, {'n': '偶像', 'v': '偶像'}, {'n': '家庭', 'v': '家庭'},
            {'n': '都市', 'v': '都市'}, {'n': '喜剧', 'v': '喜剧'}, {'n': '战争', 'v': '战争'},
            {'n': '悬疑', 'v': '悬疑'}, {'n': '科幻', 'v': '科幻'}, {'n': '冒险', 'v': '冒险'},
            {'n': '惊悚', 'v': '惊悚'}, {'n': '犯罪', 'v': '犯罪'}, {'n': '运动', 'v': '运动'},
            {'n': '恐怖', 'v': '恐怖'}, {'n': '剧情', 'v': '剧情'}, {'n': '奇幻', 'v': '奇幻'},
            {'n': '纪录片', 'v': '纪录片'}, {'n': '灾难', 'v': '灾难'}, {'n': '动作', 'v': '动作'},
            {'n': '爱情', 'v': '爱情'}, {'n': '历史', 'v': '历史'},
        ]
        class_anime = [
            {'n': '全部', 'v': ''}, {'n': '情感', 'v': '情感'}, {'n': '科幻', 'v': '科幻'},
            {'n': '热血', 'v': '热血'}, {'n': '推理', 'v': '推理'}, {'n': '搞笑', 'v': '搞笑'},
            {'n': '冒险', 'v': '冒险'}, {'n': '萝莉', 'v': '萝莉'}, {'n': '校园', 'v': '校园'},
            {'n': '动作', 'v': '动作'}, {'n': '机战', 'v': '机战'}, {'n': '运动', 'v': '运动'},
            {'n': '战争', 'v': '战争'}, {'n': '少年', 'v': '少年'}, {'n': '少女', 'v': '少女'},
            {'n': '社会', 'v': '社会'}, {'n': '原创', 'v': '原创'}, {'n': '亲子', 'v': '亲子'},
        ]
        class_variety = [
            {'n': '全部', 'v': ''}, {'n': '真人秀', 'v': '真人秀'}, {'n': '音乐', 'v': '音乐'},
            {'n': '喜剧', 'v': '喜剧'}, {'n': '脱口秀', 'v': '脱口秀'}, {'n': '文化', 'v': '文化'},
            {'n': '美食', 'v': '美食'},
        ]

        self._filters = {
            '1': [
                {'key': 'class', 'name': '类型', 'value': class_movie},
                {'key': 'area', 'name': '地区', 'value': area_all},
                {'key': 'year', 'name': '年份', 'value': year_opts},
            ],
            '2': [
                {'key': 'class', 'name': '类型', 'value': class_tv},
                {'key': 'area', 'name': '地区', 'value': area_all},
                {'key': 'year', 'name': '年份', 'value': year_opts},
            ],
            '3': [
                {'key': 'class', 'name': '类型', 'value': class_anime},
                {'key': 'area', 'name': '地区', 'value': area_all},
                {'key': 'year', 'name': '年份', 'value': year_opts},
            ],
            '4': [
                {'key': 'class', 'name': '类型', 'value': class_variety},
                {'key': 'area', 'name': '地区', 'value': area_all},
                {'key': 'year', 'name': '年份', 'value': year_opts},
            ],
        }
        # 首页不需要筛选器
        self._filters['home'] = []

    def _ensure_session(self):
        try:
            import requests as _req
            s = _req.Session()
            s.verify = False
            self._session = s
        except ImportError:
            self._session = None

    def _txt(self, url, referer=None, timeout=15):
        """请求页面 - 包含520/429/403重试"""
        headers = dict(self.header)
        if referer:
            headers['Referer'] = referer

        try:
            # 优先用 self.fetch (TVBox 内置 okhttp)
            try:
                r = self.fetch(url, headers=headers)
                text = r.text if hasattr(r, 'text') else r.content.decode('utf-8', errors='ignore')
                if text and len(text) > 500 and 'Just a moment' not in text and '520' not in text[:200]:
                    return text
            except Exception:
                pass

            # 备用: requests (带重试和cookie)
            if self._session:
                for attempt in range(3):
                    r = self._session.get(url, headers=headers, timeout=timeout)
                    r.encoding = 'utf-8'

                    # 429/403: 等待重试
                    if r.status_code in (429, 403):
                        wait = (attempt + 1) * 1.5
                        time.sleep(wait)
                        # 换 Referer 重试
                        retry_headers = dict(headers)
                        retry_headers['Referer'] = 'https://www.baidu.com/'
                        r = self._session.get(url, headers=retry_headers, timeout=timeout)
                        r.encoding = 'utf-8'
                        if r.status_code == 200 and len(r.text) > 500:
                            return r.text
                        continue

                    if r.status_code == 520:
                        retry_headers = dict(headers)
                        retry_headers['Referer'] = 'https://www.baidu.com/'
                        ts = int(time.time() * 1000)
                        sep = '&' if '?' in url else '?'
                        retry_url = f"{url}{sep}_t={ts}"
                        try:
                            r2 = self._session.get(retry_url, headers=retry_headers, timeout=timeout)
                            r2.encoding = 'utf-8'
                            if r2.status_code == 200 and len(r2.text) > 1000:
                                return r2.text
                        except Exception:
                            pass
                        if self.HOST in url:
                            for alt_host in self.HOSTS[1:]:
                                alt_url = url.replace(self.HOST, alt_host)
                                try:
                                    r3 = self._session.get(alt_url, headers=retry_headers, timeout=timeout)
                                    r3.encoding = 'utf-8'
                                    if r3.status_code == 200 and len(r3.text) > 1000:
                                        self.HOST = alt_host
                                        return r3.text
                                except Exception:
                                    continue

                    if r.status_code == 200:
                        return r.text

                    # 其他错误码: 尝试备用域名
                    if self.HOST in url and attempt < 2:
                        for alt_host in self.HOSTS[1:]:
                            alt_url = url.replace(self.HOST, alt_host)
                            try:
                                r4 = self._session.get(alt_url, headers=headers, timeout=timeout)
                                r4.encoding = 'utf-8'
                                if r4.status_code == 200 and len(r4.text) > 500:
                                    self.HOST = alt_host
                                    return r4.text
                            except Exception:
                                continue
            return ""
        except Exception:
            return ""

    def _post_txt(self, url, data, headers, timeout=10):
        """POST 请求 - 三层回退: requests → urllib → self.fetch"""
        # 方式1: requests (推荐, 自动处理 gzip/SSL)
        if self._session:
            try:
                post_headers = dict(headers)
                post_headers['Accept-Encoding'] = 'identity'
                r = self._session.post(url, data=data, headers=post_headers, timeout=timeout, verify=False)
                if r.status_code == 200 and r.text:
                    return r.text
            except Exception:
                pass

        # 方式2: self.fetch (TVBox 内置 okhttp, 支持POST)
        try:
            post_headers = dict(headers)
            body = urllib.parse.urlencode(data)
            r = self.fetch(url, headers=post_headers, data=body, method='POST')
            text = r.text if hasattr(r, 'text') else r.content.decode('utf-8', errors='ignore')
            if text:
                return text
        except Exception:
            pass

        # 方式3: urllib (最终回退)
        try:
            post_headers = dict(headers)
            post_headers['Accept-Encoding'] = 'identity'
            body = urllib.parse.urlencode(data).encode('utf-8')
            req = urllib.request.Request(url, data=body, headers=post_headers, method='POST')
            with urllib.request.urlopen(req, timeout=timeout, context=self._ssl_ctx) as resp:
                return resp.read().decode('utf-8', errors='ignore')
        except Exception:
            return ""

    def _abs(self, url):
        if not url:
            return ''
        if url.startswith('http'):
            return url
        if url.startswith('//'):
            return 'https:' + url
        if url.startswith('/'):
            return self.HOST + url
        return self.HOST + '/' + url

    def _strip_tags(self, text):
        if not text:
            return ''
        return re.sub(r'<[^>]+>', '', text).strip()

    def _clean(self, text):
        if not text:
            return ''
        text = self._strip_tags(text)
        text = re.sub(r'\s+', ' ', text)
        return text.strip()

    # ========== 首页 ==========
    def homeContent(self, filter):
        return {
            'class': self.CATEGORIES,
            'filters': self._filters,
        }

    def homeVideoContent(self):
        html = self._txt(self.HOST + "/")
        videos = self._parse_list(html)
        return {'list': videos[:72]}

    # ========== 视频列表解析 ==========
    def _parse_list(self, html):
        """解析视频列表 - 对应 JS 的 parseList() + cardFromA()"""
        videos = []
        if not html:
            return videos

        # 找所有包含 /detail/ 的 <a> 标签
        a_pattern = r'<a[^>]+href="([^"]*/detail/[^"]+)"[^>]*>(.*?)</a>'
        a_matches = re.findall(a_pattern, html, re.S)

        seen = set()
        for href, inner_html in a_matches:
            vid_match = re.search(r'/detail/(\d+)\.html', href)
            if not vid_match:
                continue
            vod_id = vid_match.group(1)
            if vod_id in seen:
                continue
            seen.add(vod_id)

            # 从 <a> 内部找 <img>: data-src > data-original > src
            img = ''
            for attr in ['data-src', 'data-original', 'src']:
                img_m = re.search(r'<img[^>]+' + attr + r'="([^"]+)"', inner_html, re.S)
                if img_m:
                    img = img_m.group(1)
                    if not any(x in img.lower() for x in ['load.gif', 'errorpic', 'placeholder', 'lazyload']):
                        break
                    img = ''

            # 标题: title 属性 > img alt > 文本
            title = ''
            title_m = re.search(r'title="([^"]*)"', href + '" ' + inner_html)
            if title_m:
                title = self._clean(title_m.group(1))
            if not title:
                alt_m = re.search(r'alt="([^"]*)"', inner_html, re.S)
                if alt_m:
                    title = self._clean(alt_m.group(1))
            if not title:
                text = self._clean(inner_html)
                title = text[:30]

            # 备注
            remark = ''
            text = self._clean(inner_html)
            remark_m = re.search(r'(4K|更新至[^\s]*|已完结|HD|全集|抢先|蓝光|超清|高清|正片|完结)', text)
            if remark_m:
                remark = remark_m.group(1)
                full_m = re.search(r'(更新至[^\s]*)', text)
                if full_m:
                    remark = full_m.group(1)

            videos.append({
                'vod_id': vod_id,
                'vod_name': title or '未知',
                'vod_pic': self._abs(img) if img else '',
                'vod_remarks': remark,
            })

        return videos

    # ========== 分类列表 (修复: /show/ 12段格式 + 筛选器) ==========
    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if pg else 1

        # 首页直接用首页URL (无分页, 单页显示所有内容)
        if tid == 'home':
            url = f"{self.HOST}/"
        else:
            # MacCMS /show/ 格式: 12段
            # /show/{id}-{area}-{by}-{class}-{lang}-{letter}-{ver}-{state}-{page}-{?}-{?}-{year}.html
            ext = extend or {}
            area = ext.get('area', '')
            cls = ext.get('class', '')
            year = ext.get('year', '')

            # URL编码中文筛选值
            area_enc = quote(area) if area else ''
            cls_enc = quote(cls) if cls else ''

            # 构造12段路径 (按位置填入)
            segments = [
                tid,        # pos 0: id
                area_enc,   # pos 1: area
                '',         # pos 2: by (排序, 不暴露)
                cls_enc,    # pos 3: class
                '',         # pos 4: lang
                '',         # pos 5: letter
                '',         # pos 6: ver
                '',         # pos 7: state
                str(page),  # pos 8: page
                '',         # pos 9: ?
                '',         # pos 10: ?
                year,       # pos 11: year
            ]
            path = '-'.join(segments)
            url = f"{self.HOST}/show/{path}.html"

        html = self._txt(url, referer=self.HOST + "/")
        videos = self._parse_list(html)

        # 解析总页数
        total_pages = 1
        if html:
            # 从分页链接中提取最大页码
            # 格式: /show/{tid}-...-{page}---{year?}.html (page在pos8, year在pos11)
            page_pattern = re.compile(
                r'/show/' + re.escape(tid) + r'-[^"]*?-(\d+)---\d*\.html'
            )
            page_nums = page_pattern.findall(html)
            if page_nums:
                total_pages = max(int(p) for p in page_nums)
            elif videos:
                total_pages = page + 1

        return {
            'list': videos,
            'page': page,
            'pagecount': total_pages,
            'limit': 20,
            'total': len(videos) * total_pages if total_pages > 1 else len(videos),
        }

    # ========== 详情页 ==========
    def detailContent(self, ids):
        if isinstance(ids, str):
            ids = [ids]
        vod_id = ids[0]

        url = f"{self.HOST}/detail/{vod_id}.html"
        html = self._txt(url, referer=self.HOST + "/")

        vod_name = ''
        vod_pic = ''
        type_name = ''
        vod_year = ''
        vod_area = ''
        vod_actor = ''
        vod_director = ''
        vod_content = ''
        vod_remarks = ''

        if html:
            # 标题
            m = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.S)
            if m:
                vod_name = self._clean(m.group(1))
                vod_name = re.sub(r'(电视剧|电影|动漫|综艺|短剧|连续剧|国产剧|动画)$', '', vod_name)

            # 封面
            for attr in ['data-original', 'data-src', 'src']:
                m = re.search(
                    r'<img[^>]+' + attr + r'="([^"]+)"[^>]*(?:alt|class)',
                    html, re.S
                )
                if m:
                    pic = m.group(1)
                    if not any(x in pic.lower() for x in ['load.gif', 'errorpic', 'placeholder']):
                        vod_pic = self._abs(pic)
                        break

            # 提取字段
            text = self._strip_tags(html)
            text = re.sub(r'\s+', ' ', text)

            def pick_field(label):
                labels = ['类型', '导演', '演员', '语言', '连载', '更新', '年份', '地区', '时间']
                others = [l for l in labels if l != label]
                pattern = label + r'\s*[：:]\s*(.*?)(?=' + '|'.join(others) + r'|简介|剧情|播放|选集|$)'
                m = re.search(pattern, text)
                if m:
                    val = self._clean(m.group(1))
                    return val[:120] if val else ''
                return ''

            type_name = pick_field('类型')
            vod_director = pick_field('导演')
            vod_actor = pick_field('演员')
            vod_year = pick_field('年份')
            vod_area = pick_field('地区')
            vod_remarks = pick_field('连载') or pick_field('更新')

            # 简介
            m = re.search(
                r'class="[^"]*module-info-introduction[^"]*"[^>]*>(.*?)</div>',
                html, re.S
            )
            if not m:
                m = re.search(r'(?:简介|剧情介绍)\s*[：:]?\s*(.*?)(?:选集|播放线路|资源|热播|相关|⚠)', text, re.S)
            if m:
                vod_content = self._clean(m.group(1))
                if len(vod_content) > 360:
                    vod_content = vod_content[:360] + '…'

            # 播放线路和集数
            play_from, play_url = self._parse_play_lines(html, vod_id)
        else:
            play_from = ['默认线路']
            play_url = [f'正片${vod_id}']

        vod = {
            'vod_id': vod_id,
            'vod_name': vod_name or vod_id,
            'vod_pic': vod_pic,
            'type_name': type_name,
            'vod_year': vod_year,
            'vod_area': vod_area,
            'vod_remarks': vod_remarks,
            'vod_actor': vod_actor,
            'vod_director': vod_director,
            'vod_content': vod_content,
            'vod_play_from': '$$$'.join(play_from),
            'vod_play_url': '$$$'.join(play_url),
        }
        return {'list': [vod]}

    def _parse_play_lines(self, html, vod_id):
        """
        解析播放线路和集数 - 完全对齐 JS parseDetail() linesGroup 逻辑

        JS 流程:
        1. 从 .module-tab-item.tab-item 提取线路名称 (data-dropdown-value)
        2. 找 panels: .module-list.sort-list.tab-list.his-tab-list
        3. 每个 panel 内找: a.module-play-list-link, a[href*="/vodplay/"], a[href*="/vplay/"], a[href*="/play/"]
        4. 无 panels 时全局搜索, 按 URL 中的 line_id 分组
        """
        play_from = []
        play_url_list = []

        # 1. 提取线路名称 - 对应 JS lineNames 逻辑
        line_names = []
        # 方式A: data-dropdown-value 属性
        dd_matches = re.findall(
            r'data-dropdown-value="([^"]*)"[^>]*>(?:<span[^>]*>)?([^<]*)',
            html, re.S
        )
        line_names = [self._clean(n[0] or n[1]) for n in dd_matches if self._clean(n[0] or n[1])]

        # 方式B: module-tab-item tab-item 文本
        if not line_names:
            tab_matches = re.findall(
                r'class="[^"]*module-tab-item[^"]*tab-item[^"]*"[^>]*>\s*(?:<span[^>]*>)?\s*([^<]+)',
                html, re.S
            )
            line_names = [self._clean(n) for n in tab_matches if self._clean(n)]

        # 方式C: 从文本提取 "线路名(集数)" 格式
        if not line_names:
            name_matches = re.findall(r'([^\s\n<>()]{2,12})\((\d+)\)', html)
            line_names = [n[0] for n in name_matches
                         if not any(x in n[0] for x in ['提醒', '搜索', '播放', '记录', '排序', '切换', '简介', '剧情'])]

        line_names = list(dict.fromkeys(line_names))

        # 2. 提取集数链接 - 灵活匹配 (不限定 URL 格式)
        # 对应 JS: a[href*="/vodplay/"], a[href*="/vplay/"], a[href*="/play/"], a.module-play-list-link
        play_link_pattern = r'<a[^>]*href="([^"]*(?:/vodplay/|/vplay/|/play/)[^"]*\.html)"[^>]*>(.*?)</a>'

        # 3. 尝试按 panel 分组 - 对应 JS panels 逻辑
        # JS: d.querySelectorAll('.module-list.sort-list.tab-list.his-tab-list')
        panel_pattern = r'class="[^"]*module-list[^"]*sort-list[^"]*tab-list[^"]*his-tab-list[^"]*"'
        panels = re.split(panel_pattern, html)

        lines_group = []  # [(name, [(title, href), ...]), ...]

        if len(panels) > 1:
            # 有 panels - 每个 panel 是一条线路
            for i, panel_html in enumerate(panels[1:], 0):
                eps = re.findall(play_link_pattern, panel_html, re.S)
                if not eps:
                    continue
                # 去重
                seen = set()
                arr = []
                for href, inner in eps:
                    abs_href = self._abs(href)
                    if abs_href in seen:
                        continue
                    seen.add(abs_href)
                    title = self._clean(re.sub(r'<[^>]+>', '', inner)) or '播放'
                    arr.append((title, abs_href))

                # 按集数排序
                def ep_num(ep):
                    m = re.search(r'/(?:vodplay|vplay|play)/\d+-\d+-(\d+)\.html', ep[1])
                    if m:
                        return int(m.group(1))
                    m2 = re.search(r'(\d+)', ep[0])
                    return int(m2.group(1)) if m2 else 0

                arr.sort(key=ep_num)
                name = line_names[i] if i < len(line_names) else f'线路{i+1}'
                lines_group.append((name, arr))

        if not lines_group:
            # 无 panels - 全局搜索, 按 URL 中的 line_id 分组
            # 对应 JS: eps0.forEach 分组逻辑
            all_eps = re.findall(play_link_pattern, html, re.S)
            if not all_eps:
                # 最终回退: 也尝试 module-play-list-link
                mpl_pattern = r'<a[^>]*class="[^"]*module-play-list-link[^"]*"[^>]*href="([^"]+)"[^>]*>(.*?)</a>'
                all_eps = re.findall(mpl_pattern, html, re.S)

            if not all_eps:
                return ['默认线路'], [f'正片${vod_id}']

            # 去重
            seen = set()
            groups = {}
            line_order = []

            for href, inner in all_eps:
                abs_href = self._abs(href)
                if abs_href in seen:
                    continue
                seen.add(abs_href)

                # 提取 line_id: /vodplay/{num}-{line_id}-{ep_num}.html
                sid_match = re.search(r'/(?:vodplay|vplay|play)/\d+-(\d+)-\d+\.html', abs_href)
                sid = sid_match.group(1) if sid_match else '1'

                if sid not in groups:
                    groups[sid] = []
                    line_order.append(sid)

                title = self._clean(re.sub(r'<[^>]+>', '', inner)) or '播放'
                groups[sid].append((title, abs_href))

            # 排序
            for sid in line_order:
                def ep_num(ep):
                    m = re.search(r'/(?:vodplay|vplay|play)/\d+-\d+-(\d+)\.html', ep[1])
                    if m:
                        return int(m.group(1))
                    m2 = re.search(r'(\d+)', ep[0])
                    return int(m2.group(1)) if m2 else 0
                groups[sid].sort(key=ep_num)

            for i, sid in enumerate(line_order):
                name = line_names[i] if i < len(line_names) else f'线路{sid}'
                lines_group.append((name, groups[sid]))

        if not lines_group:
            return ['默认线路'], [f'正片${vod_id}']

        for name, eps in lines_group:
            play_from.append(name)
            episodes = [f'{title}${href}' for title, href in eps]
            play_url_list.append('#'.join(episodes))

        return play_from, play_url_list

    # ========== 搜索 ==========
    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if pg else 1
        if page == 1:
            url = f"{self.HOST}/search/{quote(key)}-------------.html"
        else:
            url = f"{self.HOST}/search/{quote(key)}----------{page}---.html"

        html = self._txt(url, referer=self.HOST + "/")
        videos = self._parse_list(html)

        return {
            'list': videos,
            'page': page,
            'pagecount': 10,
            'limit': 20,
            'total': len(videos) * 10,
        }

    # ========== 播放解析 (完全对齐 JS playEpisode + parsePlay + directResolve) ==========
    def playerContent(self, flag, id, vipFlags):
        """
        播放解析 - 完全对齐 JS 的 playEpisode() + parsePlay() + directResolve()

        修复 (抓包验证):
        1. 永不返回 parse:1 嗅探 (会导致推荐/蓝光E/蓝光B线路卡死)
        2. directResolve 失败时返回 parse:0 空URL (优雅失败, 不卡死)
        3. 所有媒体URL统一用 Origin: PLAYER_HOST (抓包验证)
        """
        url = self._abs(id) if not id.startswith('http') else id

        # 情况0: 直接媒体链接 (play_url 中直接存的 m3u8/mp4)
        if any(ext in url.lower() for ext in ['.m3u8', '.mp4', '.mkv', '.flv']):
            return self._media_result(url)

        # 请求播放页 (短超时)
        html = self._txt(url, referer=self.HOST + "/", timeout=10)

        # ===== 对齐 JS parsePlay() =====
        player_data = self._extract_player_aaaa(html)

        # 提取 iframe (JS: d.querySelector('iframe[src]'))
        iframe_src = ''
        iframe_match = re.search(r'<iframe[^>]+src="([^"]+)"', html, re.S)
        if iframe_match:
            iframe_src = self._abs(iframe_match.group(1))

        if player_data:
            token = player_data.get('url', '')
            from_field = player_data.get('from', '')
            link_next = player_data.get('link_next', '')
            vod_name = ''
            if player_data.get('vod_data'):
                vod_name = player_data['vod_data'].get('vod_name', '')

            # ===== 构造 pp.src (完全对齐 JS parsePlay) =====
            pp_src = ''
            if iframe_src:
                pp_src = iframe_src
            elif token:
                if token.startswith('http'):
                    pp_src = token
                else:
                    next_param = ''
                    if link_next:
                        host = re.search(r'https?://([^/]+)', self.HOST)
                        if host:
                            next_param = f'//{host.group(1)}{link_next}'
                    pp_src = f'{self.PLAYER_HOST}/player/?url={quote(token)}'
                    if next_param:
                        pp_src += f'&next={quote(next_param)}'
                    if vod_name:
                        pp_src += f'&title={quote(vod_name)}'

            if pp_src and token:
                # 情况1: token 是直链媒体
                if token.startswith('http') and any(
                    ext in token.lower() for ext in ['.m3u8', '.mp4', '.mkv']
                ):
                    return self._media_result(token, pp_src)

                # 情况2: directResolve (JS: let real = await directResolve(pp))
                real_url = self._direct_resolve(token, pp_src)
                if real_url:
                    # 检查是否是媒体URL
                    if any(ext in real_url.lower() for ext in ['.m3u8', '.mp4', '.mkv']):
                        return self._media_result(real_url, pp_src)
                    # 解密结果可能是不含扩展名的URL, 但以http开头也尝试播放
                    if real_url.startswith('http'):
                        return self._media_result(real_url, pp_src)

                # 情况3: directResolve 失败 → 优雅失败 (不返回 parse:1 嗅探, 防卡死)
                return {
                    'parse': 0,
                    'playUrl': '',
                    'url': '',
                    'header': {
                        'User-Agent': self.MOBILE_UA,
                    },
                }

        # 情况4: 无 player_aaaa, 查找 iframe 中的直链
        if iframe_src:
            if any(ext in iframe_src.lower() for ext in ['.m3u8', '.mp4', '.mkv']):
                return self._media_result(iframe_src)
            # iframe 非直链: 不嗅探, 优雅失败
            return {
                'parse': 0,
                'playUrl': '',
                'url': '',
                'header': {
                    'User-Agent': self.MOBILE_UA,
                },
            }

        # 情况5: 页面中直接有 m3u8/mp4
        m = re.search(r'["\'](https?://[^"\']+\.(?:m3u8|mp4|mkv)[^"\']*)["\']', html, re.I)
        if m:
            return self._media_result(m.group(1))

        # 兜底: 优雅失败 (不返回 parse:1 嗅探原页面, 防卡死)
        return {
            'parse': 0,
            'playUrl': '',
            'url': '',
            'header': {
                'User-Agent': self.MOBILE_UA,
            },
        }

    def _media_result(self, media_url, pp_src=''):
        """
        构造媒体播放结果 - 完全对齐抓包验证的请求头

        抓包发现:
        - 所有 m3u8 请求 (ts.php/play.php/123pan) 统一带:
          Origin: https://xn--qvr2v.850088.xyz (PLAYER_HOST)
          X-Requested-With: mark.via
          User-Agent: Chrome/149 Android 11
        - 无 Referer (抓包中 ts.php/play.php/123pan 均无 Referer)
        - 响应 access-control-allow-origin: * (CORS开放)
        """
        play_headers = {
            'User-Agent': self.MOBILE_UA,
            'Origin': self.PLAYER_HOST,
            'X-Requested-With': 'mark.via',
        }

        is_m3u8 = '.m3u8' in media_url.lower()
        return {
            'parse': 0,
            'playUrl': '',
            'url': media_url,
            'header': play_headers,
            'format': 'application/x-mpegURL' if is_m3u8 else '',
            'contentType': 'application/x-mpegURL' if is_m3u8 else '',
        }

    def _extract_player_aaaa(self, html):
        """提取 var player_aaaa = {...} - 对齐 JS parsePlay()
        
        JS: html.match(/var\\s+player_aaaa\\s*=\\s*(\\{[\\s\\S]*?\\})\\s*<\\/script>/)
        
        改进: 用括号深度匹配, 正确处理嵌套JSON对象
        """
        if not html:
            return None
        
        # 方式1: 对齐 JS 正则 (要求 </script> 结尾, 非贪婪也能匹配到正确的 })
        m = re.search(r'var\s+player_aaaa\s*=\s*(\{[\s\S]*?\})\s*</script>', html)
        if m:
            try:
                raw = m.group(1).replace('\\/', '/').replace('\\n', '\n').replace('\\t', '\t')
                return json.loads(raw)
            except Exception:
                pass
        
        # 方式2: 括号深度匹配 (处理嵌套JSON, 不依赖 </script>)
        start_match = re.search(r'var\s+player_aaaa\s*=\s*\{', html)
        if start_match:
            start = start_match.end() - 1  # 指向 '{'
            depth = 0
            in_str = False
            escape = False
            for i in range(start, len(html)):
                ch = html[i]
                if escape:
                    escape = False
                    continue
                if ch == '\\':
                    escape = True
                    continue
                if ch == '"':
                    in_str = not in_str
                    continue
                if in_str:
                    continue
                if ch == '{':
                    depth += 1
                elif ch == '}':
                    depth -= 1
                    if depth == 0:
                        raw = html[start:i+1].replace('\\/', '/').replace('\\n', '\n').replace('\\t', '\t')
                        try:
                            return json.loads(raw)
                        except Exception:
                            pass
                        break
        
        # 方式3: 简单回退
        m = re.search(r'var\s+player_aaaa\s*=\s*(\{.*?\})\s*;', html, re.S)
        if m:
            try:
                raw = m.group(1).replace('\\/', '/')
                return json.loads(raw)
            except Exception:
                pass
        
        return None

    def _direct_resolve(self, token, pp_src=''):
        """
        解析播放地址 - 纯Python RC4 + AES-CBC
        完全对齐 JS 的 directResolve() 函数

        JS 流程:
        1. let u = new URL(pp.src), host = u.host  ← 从 pp.src 提取 host
        2. rc4key = (md5(urlParam) + ' P').slice(-22)
        3. POST {url, key, vkey, ckey} 到 https://{host}/player/api.php
        4. AES-CBC 解密返回的 url 字段

        参数:
          token: player_aaaa.url (pp.token)
          pp_src: pp.src (播放器页面URL, 用于提取host)
        """
        # 从 pp_src 提取 host (对齐 JS: let u=new URL(pp.src), host=u.host)
        host = 'xn--qvr2v.850088.xyz'  # 默认值
        if pp_src:
            host_match = re.search(r'https?://([^/]+)', pp_src)
            if host_match:
                host = host_match.group(1)

        # 重试逻辑 (最多2次)
        for attempt in range(2):
            try:
                url_param = token
                salt = 'stray'
                t = str(int(time.time()))

                def md5(s):
                    return hashlib.md5(s.encode('utf-8')).hexdigest()

                rc4key = (md5(url_param) + ' P')[-22:]

                # Referer = pp.src (对齐 JS: 'Referer': pp.src)
                referer = pp_src if pp_src else f'{self.PLAYER_HOST}/player/?url={quote(token)}'

                post_data = {
                    'url': url_param,
                    'key': self._rc4_b64(rc4key, md5(url_param + salt)),
                    'vkey': self._rc4_b64(rc4key, t + md5(rc4key + salt)),
                    'ckey': self._rc4_b64(rc4key, md5(host + salt)),
                }

                # Origin = 'https://' + host (对齐 JS)
                origin = f'https://{host}'

                post_headers = {
                    'User-Agent': self.MOBILE_UA,
                    'Referer': referer,
                    'Origin': origin,
                    'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                    'Accept': 'application/json, text/javascript, */*; q=0.01',
                    'X-Requested-With': 'mark.via',
                }

                api_url = f"https://{host}/player/api.php"
                resp = self._post_txt(api_url, post_data, post_headers, timeout=15)
                if not resp:
                    if attempt == 0:
                        time.sleep(0.5)
                        continue
                    return ''

                result = json.loads(resp)
                if not result or not result.get('url'):
                    if attempt == 0:
                        time.sleep(0.5)
                        continue
                    return ''

                # AES-CBC 解密 (纯Python)
                encrypted = base64.b64decode(result['url'])
                decrypted = _AES.cbc_decrypt(encrypted, self.AES_KEY, self.AES_IV)
                decoded = decrypted.decode('utf-8')

                if decoded and decoded.startswith('http'):
                    return decoded

                # 解密结果不是媒体URL, 可能是错误信息
                return ''

            except Exception:
                if attempt == 0:
                    time.sleep(0.5)
                    continue
                return ''

        return ''

    def _rc4_b64(self, key, data):
        """RC4 加密后 Base64 编码 - 对应 JS 的 rc4b64() 函数"""
        S = list(range(256))
        j = 0
        for i in range(256):
            j = (j + S[i] + ord(key[i % len(key)])) & 255
            S[i], S[j] = S[j], S[i]

        i = 0
        j = 0
        result = []
        for byte in data.encode('utf-8'):
            i = (i + 1) & 255
            j = (j + S[i]) & 255
            S[i], S[j] = S[j], S[i]
            result.append(byte ^ S[(S[i] + S[j]) & 255])

        return base64.b64encode(bytes(result)).decode('ascii')

    # ========== 本地代理 ==========
    def localProxy(self, param):
        return [200, "video/MP2T", b"", ""]

    def destroy(self):
        pass

    def close(self):
        self.destroy()
