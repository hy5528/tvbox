<?php
$id=$_GET['id'];
$n = [
    "zhonghe" => 31,//广州综合
    "xinwen" => 32,//广州新闻
    "jingsai" => 35,//广州竞赛
    "yingshi" => 36,//广州影视
    "fazhi" => 34,//广州法治
    "shenghuo" => 33,//广州南国都市
    ];
$data = json_decode(file_get_contents("https://gzbn.gztv.com:7443/plus-cloud-manage-app/liveChannel/queryLiveChannelList?type=1"))->data;//id=31-36
$count = count($data);
for($i=0;$i<$count;$i++){
if($data[$i]->stationNumber == $n[$id]){
$playurl = $data[$i]->httpUrl;
break;
}}
header("Location: {$playurl}",true,302);
?>
