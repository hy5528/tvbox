# coding=utf-8
#!/usr/bin/python
import re
import sys
from html import unescape
from urllib.parse import urljoin, quote

sys.path.append('..')
from base.spider import Spider


class Spider(Spider):
    host = 'https://www.xb6v.org'
    headers = {
        'User-Agent': 'Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 Chrome/120 Mobile Safari/537.36',
        'Referer': 'https://www.xb6v.org/',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9',
    }
    classes = [
        {'type_name': '首页', 'type_id': '/'},
        {'type_name': '喜剧片', 'type_id': '/xijupian/'},
        {'type_name': '动作片', 'type_id': '/dongzuopian/'},
        {'type_name': '爱情片', 'type_id': '/aiqingpian/'},
        {'type_name': '科幻片', 'type_id': '/kehuanpian/'},
        {'type_name': '恐怖片', 'type_id': '/kongbupian/'},
        {'type_name': '剧情片', 'type_id': '/juqingpian/'},
        {'type_name': '战争片', 'type_id': '/zhanzhengpian/'},
        {'type_name': '纪录片', 'type_id': '/jilupian/'},
        {'type_name': '动画片', 'type_id': '/donghuapian/'},
        {'type_name': '电视剧', 'type_id': '/dianshiju/'},
        {'type_name': '综艺', 'type_id': '/ZongYi/'},
    ]

    def getName(self):
        return '6v影视'

    def init(self, extend=''):
        pass

    def isVideoFormat(self, url):
        pass

    def manualVideoCheck(self):
        pass

    def destroy(self):
        pass

    def homeContent(self, filter):
        return {'class': self.classes}

    def homeVideoContent(self):
        return {'list': self._parse_list(self._html(self.host + '/'))}

    # 兼容部分 Python Spider 壳的命名
    def homeVod(self):
        return self.homeVideoContent()

    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg or 1)
        path = tid or '/'
        if page > 1:
            if path.endswith('/'):
                path = path + 'index_%d.html' % page
            else:
                path = path.rstrip('/') + '/index_%d.html' % page
        html = self._html(self._abs(path))
        videos = self._parse_list(html)
        return {'list': videos, 'page': page, 'pagecount': page + 1 if videos else page, 'limit': 18, 'total': 999999 if videos else 0}

    def detailContent(self, ids):
        url = ids[0] if isinstance(ids, list) else ids
        url = self._abs(url)
        html = self._html(url)
        title = self._first([r'<title>\s*([^<]+?)(?:-|_|\|).*?</title>', r'<h1[^>]*>(.*?)</h1>'], html, '未知影片')
        pic = self._first([r'<div[^>]+class=["\'][^"\']*thumbnail[^"\']*["\'][\s\S]*?<img[^>]+(?:src|data-original|data-src)=["\']([^"\']+)["\']', r'<img[^>]+(?:src|data-original|data-src)=["\']([^"\']+\.(?:jpg|jpeg|png|webp)[^"\']*)["\']'], html, '')
        desc = self._first([r'◎简\s*介\s*([\s\S]*?)(?:◎|<h3|</article>|$)', r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)["\']'], html, '暂无简介')
        lines = self._parse_detail_lines(html)
        play_from = '$$$'.join([x['name'] for x in lines]) or '详情页'
        play_url = '$$$'.join(['#'.join(['%s$%s' % (ep['title'], ep['url']) for ep in x['episodes']]) for x in lines]) or ('打开详情页$' + url)
        vod = {
            'vod_id': url,
            'vod_name': self._clean(title),
            'vod_pic': self._abs(pic),
            'type_name': '6v影视',
            'vod_year': self._year(title + ' ' + html),
            'vod_area': '',
            'vod_remarks': '',
            'vod_actor': '',
            'vod_director': '',
            'vod_content': self._clean(desc),
            'vod_play_from': play_from,
            'vod_play_url': play_url,
        }
        return {'list': [vod]}

    def searchContent(self, key, quick, pg='1'):
        url = self.host + '/e/search/11index.php'
        body = 'keyboard=%s&show=title&tempid=1&tbname=article&mid=1&dopost=search&submit=' % quote(key or '')
        html = self._html(url, method='post', data=body, extra_headers={'Content-Type': 'application/x-www-form-urlencoded'})
        return {'list': self._parse_list(html)}

    def playerContent(self, flag, id, vipFlags):
        url = self._abs(id)
        low = url.lower()
        if low.startswith('magnet:') or any(x in low for x in ['pan.quark.cn', 'pan.baidu.com', 'xunlei.com', 'aliyundrive.com', 'alipan.com', 'cloud.189.cn', 'yun.139.com', '123pan']):
            return {'parse': 0, 'jx': 0, 'url': url, 'header': self.headers}
        real = self._resolve_play_url(url)
        return {'parse': 0, 'jx': 0, 'url': real or url, 'header': {'User-Agent': self.headers['User-Agent'], 'Referer': self.host + '/'}}

    def localProxy(self, param):
        return None

    def _html(self, url, method='get', data=None, extra_headers=None):
        headers = dict(self.headers)
        if extra_headers:
            headers.update(extra_headers)
        try:
            if method.lower() == 'post':
                res = self.fetch(url, headers=headers, data=data, method='post', timeout=20)
            else:
                res = self.fetch(url, headers=headers, timeout=20)
            return self._res_text(res)
        except Exception:
            # 某些壳不支持 method 参数，POST 搜索失败时返回空；分类/首页不受影响
            try:
                if method.lower() == 'post':
                    res = self.fetch(url, headers=headers, postData=data, timeout=20)
                    return self._res_text(res)
            except Exception:
                pass
        return ''

    def _res_text(self, res):
        if res is None:
            return ''
        if isinstance(res, str):
            return res
        if isinstance(res, bytes):
            return self._decode(res)
        if isinstance(res, dict):
            val = res.get('content') or res.get('body') or res.get('data') or res.get('text') or ''
            if isinstance(val, bytes):
                return self._decode(val)
            return str(val or '')
        if hasattr(res, 'content'):
            val = getattr(res, 'content')
            if isinstance(val, bytes):
                return self._decode(val)
            return str(val or '')
        if hasattr(res, 'text'):
            return str(getattr(res, 'text') or '')
        return str(res)

    def _decode(self, data):
        for enc in ('utf-8', 'gbk', 'gb18030'):
            try:
                txt = data.decode(enc)
                if '锟斤拷' not in txt and '\ufffd' not in txt:
                    return txt
            except Exception:
                pass
        try:
            return data.decode('utf-8', errors='ignore')
        except Exception:
            return ''

    def _abs(self, url):
        if not url:
            return ''
        if str(url).startswith('magnet:'):
            return url
        return urljoin(self.host + '/', str(url).replace('&amp;', '&'))

    def _clean(self, text):
        text = re.sub(r'<script[\s\S]*?</script>|<style[\s\S]*?</style>', '', str(text or ''), flags=re.I)
        text = re.sub(r'<[^>]+>', ' ', text)
        text = unescape(text)
        text = re.sub(r'"?>\s*', ' ', text)
        text = re.sub(r'[\ue000-\uf8ff]', '', text)
        return re.sub(r'\s+', ' ', text).strip()

    def _first(self, patterns, html, default=''):
        for pat in patterns:
            m = re.search(pat, html or '', flags=re.I)
            if m:
                return self._clean(m.group(1))
        return default

    def _year(self, text):
        m = re.search(r'\b((?:19|20)\d{2})\b', text or '')
        return m.group(1) if m else ''

    def _parse_list(self, html):
        html = html or ''
        videos = []
        seen = set()
        # 6v 实测列表：<li class="post box row fixed-hight"> ... thumbnail ... h2 ... </li>
        blocks = re.findall(r'<li[^>]+class=["\'][^"\']*\bpost\b[^"\']*["\'][^>]*>[\s\S]*?</li>', html, flags=re.I)
        for block in blocks:
            href = self._first_raw([r'<h2>[\s\S]*?<a[^>]+href=["\']([^"\']+\.html)["\']', r'<a[^>]+href=["\']([^"\']+\.html)["\'][^>]*class=["\'][^"\']*zoom'], block)
            title = self._first_raw([r'<h2>[\s\S]*?<a[^>]*>([\s\S]*?)</a>', r'<h2>[\s\S]*?<a[^>]*title=["\']([^"\']+)["\']', r'<a[^>]*title=["\']([^"\']+)["\']'], block)
            pic = self._first_raw([r'<img[^>]+(?:src|data-original|data-src)=["\']([^"\']+)["\']'], block)
            item = self._item(href, title, pic)
            if item and item['vod_id'] not in seen:
                seen.add(item['vod_id'])
                videos.append(item)
        if videos:
            return videos
        # 兜底：全页 anchor，只收真正详情页，避免导航链接
        for href, inner in re.findall(r'<a\b[^>]*href=["\']([^"\']+\.html)["\'][^>]*>([\s\S]*?)</a>', html, flags=re.I):
            if '/e/' in href or href in ('/', '/index.html'):
                continue
            if not re.search(r'/[A-Za-z0-9_-]+/\d+\.html|/\d+\.html', href):
                continue
            title = self._clean(inner)
            pic = self._first_raw([r'<img[^>]+(?:src|data-original|data-src)=["\']([^"\']+)["\']'], inner)
            item = self._item(href, title, pic)
            if item and item['vod_id'] not in seen:
                seen.add(item['vod_id'])
                videos.append(item)
        return videos

    def _first_raw(self, patterns, text):
        for pat in patterns:
            m = re.search(pat, text or '', flags=re.I)
            if m:
                return m.group(1)
        return ''

    def _item(self, href, title, pic=''):
        title = self._clean(title)
        if not href or len(title) < 2:
            return None
        url = self._abs(href)
        return {'vod_id': url, 'vod_name': title, 'vod_pic': self._abs(pic), 'vod_remarks': self._year(title) or '点击查看'}

    def _parse_detail_lines(self, html):
        lines = []
        h3s = list(re.finditer(r'<h3[^>]*>([^<]*播放地址[^<]*)</h3>', html or '', flags=re.I))
        for i, h3 in enumerate(h3s):
            section = html[h3.start():(h3s[i + 1].start() if i + 1 < len(h3s) else len(html))]
            eps = self._parse_eps(section, play=True)
            if eps:
                lines.append({'name': self._clean(h3.group(1)) or '在线播放', 'episodes': eps})
        if not lines:
            eps = self._parse_eps(html, play=True)
            if eps:
                lines.append({'name': '在线播放', 'episodes': eps})
        idx = (html or '').find('【下载地址】')
        if idx >= 0:
            sec = html[idx:]
            cut_points = [x for x in [sec.find('<h3', 6), sec.find('<div class="widget', 6)] if x > 0]
            if cut_points:
                sec = sec[:min(cut_points)]
            eps = self._parse_eps(sec, play=False)
            if eps:
                lines.append({'name': '下载地址', 'episodes': eps})
        return lines

    def _parse_eps(self, html, play=True):
        eps, seen = [], set()
        if play:
            pat = r'<a\s+(?:[^>]*?\s+)?href\s*=\s*["\']([^"\']*/e/DownSys/play/[^"\']+)["\'][^>]*>(.*?)</a>'
        else:
            pat = r'<a\s+(?:[^>]*?\s+)?href\s*=\s*["\']([^"\']+)["\'][^>]*>(.*?)</a>'
        for href, title in re.findall(pat, html or '', flags=re.I):
            title = self._clean(title)
            if href in seen or not title:
                continue
            if not play and ('#respond' in href or 'category' in href):
                continue
            seen.add(href)
            if not play and (title == '链接' or len(title) < 2):
                low = href.lower()
                title = '夸克网盘' if 'quark' in low else ('迅雷网盘' if 'xunlei' in low else ('磁力链接' if low.startswith('magnet:') else '下载'))
            eps.append({'title': title, 'url': self._abs(href)})
        return eps

    def _resolve_play_url(self, play_url):
        html = self._html(play_url)
        media = self._find_media(html, play_url)
        if media:
            return media
        iframe = re.search(r'<iframe[^>]+src\s*=\s*["\']([^"\']+)["\']', html or '', flags=re.I)
        if iframe:
            iframe_url = urljoin(play_url, iframe.group(1))
            media = self._find_media(self._html(iframe_url), iframe_url)
            if media:
                return media
        return None

    def _find_media(self, html, base_url):
        patterns = [
            r'https?://[^\s"\'<>]+\.(?:m3u8|mp4)[^\s"\'<>]*',
            r'const\s+url\s*=\s*["\']([^"\']+\.(?:m3u8|mp4)[^"\']*)["\']',
            r'url\s*[:=]\s*["\']([^"\']+\.(?:m3u8|mp4)[^"\']*)["\']',
            r'["\']url["\']\s*:\s*["\']([^"\']+\.(?:m3u8|mp4)[^"\']*)["\']',
        ]
        for pat in patterns:
            m = re.search(pat, html or '', flags=re.I)
            if m:
                val = m.group(1) if m.lastindex else m.group(0)
                return urljoin(base_url, val.replace('\\/', '/'))
        return None
