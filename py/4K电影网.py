#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
4K影视网 (sta-cafe.com) 爬虫 - TVBox/影视仓 Spider 插件
支持分类浏览、筛选、搜索、详情获取、播放链接解析
"""

import re
import json
import logging
import urllib.parse
import os
import sys
import requests
from bs4 import BeautifulSoup

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
try:
    from base.spider import Spider as BaseSpider
except ImportError:
    BaseSpider = object

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class Spider(BaseSpider):
    """4K影视网爬虫"""

    BASE_URL = "https://www.sta-cafe.com"
    
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }

    CATEGORY_MAP = {
        "1": "动作片",
        "2": "喜剧片",
        "3": "爱情片",
        "4": "科幻片",
        "5": "恐怖片",
        "6": "剧情片",
        "7": "战争片",
        "8": "国产剧",
        "9": "香港剧",
        "10": "韩国剧",
        "11": "欧美剧",
        "12": "台湾剧",
        "13": "日本剧",
        "14": "海外剧",
        "15": "泰国剧",
        "16": "国产动漫",
        "17": "日韩动漫",
        "18": "欧美动漫",
        "19": "港台动漫",
        "20": "海外动漫",
        "21": "大陆综艺",
        "22": "港台综艺",
        "23": "日韩综艺",
        "24": "欧美综艺",
    }

    CATEGORY_PARENT = {
        "1": "电影", "2": "电影", "3": "电影", "4": "电影",
        "5": "电影", "6": "电影", "7": "电影",
        "8": "电视剧", "9": "电视剧", "10": "电视剧", "11": "电视剧",
        "12": "电视剧", "13": "电视剧", "14": "电视剧", "15": "电视剧",
        "16": "动漫", "17": "动漫", "18": "动漫", "19": "动漫", "20": "动漫",
        "21": "综艺", "22": "综艺", "23": "综艺", "24": "综艺",
    }

    SORT_MAP = {
        "0": "最新",
        "1": "最热",
        "2": "评分",
    }

    def __init__(self):
        try:
            super().__init__()
        except Exception:
            pass
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)

    def init(self, extend):
        """初始化"""
        pass

    def getName(self):
        return "4K影视网"

    def _parse_ext(self, ext):
        """解析ext参数，兼容dict和JSON字符串格式"""
        if not ext:
            return {}
        if isinstance(ext, dict):
            return ext
        if isinstance(ext, str):
            try:
                return json.loads(ext)
            except Exception:
                return {}
        return {}

    def _parse_nuxt_data(self, html):
        """解析 Nuxt.js SSR 扁平化数组数据"""
        match = re.search(
            r'<script[^>]*id="__NUXT_DATA__"[^>]*>(.*?)</script>',
            html, re.DOTALL
        )
        if not match:
            scripts = re.findall(r'<script[^>]*>(.*?)</script>', html, re.DOTALL)
            for s in scripts:
                if 'ShallowReactive' in s and ('vodName' in s or 'typeId' in s):
                    start = s.find('[')
                    end = s.rfind(']') + 1
                    if start >= 0 and end > start:
                        try:
                            return json.loads(s[start:end])
                        except Exception:
                            pass
            return []
        try:
            return json.loads(match.group(1))
        except Exception as e:
            logger.warning(f"解析Nuxt数据失败: {e}")
            return []

    def _get_val(self, arr, idx):
        """从扁平化数组中获取值，如果idx是数字则索引，否则直接返回"""
        if isinstance(idx, int) and idx < len(arr):
            return arr[idx]
        return idx

    def _resolve_dict(self, arr, d):
        """递归解析字典中的所有索引值"""
        if not isinstance(d, dict):
            return self._get_val(arr, d) if isinstance(d, int) else d
        result = {}
        for k, v in d.items():
            if isinstance(v, int):
                val = self._get_val(arr, v)
                if isinstance(val, dict):
                    result[k] = self._resolve_dict(arr, val)
                elif isinstance(val, list):
                    result[k] = self._resolve_list(arr, val)
                else:
                    result[k] = val
            elif isinstance(v, dict):
                result[k] = self._resolve_dict(arr, v)
            elif isinstance(v, list):
                result[k] = self._resolve_list(arr, v)
            else:
                result[k] = v
        return result

    def _resolve_list(self, arr, lst):
        """递归解析列表中的所有索引值"""
        if not isinstance(lst, list):
            return lst
        result = []
        for item in lst:
            if isinstance(item, int):
                val = self._get_val(arr, item)
                if isinstance(val, dict):
                    result.append(self._resolve_dict(arr, val))
                elif isinstance(val, list):
                    result.append(self._resolve_list(arr, val))
                else:
                    result.append(val)
            elif isinstance(item, dict):
                result.append(self._resolve_dict(arr, item))
            elif isinstance(item, list):
                result.append(self._resolve_list(arr, item))
            else:
                result.append(item)
        return result

    def _find_state_data(self, arr, keyword):
        """从state中查找包含关键字的数据"""
        if len(arr) < 4:
            return None
        state = arr[3]
        if not isinstance(state, dict):
            return None
        for k, v in state.items():
            if keyword in str(k):
                if isinstance(v, int):
                    data = arr[v]
                    if isinstance(data, dict) and 'obj' in data:
                        obj_idx = data['obj']
                        if isinstance(obj_idx, int):
                            return self._resolve_dict(arr, arr[obj_idx])
                    return self._resolve_dict(arr, data) if isinstance(data, dict) else data
        return None

    def homeContent(self, filter=False):
        """首页内容"""
        try:
            url = f"{self.BASE_URL}/"
            resp = self.session.get(url, timeout=30)
            resp.raise_for_status()
            html = resp.text
            arr = self._parse_nuxt_data(html)
            if not arr:
                return {}
            
            classes = []
            for cate_id, cate_name in self.CATEGORY_MAP.items():
                classes.append({
                    "type_id": cate_id,
                    "type_name": cate_name,
                })
            
            return {
                "class": classes,
                "filters": self._get_filters(),
                "list": self._get_home_videos(arr),
            }
        except Exception as e:
            logger.error(f"获取首页失败: {e}")
            return {}

    def homeVideoContent(self):
        """首页视频内容"""
        home = self.homeContent()
        return {"list": home.get("list", [])}

    def _get_home_videos(self, arr):
        """从首页数据中提取推荐视频"""
        videos = []
        seen_ids = set()
        for i, item in enumerate(arr):
            if isinstance(item, dict) and 'vodId' in item and 'vodName' in item:
                vod = self._resolve_dict(arr, item)
                vod_id = str(vod.get('vodId', ''))
                if vod_id and vod_id not in seen_ids:
                    seen_ids.add(vod_id)
                    videos.append({
                        "vod_id": vod_id,
                        "vod_name": vod.get('vodName', ''),
                        "vod_pic": vod.get('vodPic', ''),
                        "vod_remarks": vod.get('vodLastRemarks', ''),
                    })
                if len(videos) >= 36:
                    break
        return videos

    def _get_filters(self):
        """获取筛选配置"""
        filters = {}
        for cate_id in self.CATEGORY_MAP:
            parent = self.CATEGORY_PARENT.get(cate_id, '')
            siblings = [
                {"n": name, "v": tid}
                for tid, name in self.CATEGORY_MAP.items()
                if self.CATEGORY_PARENT.get(tid) == parent
            ]
            filters[cate_id] = [
                {
                    "key": "type",
                    "name": "类型",
                    "value": [{"n": "全部", "v": ""}] + siblings
                },
                {
                    "key": "sort",
                    "name": "排序",
                    "value": [
                        {"n": "最新", "v": "0"},
                        {"n": "最热", "v": "1"},
                        {"n": "评分", "v": "2"},
                    ]
                },
            ]
        return filters

    def categoryContent(self, tid, pg, filter, ext):
        """分类内容"""
        try:
            page = int(pg) if pg else 1
            type_id = str(tid)
            
            ext_dict = self._parse_ext(ext)
            
            if ext_dict and ext_dict.get('type'):
                type_id = str(ext_dict['type'])
            
            sort = ext_dict.get('sort', '0') if ext_dict else '0'
            
            url = f"{self.BASE_URL}/vodtype/{type_id}"
            if page > 1:
                url += f"/{page}"
            
            resp = self.session.get(url, timeout=30)
            resp.raise_for_status()
            html = resp.text
            arr = self._parse_nuxt_data(html)
            if not arr:
                return {"list": [], "page": page, "pagecount": 1, "limit": 20, "total": 0}
            
            page_data = self._find_state_data(arr, 'type-data-')
            if not page_data or 'data' not in page_data:
                return {"list": [], "page": page, "pagecount": 1, "limit": 20, "total": 0}
            
            data = page_data['data']
            if isinstance(data, int):
                data = self._resolve_dict(arr, arr[data])
            
            total = data.get('total', 0)
            total_page = data.get('total_page', 1)
            per_page = data.get('per_page', 18)
            
            vod_list = []
            vod_recent = data.get('vod_recent', [])
            if isinstance(vod_recent, int):
                vod_recent = arr[vod_recent] if vod_recent < len(arr) else []
                if isinstance(vod_recent, list):
                    resolved = []
                    for idx in vod_recent:
                        if isinstance(idx, int) and idx < len(arr):
                            vod_obj = arr[idx]
                            if isinstance(vod_obj, dict):
                                resolved.append(self._resolve_dict(arr, vod_obj))
                    vod_recent = resolved
            
            if isinstance(vod_recent, list):
                for vod in vod_recent:
                    if isinstance(vod, dict):
                        vod_list.append({
                            "vod_id": str(vod.get('vodId', '')),
                            "vod_name": vod.get('vodName', ''),
                            "vod_pic": vod.get('vodPic', ''),
                            "vod_remarks": vod.get('vodLastRemarks', ''),
                        })
            
            return {
                "list": vod_list,
                "page": page,
                "pagecount": total_page,
                "limit": per_page,
                "total": total,
            }
        except Exception as e:
            logger.error(f"获取分类内容失败: {e}")
            return {"list": [], "page": 1, "pagecount": 1, "limit": 20, "total": 0}

    def detailContent(self, ids):
        """详情内容"""
        try:
            vod_id = ids[0] if isinstance(ids, list) else str(ids)
            url = f"{self.BASE_URL}/voddetail/{vod_id}.html"
            resp = self.session.get(url, timeout=30)
            resp.raise_for_status()
            html = resp.text
            arr = self._parse_nuxt_data(html)
            if not arr:
                return {"list": []}
            
            detail_data = self._find_state_data(arr, 'vod-detail-page-')
            if not detail_data or 'detail' not in detail_data:
                return {"list": []}
            
            detail = detail_data['detail']
            if isinstance(detail, int):
                detail = self._resolve_dict(arr, arr[detail])
            
            vod_play = detail.get('vod_play', [])
            if isinstance(vod_play, int):
                vod_play = arr[vod_play] if vod_play < len(arr) else []
                if isinstance(vod_play, list):
                    resolved = []
                    for idx in vod_play:
                        if isinstance(idx, int) and idx < len(arr):
                            src_obj = arr[idx]
                            if isinstance(src_obj, dict):
                                resolved.append(self._resolve_dict(arr, src_obj))
                    vod_play = resolved
            
            play_from_list = []
            play_url_list = []
            
            if isinstance(vod_play, list):
                for src in vod_play:
                    if isinstance(src, dict):
                        collect_source = src.get('collectSource', {})
                        from_name = ''
                        if isinstance(collect_source, dict):
                            from_name = collect_source.get('webName', '')
                        if not from_name:
                            from_name = src.get('vodRemarks', '播放源')
                        if not from_name:
                            from_name = '播放源'
                        
                        play_url = src.get('vodPlayUrl', '')
                        if play_url:
                            episodes = []
                            # 每集之间用 # 分隔，每集格式为 "集名$链接"
                            # 注意：链接中可能含有 $ 字符，所以只按第一个 $ 分割
                            items = play_url.split('#')
                            for item in items:
                                item = item.strip()
                                if not item:
                                    continue
                                # 按 $ 分割，最多分2段（集名 + 链接）
                                # 但要处理多个 $$$ 的情况（某些源用 $$$ 当分隔符）
                                if '$$$' in item:
                                    # 格式: 集名$$$链接
                                    sub_parts = item.split('$$$', 1)
                                    ep_name = sub_parts[0].strip()
                                    ep_url = sub_parts[1].strip() if len(sub_parts) > 1 else ''
                                    if ep_url:
                                        episodes.append(f"{ep_name}${ep_url}")
                                elif '$' in item:
                                    # 格式: 集名$链接
                                    idx = item.find('$')
                                    ep_name = item[:idx].strip()
                                    ep_url = item[idx+1:].strip()
                                    if ep_url:
                                        episodes.append(f"{ep_name}${ep_url}")
                                    elif ep_name:
                                        episodes.append(f"{ep_name}$")
                                else:
                                    # 只有链接，没有集名
                                    episodes.append(f"第{len(episodes)+1}集${item}")
                            if episodes:
                                play_url_list.append('#'.join(episodes))
                                play_from_list.append(from_name)
            
            vod_item = {
                "vod_id": str(detail.get('vodId', vod_id)),
                "vod_name": detail.get('vodName', ''),
                "vod_pic": detail.get('vodPic', ''),
                "type_name": detail.get('type', {}).get('typeName', '') if isinstance(detail.get('type'), dict) else '',
                "vod_year": str(detail.get('vodYear', '')),
                "vod_area": detail.get('vodArea', ''),
                "vod_remarks": detail.get('vodLastRemarks', ''),
                "vod_actor": detail.get('vodActor', ''),
                "vod_director": detail.get('vodDirector', ''),
                "vod_content": detail.get('vodContent', '') or detail.get('vodBlurb', ''),
                "vod_play_from": '$$$'.join(play_from_list),
                "vod_play_url": '$$$'.join(play_url_list),
            }
            
            return {"list": [vod_item]}
        except Exception as e:
            logger.error(f"获取详情失败: {e}")
            return {"list": []}

    def playerContent(self, flag, id, vipFlags):
        """播放内容 - 直接返回m3u8链接"""
        try:
            play_url = urllib.parse.unquote(id) if id else ''
            return {
                "parse": 0,
                "url": play_url,
            }
        except Exception as e:
            logger.error(f"解析播放失败: {e}")
            return {"parse": 0, "url": ""}

    def searchContent(self, key, quick, pg):
        """搜索内容"""
        try:
            page = int(pg) if pg else 1
            encoded_key = urllib.parse.quote(key)
            url = f"{self.BASE_URL}/vodsearch/{encoded_key}"
            if page > 1:
                url += f"/{page}"
            
            resp = self.session.get(url, timeout=30)
            resp.raise_for_status()
            html = resp.text
            arr = self._parse_nuxt_data(html)
            if not arr:
                return {"list": [], "page": page, "pagecount": 1, "limit": 20, "total": 0}
            
            search_data = self._find_state_data(arr, 'search-page-data-')
            if not search_data or 'data' not in search_data:
                return {"list": [], "page": page, "pagecount": 1, "limit": 20, "total": 0}
            
            data = search_data['data']
            if isinstance(data, int):
                data = self._resolve_dict(arr, arr[data])
            
            total = data.get('total', 0)
            total_page = data.get('total_page', 1)
            per_page = data.get('per_page', data.get('page_size', 18))
            
            vod_list = []
            vod_recent = data.get('vod_recent', data.get('vods', []))
            if isinstance(vod_recent, int):
                vod_recent = arr[vod_recent] if vod_recent < len(arr) else []
                if isinstance(vod_recent, list):
                    resolved = []
                    for idx in vod_recent:
                        if isinstance(idx, int) and idx < len(arr):
                            vod_obj = arr[idx]
                            if isinstance(vod_obj, dict):
                                resolved.append(self._resolve_dict(arr, vod_obj))
                    vod_recent = resolved
            
            if isinstance(vod_recent, list):
                for vod in vod_recent:
                    if isinstance(vod, dict):
                        vod_list.append({
                            "vod_id": str(vod.get('vodId', '')),
                            "vod_name": vod.get('vodName', ''),
                            "vod_pic": vod.get('vodPic', ''),
                            "vod_remarks": vod.get('vodLastRemarks', ''),
                        })
            
            return {
                "list": vod_list,
                "page": page,
                "pagecount": total_page,
                "limit": per_page,
                "total": total,
            }
        except Exception as e:
            logger.error(f"搜索失败: {e}")
            return {"list": [], "page": 1, "pagecount": 1, "limit": 20, "total": 0}


def main():
    """测试用例"""
    spider = Spider()
    
    print("=" * 60)
    print("【1】测试首页")
    print("=" * 60)
    home = spider.homeContent()
    print(f"分类数量: {len(home.get('class', []))}")
    for c in home.get('class', [])[:5]:
        print(f"  - {c['type_name']} ({c['type_id']})")
    print(f"推荐视频数: {len(home.get('list', []))}")
    
    print("\n" + "=" * 60)
    print("【2】测试分类列表 (动作片)")
    print("=" * 60)
    cat = spider.categoryContent("1", "1", False, {})
    print(f"总数: {cat.get('total')}")
    print(f"总页数: {cat.get('pagecount')}")
    print(f"当前页: {cat.get('page')}")
    print(f"本页视频数: {len(cat.get('list', []))}")
    for v in cat.get('list', [])[:5]:
        print(f"  - {v['vod_name']} [{v['vod_remarks']}]")
    
    print("\n" + "=" * 60)
    print("【3】测试详情页")
    print("=" * 60)
    if cat.get('list'):
        first_id = cat['list'][0]['vod_id']
        detail = spider.detailContent([first_id])
        if detail.get('list'):
            d = detail['list'][0]
            print(f"标题: {d['vod_name']}")
            print(f"年份: {d['vod_year']}")
            print(f"地区: {d['vod_area']}")
            print(f"演员: {d['vod_actor'][:50]}...")
            print(f"播放源数量: {len(d['vod_play_from'].split('$$$')) if d['vod_play_from'] else 0}")
            print(f"播放源: {d['vod_play_from'][:80]}...")
    
    print("\n" + "=" * 60)
    print("【4】测试搜索")
    print("=" * 60)
    search = spider.searchContent("逆风草", False, "1")
    print(f"搜索结果数: {search.get('total')}")
    for v in search.get('list', [])[:5]:
        print(f"  - {v['vod_name']} [{v['vod_remarks']}]")
    
    print("\n" + "=" * 60)
    print("测试完成!")
    print("=" * 60)


if __name__ == "__main__":
    main()
