var rule = {
    title: '哔哩音乐[官]',
    host: 'https://api.bilibili.com',
    url: '/fyclass-fypage&vmid=$vmid',
    detailUrl: '/pgc/view/web/season?season_id=fyid',
    filter_url: 'fl={{fl}}',
    searchUrl: '/x/web-interface/search/type?keyword=**&page=fypage&search_type=media_bangumi&search_type=media_ft',
    searchable: 1,
    filterable: 1,
    quickSearch: 0,

    // 屏蔽地址
    blocked_urls: [
       'http://lie.yuyun4kmaopan.qijiyun.vip/d/ty/923241268797768768/video_260803_125610.mp4',
       'http://mlwl.7766.org:91/qf.mp4',
       'https://raw.giteeusercontent.com/nm_nm/interface/raw/master/ips/ips(20250418105556)_000.ts',
       'https://gitee.com/nm_nm/interface/raw/master/ips/ips(20250418105556)_001.ts',
        'IP使用次数超限，请加群签到.mp4'
    ],

    headers: {
        'User-Agent': 'PC_UA',
        'Referer': 'https://www.bilibili.com'
    },
    tab_order: ['哔哩哔哩'],
    timeout: 5000,
    class_name: '粤语&热榜&抖音神曲&无损音乐&经典合集&经典老歌&全部',
    class_url: '1&2&3&4&5&6&全部&综合排序&最新发布&时间表',

    filter: {
        "全部": [
            {"key": "tid", "name": "分类", "value": [
                {"n": "粤语", "v": "1"},
                {"n": "热榜", "v": "2"},
                {"n": "抖音神曲", "v": "3"},
                {"n": "无损音乐", "v": "4"},
                {"n": "经典合集", "v": "5"},
                {"n": "经典老歌", "v": "6"}
            ]},
            {"key": "order", "name": "排序", "value": [
                {"n": "综合排序", "v": "2"},
                {"n": "最新发布", "v": "0"},
                {"n": "最高评分", "v": "4"},
                {"n": "弹幕数量", "v": "1"},
                {"n": "追看人数", "v": "3"}
            ]},
            {"key": "season_status", "name": "付费", "value": [
                {"n": "全部", "v": "-1"},
                {"n": "免费", "v": "1"},
                {"n": "付费", "v": "2%2C6"},
                {"n": "大会员", "v": "4%2C6"}
            ]}
        ],
        "时间表": [
            {"key": "tid", "name": "分类", "value": [
                {"n": "全部", "v": "1"},
                {"n": "10分钟以下", "v": "4"}
            ]}
        ]
    },
    play_parse: true,

    lazy: $js.toString(() => {
        let apiList = [
            "http://niubi.69mini.com/api/?key=09a74556faba7e3b528d64b9c9a86a61&url=",
           "http://103.236.72.166:188/api/?key=veniDOaEzSzIThZsyb&url=",
            'https://jx.xmflv.com/?url='
        ];

        let danmakuUrls = ['https://api.bilibili.com/x/v1/dm/list.so?oid='];

        // 内部解析函数 - 用于epid_cid格式
        function parseInternal(ids, danmaku) {
            let url = "https://api.bilibili.com/pgc/player/web/playurl?qn=116&ep_id=" + ids[0] + "&cid=" + ids[1];
            let html = request(url);
            let jRoot = JSON.parse(html);

            if (jRoot["message"] !== "success") {
                print("需要大会员权限或解析失败");
                // 返回空，让外部使用通用解析
                return null;
            }

            let jo = jRoot["result"];
            let ja = jo["durls"];
            let maxSize = -1, position = -1;
            for (let i = 0; i < ja.length; i++) {
                if (maxSize < Number(ja[i]["size"])) {
                    maxSize = Number(ja[i]["size"]);
                    position = i;
                }
            }
            return {
                "parse": 0,
                "url": ja[position === -1 ? 0 : position]["url"],
                "header": {"Referer": "https://www.bilibili.com", "User-Agent": "Mozilla/5.0"},
                "contentType": "video/x-flv",
                "danmaku": danmaku
            };
        }

        // 解析外部链接
        function parseExternal(targetUrl) {
            let idx = 0;

            // 检查屏蔽地址
            function isBlocked(url) {
                if (!url) return false;
                for (let i = 0; i < rule.blocked_urls.length; i++) {
                    if (url.indexOf(rule.blocked_urls[i]) !== -1) {
                        return true;
                    }
                }
                return false;
            }

            function doParse() {
                if (idx >= apiList.length) {
                    print("所有解析接口都失败");
                    input = "";
                    return;
                }

                let apiUrl = apiList[idx] + encodeURIComponent(targetUrl);
                print("尝试解析接口" + (idx + 1));

                try {
                    let response = fetch(apiUrl);

                    if (!response || response.length < 10) {
                        print("接口" + (idx + 1) + "无响应");
                        idx++;
                        doParse();
                        return;
                    }

                    let playUrl = '';

                    try {
                        let data = JSON.parse(response);
                        playUrl = data.url || data.playUrl || data.data || data.m3u8;
                    } catch (e) {
                        if (response.startsWith('http')) {
                            playUrl = response;
                        }
                    }

                    // 检查是否是屏蔽地址
                    if (playUrl && isBlocked(playUrl)) {
                        print("接口" + (idx + 1) + "返回屏蔽地址，跳过");
                        idx++;
                        doParse();
                        return;
                    }

                    if (playUrl && playUrl.startsWith('http') && playUrl.length > 10) {
                        print("接口" + (idx + 1) + "成功");

                        let danmaku = '';
                        try {
                            let bvMatch = targetUrl.match(/BV[\w]+/);
                            if (bvMatch) {
                                let bvInfo = fetch('https://api.bilibili.com/x/web-interface/view?bvid=' + bvMatch[0]);
                                let bvJson = JSON.parse(bvInfo);
                                if (bvJson.code === 0 && bvJson.data && bvJson.data.cid) {
                                    danmaku = danmakuUrls[0] + bvJson.data.cid;
                                }
                            }
                        } catch (e) {}

                        input = {
                            "parse": 0,
                            "url": playUrl,
                            "header": {"Referer": "https://www.bilibili.com", "User-Agent": "Mozilla/5.0"},
                            "danmaku": danmaku
                        };
                        return;
                    } else {
                        print("接口" + (idx + 1) + "无效");
                        idx++;
                        doParse();
                        return;
                    }
                } catch (e) {
                    print("接口" + (idx + 1) + "失败: " + e.message);
                    idx++;
                    doParse();
                    return;
                }
            }

            doParse();
        }

        if (/^http/.test(input)) {
            parseExternal(input.split("?")[0]);
        } else {
            let ids = input.split("_");
            let dan = danmakuUrls[0] + ids[1];
            let result = parseInternal(ids, dan);
            if (result) {
                input = result;
            } else {
                // 内部解析失败，使用外部解析
                let url = "https://www.bilibili.com/bangumi/play/ep" + ids[0];
                parseExternal(url);
            }
        }
    }),

    limit: 5,
    推荐: 'js:let d=[];function get_result(url){let videos=[];let html=request(url);let jo=JSON.parse(html);if(jo["code"]===0){let vodList=jo.result?jo.result.list:jo.data.list;vodList.forEach(function(vod){let aid=(vod["season_id"]+"").trim();let title=vod["title"].trim();let img=vod["cover"].trim();let remark=vod.new_ep?vod["new_ep"]["index_show"]:vod["index_show"];if(!title.includes("预告")){videos.push({vod_id:aid,vod_name:title,vod_pic:img,vod_remarks:remark})}})}return videos}function get_rank(tid,pg){return get_result("https://api.bilibili.com/pgc/web/rank/list?season_type="+tid+"&pagesize=20&page="+pg+"&day=3")}function get_rank2(tid,pg){return get_result("https://api.bilibili.com/pgc/season/rank/web/list?season_type="+tid+"&pagesize=20&page="+pg+"&day=3")}function home_video(){let videos=get_rank(1).slice(0,5);[4,2,5,3,7].forEach(function(i){videos=videos.concat(get_rank2(i).slice(0,5))});return videos}VODS=home_video();',
    一级: 'js:let d=[];let vmid=input.split("vmid=")[1].split("&")[0];function get_result(url){let videos=[];let html=request(url);let jo=JSON.parse(html);if(jo["code"]===0){let vodList=jo.result?jo.result.list:jo.data.list;vodList.forEach(function(vod){let aid=(vod["season_id"]+"").trim();let title=vod["title"].trim();let img=vod["cover"].trim();let remark=vod.new_ep?vod["new_ep"]["index_show"]:vod["index_show"];if(!title.includes("预告") && !remark.includes("预告")){videos.push({vod_id:aid,vod_name:title,vod_pic:img,vod_remarks:remark})}})}return videos}function get_rank(tid,pg){return get_result("https://api.bilibili.com/pgc/web/rank/list?season_type="+tid+"&pagesize=20&page="+pg+"&day=3")}function get_rank2(tid,pg){return get_result("https://api.bilibili.com/pgc/season/rank/web/list?season_type="+tid+"&pagesize=20&page="+pg+"&day=3")}function get_zhui(pg,mode){let url="https://api.bilibili.com/x/space/bangumi/follow/list?type="+mode+"&follow_status=0&pn="+pg+"&ps=10&vmid="+vmid;return get_result(url)}function get_all(tid,pg,order,season_status){let url="https://api.bilibili.com/pgc/season/index/result?order="+order+"&pagesize=20&type=1&season_type="+tid+"&page="+pg+"&season_status="+season_status;return get_result(url)}function get_timeline(tid,pg){let videos=[];let url="https://api.bilibili.com/pgc/web/timeline/v2?season_type="+tid+"&day_before=2&day_after=4";let html=request(url);let jo=JSON.parse(html);if(jo["code"]===0){let videos1=[];let vodList=jo.result.latest;vodList.forEach(function(vod){let aid=(vod["season_id"]+"").trim();let title=vod["title"].trim();let img=vod["cover"].trim();let remark=vod["pub_index"]+"　"+vod["follows"].replace("系列","");if(!title.includes("预告") && !remark.includes("预告")){videos1.push({vod_id:aid,vod_name:title,vod_pic:img,vod_remarks:remark})}});let videos2=[];for(let i=0;i<7;i++){let vodList=jo["result"]["timeline"][i]["episodes"];vodList.forEach(function(vod){if(vod["published"]+""==="0" && !vod["title"].includes("预告")){let aid=(vod["season_id"]+"").trim();let title=vod["title"].trim();let img=vod["cover"].trim();let date=vod["pub_ts"];let remark=date+" "+vod["pub_index"];videos2.push({vod_id:aid,vod_name:title,vod_pic:img,vod_remarks:remark})}})}videos=videos2.concat(videos1)}return videos}function cate_filter(d,cookie){if(MY_CATE==="1"){return get_rank(MY_CATE,MY_PAGE)}else if(["2","3","4","5","7"].includes(MY_CATE)){return get_rank2(MY_CATE,MY_PAGE)}else if(MY_CATE==="全部"){let tid=MY_FL.tid||"1";let order=MY_FL.order||"2";let season_status=MY_FL.season_status||"-1";return get_all(tid,MY_PAGE,order,season_status)}else if(MY_CATE==="追番"){return get_zhui(MY_PAGE,1)}else if(MY_CATE==="追剧"){return get_zhui(MY_PAGE,2)}else if(MY_CATE==="时间表"){let tid=MY_FL.tid||"1";return get_timeline(tid,MY_PAGE)}else{return[]}}VODS=cate_filter();',
    二级: 'js:function zh(num){let p="";if(Number(num)>1e8){p=(num/1e8).toFixed(2)+"亿"}else if(Number(num)>1e4){p=(num/1e4).toFixed(2)+"万"}else{p=num}return p}let html=request(input);let jo=JSON.parse(html).result;let id=jo["season_id"];let title=jo["title"];let pic=jo["cover"];let areas=jo["areas"][0]["name"];let typeName=jo["share_sub_title"];let date=jo["publish"]["pub_time"].substr(0,4);let dec=jo["evaluate"];let remark=jo["new_ep"]["desc"];let stat=jo["stat"];let status="弹幕: "+zh(stat["danmakus"])+"　点赞: "+zh(stat["likes"])+"　投币: "+zh(stat["coins"])+"　追番追剧: "+zh(stat["favorites"]);let score=jo.hasOwnProperty("rating")?"评分: "+jo["rating"]["score"]+"　"+jo["subtitle"]:"暂无评分"+"　"+jo["subtitle"];let vod={vod_id:id,vod_name:title,vod_pic:pic,type_name:typeName,vod_year:date,vod_area:areas,vod_remarks:remark,vod_actor:status,vod_director:score,vod_content:dec};let ja=jo["episodes"].filter(ep=>!ep.title.includes("预告") && !(ep.badge && ep.badge.includes("预告")));let playurls1=[];ja.forEach(function(tmpJo){let link=tmpJo["link"];let part=tmpJo["title"].replace("#","-")+" "+tmpJo["long_title"]+"["+tmpJo["badge"]+"]";playurls1.push(part+"$"+link)});let playUrl=playurls1.join("#");vod["vod_play_from"]="哔哩哔哩";vod["vod_play_url"]=playUrl;VOD=vod;',
    搜索: 'js:let keyword=KEY;let page=MY_PAGE;let v=[];try{function getWbiKeys(){let html=request("https://api.bilibili.com/x/web-interface/nav");let j=JSON.parse(html);let iu=j.data.wbi_img.img_url;let su=j.data.wbi_img.sub_url;return{img_key:iu.split("/").pop().split(".")[0],sub_key:su.split("/").pop().split(".")[0]}}function encWbi(p,k){let t=[46,47,18,2,53,8,23,32,15,50,10,31,58,3,45,35,27,43,5,49,33,9,42,19,29,28,14,39,12,38,41,13,37,48,7,16,24,55,40,61,26,17,0,1,60,51,30,4,22,25,54,21,56,59,6,63,57,62,11,36,20,52,44];let m=t.map(n=>(k.img_key+k.sub_key)[n]).join("").substr(0,32);p.wts=Math.floor(Date.now()/1000);let q=Object.keys(p).sort().map(x=>{let val=p[x].toString().replace(/![\\x27()*]/g,"");return encodeURIComponent(x)+"="+encodeURIComponent(val)}).join("&");return q+"&w_rid="+md5(q+m)}let keys=getWbiKeys();function search(type){let p={keyword:keyword,page:page,page_size:20,platform:"pc",search_type:type,web_location:1430654};let q=encWbi(p,keys);let u="https://api.bilibili.com/x/web-interface/wbi/search/type?"+q;return JSON.parse(request(u))}function add(jo){if(jo.code===0&&jo.data&&jo.data.result){jo.data.result.forEach(function(vod){let title=(vod.title||"").replace(/<[^>]+>/g,"").trim();if(!title.includes("预告")){let aid=(vod.season_id+"").trim();let img=(vod.cover||"").trim();if(img.startsWith("//")){img="https:"+img}let remark=(vod.index_show||"").trim();v.push({vod_id:aid,vod_name:title,vod_pic:img,vod_remarks:remark})}})}}add(search("media_bangumi"));add(search("media_ft"))}catch(e){}VODS=v;'
}
