<?php
$id=isset($_GET['id'])?$_GET['id']:'cctv1';

$hostname = 'liveali-tpgq.cctv.cn';

// 获取域名的 IPv4 地址
$ip = gethostbyname($hostname);

// 构建 URL
$url = "http://{$ip}/liveali-tpgq.cctv.cn/live/" . $id .".m3u8";

header('location:'   . $url);

?>