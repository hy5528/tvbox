<?php 
// m3u.php 返回m3u格式的频道接口数据
// author: aming.ou
// http://127.0.0.1/m3u.php
class ChannelDB extends SQLite3
{
	function __construct()
	{
		$this->open("channel_epg.db");
	}
}
$config = array();
$channel = new ChannelDB();
$group = 'xxxxx'; 
// 当前IP
$ip = $_SERVER['REMOTE_ADDR'];
$time = date("Y-m-d H:i:s"); 
// 当前url
$url = $_SERVER['HTTP_HOST'] . $_SERVER['REQUEST_URI']; 
// 获取最后来源地址
if (empty($_SERVER['HTTP_REFERER']))
{
	$source_link = $url;
}
else
{
	$source_link = $_SERVER['HTTP_REFERER'];
}
$source_link = urldecode($source_link);
// 将IP地址记录到日志文件或数据库中
$result = $channel->query("INSERT or ignore INTO access_log (ip_address,access_time,url) VALUES ('{$ip}','{$time}','{$source_link}');");

$result = $channel->query('select * from list where isdel > 0 order by isdel;');
while ($row = $result->fetchArray())
{
	$config[] = ['item' => $row[0], 'title' => sprintf("%s", $row[1]), 'url' => sprintf("%s", $row[3])];
}
$groupconfig = array_reduce($config, function($result, $item)
	{
		$gender = $item['item'];
		if (!isset($result[$gender]))
		{
			$result[$gender] = [];
		}
		$result[$gender][] = $item;
		return $result;
	}, []);

function gentxt($groupconfig)
{
	$config = array();
	foreach ($groupconfig as $item => $titles)
	{
		$config[] = sprintf("%s,#genre#", $item);
		foreach ($titles as $k => $v)
		{
			$config[] = $v['title'] . ',' . $v['url'];
		}
	}
	echo implode(PHP_EOL, $config);
}
function genm3u($groupconfig)
{
	$config = array();
	$config[] = '#EXTM3U x-tvg-url="http://epg.51zmt.top:8000/e.xml"';
	foreach ($groupconfig as $item => $titles)
	{
		foreach ($titles as $k => $v)
		{
			$text = strtoupper($v['title']);
			if (strpos($text, "CCTV") >= 0 && strpos($text, "清") > 0)
			{
				preg_match_all("/^[A-Za-z0-9-+]+/", $text, $matches);
				$text = str_replace('-', '', $matches[0][0]);
			}elseif (preg_match("/^[A-Za-z0-9-+]+/", $text))
			{
				$text = str_replace('-', '', $text);
			}
			if (strpos($text, "[") > 0)
			{
				$text = substr($text, 0, strpos($text, "["));
			}
			$config[] = sprintf('#EXTINF:-1 tvg-name="%s" tvg-logo="" group-title="%s",%s', $text, $item, $v['title']);
			$config[] = $v['url'];
		}
	}
	echo implode(PHP_EOL, $config);
}

genm3u($groupconfig);
// echo iconv("UTF-8",'UCS-2BE',implode(PHP_EOL, $config));

?>