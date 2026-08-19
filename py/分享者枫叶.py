# -*- coding: utf-8 -*-
# by @嗷呜
import json
import random
import re
import sys
from urllib.parse import quote
from pyquery import PyQuery as pq
sys.path.append('..')
from base.spider import Spider


class Spider(Spider):

    def init(self, extend='{}'):
        from android.os import Handler, Looper
        self._handler = Handler(Looper.getMainLooper())
        self._toast = None
        pass

    def destroy(self):
        pass

    def getActivity(self):
        from java.lang import Class
        activityThreadClass = Class.forName("android.app.ActivityThread")
        activityThread = activityThreadClass.getMethod("currentActivityThread", None).invoke(None, None)
        activitiesField = activityThreadClass.getDeclaredField("mActivities")
        activitiesField.setAccessible(True)
        activities = activitiesField.get(activityThread)
        if activities is not None:
            values = activities.values()
            try:
                records = values.toArray()
            except:
                records = values.getClass().getMethod("toArray").invoke(values)
            for activityRecord in records:
                try:
                    activityRecordClass = activityRecord.getClass()
                    pausedField = activityRecordClass.getDeclaredField("paused")
                    pausedField.setAccessible(True)
                    if not pausedField.getBoolean(activityRecord):
                        activityField = activityRecordClass.getDeclaredField("activity")
                        activityField.setAccessible(True)
                        return activityField.get(activityRecord)
                except:
                    continue
        return None

    def execute(self, func):
        import threading
        threading.Thread(target=func).start()

    def run(self, func, delay=0):
        from java import dynamic_proxy
        from java.lang import Runnable
        import traceback
        def safe():
            try:
                func()
            except Exception as e:
                self.log("run error: " + str(e))
                self.log(traceback.format_exc())
        if not hasattr(self, '_r_class'):
            class R(dynamic_proxy(Runnable)):
                def __init__(self, fn):
                    super().__init__()
                    self.fn = fn
                def run(self):
                    self.fn()
            self._r_class = R
        if delay > 0:
            self._handler.postDelayed(self._r_class(safe), delay)
        else:
            self._handler.post(self._r_class(safe))

    def show(self, text):
        def make():
            from android.widget import Toast
            if not text: return
            try:
                activity = self.getActivity()
                if not activity: return
                if self._toast is not None: self._toast.cancel()
                self._toast = Toast.makeText(activity, text, Toast.LENGTH_LONG)
                self._toast.show()
            except Exception as e:
                self.log("show error: " + str(e))
        self.run(make)

    Host='https://www.cd-zj.com'

    cookies = {}

    headers = {
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'accept-language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'referer': f'{Host}/',
        'sec-ch-ua': '"Not/A)Brand";v="8", "Chromium";v="148", "Google Chrome";v="148"',
        'sec-ch-ua-mobile': '?1',
        'sec-ch-ua-platform': '"Android"',
        'user-agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36',
    }

    playList=None

    def getList(self, doc):
        vs = []
        for v in doc.items():
            img=v('img');name=v.attr('title')
            if not name:name=img.attr('alt')
            vs.append({
                'vod_id': v.attr('href'),
                'vod_name': name,
                'vod_pic': img.attr('data-src'),
                'vod_remarks': v('.public-list-prb.hide').text()
            })
        return  vs

    def show_captcha_dialog(self, img_bytes, callback=None):
        from java import jclass, dynamic_proxy
        def build():
            try:
                activity = self.getActivity()
                if not activity:
                    return
                BitmapFactory = jclass("android.graphics.BitmapFactory")
                ImageView = jclass("android.widget.ImageView")
                EditText = jclass("android.widget.EditText")
                LinearLayout = jclass("android.widget.LinearLayout")
                AlertDialog = jclass("android.app.AlertDialog")
                OnClickListener = jclass("android.content.DialogInterface$OnClickListener")
                OnDismissListener = jclass("android.content.DialogInterface$OnDismissListener")
                Gravity = jclass("android.view.Gravity")
                ViewGroup = jclass("android.view.ViewGroup")
                bitmap = BitmapFactory.decodeByteArray(img_bytes, 0, len(img_bytes))
                img_view = ImageView(activity)
                img_view.setImageBitmap(bitmap)
                img_view.setAdjustViewBounds(True)
                img_view.setScaleType(ImageView.ScaleType.FIT_CENTER)
                # 宽度撑满弹，高度自适应
                img_params = LinearLayout.LayoutParams(
                    ViewGroup.LayoutParams.MATCH_PARENT, 
                    ViewGroup.LayoutParams.WRAP_CONTENT
                )
                img_params.bottomMargin = 20
                input_et = EditText(activity)
                input_et.setHint("分享者温馨提示:请输入验证码")
                layout = LinearLayout(activity)
                layout.setOrientation(LinearLayout.VERTICAL)
                layout.setPadding(40, 20, 40, 20)
                layout.addView(img_view, img_params)
                layout.addView(input_et)
                outer = self
                dismissed = [False]
                class PositiveListener(dynamic_proxy(OnClickListener)):
                    def onClick(self, dialog, which):
                        dismissed[0] = True
                        code = str(input_et.getText().toString()).strip()
                        dialog.dismiss()
                        if callback:
                            outer.execute(lambda: callback(code))
                class NegativeListener(dynamic_proxy(OnClickListener)):
                    def onClick(self, dialog, which):
                        dismissed[0] = True
                        dialog.dismiss()
                        if callback:
                            outer.execute(lambda: callback(""))
                class DismissListener(dynamic_proxy(OnDismissListener)):
                    def onDismiss(self, dialog):
                        if not dismissed[0]:
                            dismissed[0] = True
                            if callback:
                                outer.execute(lambda: callback(""))
                dialog = AlertDialog.Builder(activity) \
                    .setTitle("分享者红叶验证码") \
                    .setView(layout) \
                    .setPositiveButton("确定", PositiveListener()) \
                    .setNegativeButton("关闭", NegativeListener()) \
                    .create()
                dialog.setOnDismissListener(DismissListener())
                dialog.show()
            except Exception as e:
                self.log("show_captcha_dialog error: " + str(e))
        self.run(build)

    def captcha(self, cookie):
        img_url = f"{self.Host}/captcha.php?type=code&r={random.random()}"
        resp = self.fetch(img_url, headers=self.headers, cookies=cookie)
        rck = resp.cookies.get_dict()

        from java import jclass
        ArrayBlockingQueue = jclass("java.util.concurrent.ArrayBlockingQueue")
        q = ArrayBlockingQueue(1)
        self.show_captcha_dialog(resp.content, lambda code: q.offer(code))
        code = str(q.take())
        if not code:
            self.show("取消验证")
            return
        # POST 验证
        post_url = f"{self.Host}/captcha.php?type=verify"
        verify = self.post(post_url, headers=self.headers, data={'check': code}, cookies=rck)
        self.log(f"验证结果: {verify.text}")
        try:
            data = json.loads(verify.text)
            if data.get('code') != 1:
                self.show("验证失败，请刷新重新验证")
                return
            self.show("验证成功")
            vck = verify.cookies.get_dict()
            vck.update(rck)
            self.cookies = vck
        except Exception as e:
            self.show("验证异常: " + str(e))

    def getHtml(self,url):
        resp=self.fetch(url,headers=self.headers,cookies=self.cookies)
        if "系统安全验证" in resp.text:
            self.captcha(resp.cookies.get_dict())
            resp = self.fetch(url, headers=self.headers, cookies=self.cookies)
        return pq(resp.content)

    def homeContent(self, filter):
        doc=self.getHtml(self.Host)
        cls=doc("div.head-more.none.box.size > a")
        classes=[
            {
                "type_id": c.attr("href").replace('.html', ''),
                "type_name": c.text(),
            } for c in cls.items() if c.attr("href")!="/"
        ]
        vs=doc("div.flex.wrap.border-box .public-list-exp")
        return {"class": classes, "filters": {}, "list": self.getList(vs)}

    def categoryContent(self, tid, pg, filter, extend):
        path=f"/cupfox-list/{tid.replace('/type/', '')}--------{pg}---.html" if "type" in tid else f"{tid}/page/{pg}.html"
        doc=self.getHtml(self.Host+ path)
        vs=doc("div.list-vod.flex.wrap .public-list-exp")
        return {"list": self.getList(vs)}

    def detailContent(self, ids):
        doc=self.getHtml(self.Host+ids[0])
        vod = {
            'vod_name': doc(".slide-info-title.hide").text(),
            'vod_pic': doc("img.lazy.lazy1.mask-1").attr("src"),
            'vod_content': doc(".text.cor3").text(),
        }
        vs = doc("div.detail-info.rel.flex-auto.wow .slide-info.hide")
        for i in vs.items():
            name=i.text()
            i.remove("strong")
            if name=="导演：":
                vod['vod_actor']=i.text()
            elif name=="主演：":
                vod['vod_director']=i.text()
            elif name=="更新 :":
                vod['vod_year']=i.text()
            elif name=="连载 :":
                vod['vod_remarks']=i.text()
        names = list(doc("div.swiper-wrapper .swiper-slide").items())
        urls = list(doc("ul.anthology-list-play.size").items())
        n,p=[],[]
        for i,j in enumerate(names):
            j.remove(".badge")
            n.append(j.text()+f"#{i+1}")
            ps=urls[i]('li')
            s=[
                f"{m.text()}${m('a').attr('href')}"
                for m in reversed(list(ps.items()))
            ]
            p.append('#'.join(s))
        vod['vod_play_from']='$$$'.join(n)
        vod['vod_play_url']='$$$'.join(p)
        return {'list': [vod]}

    def searchContent(self, key, quick, pg="1"):
        url=f"{self.Host}/cupfox-search/-------------.html?wd={quote(key)}"
        doc=self.getHtml(url)
        vs=doc("div.row-right .public-list-exp")
        return {"list": self.getList(vs)}

    def getJx(self,key,path):
        if self.playList is None:
            resp=self.getHtml(self.Host+path).text()
            pattern = r'MacPlayerConfig\.player_list\s*=\s*({.*?}),\s*MacPlayerConfig\.downer_list'
            data_str = re.search(pattern, resp, re.S).group(1)
            self.playList = json.loads(data_str)
        return self.playList.get(key)

    def playerContent(self, flag, id, vipFlags):
        try:
            doc=self.getHtml(self.Host+id)
            script=doc("div.player-left .MacPlayer script")
            aj=json.loads(script.eq(0).text().split("=",1)[-1])
            frmo=self.getJx(aj.get("from"), script.eq(1).attr("src"))
            if frmo.get("ps") == "0":return {"parse": 0, "url": aj.get("url")}
            parse=frmo.get("parse")
            resp=self.fetch(parse+aj.get("url"),headers=self.headers)
            token=pq(resp.content)("#player-data").attr("data-te")
            data=self.post(parse.split("?")[0]+"mplayer.php",headers=self.headers,data={"url":aj.get("url"),"token":token}).json()
            if data.get("code")==200:return {"parse": 0,"url": data.get("url")}
            return {"parse": 1,"url": self.Host+id}
        except  Exception as e:
            print(e)
            return {"parse": 1, "url": self.Host+id}
