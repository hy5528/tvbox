<?php 
// json.php 返回超级直播json格式的频道接口数据
// author: aming.ou
// http://127.0.0.1/json.php
class ChannelDB extends SQLite3
{
	function __construct()
	{
		$this->open("channel_epg.db");
	}
}
$config = array();
$channel = new ChannelDB();
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
	$group = $row[0];
	if ($group == '')
	{
		$group = '默认';
	}
	@$item = $config[$group];
	if (!isset($item))
	{
		$item = array();
		$config[$group] = array();
	}
	array_push($config[$group], array('epg' => $row[2],
			'title' => $row[1],
			'url' => $row[3]
			));
}
$info = htmlspecialchars_decode($info);
$info = html_entity_decode($info);

header("Content-Type: application/json"); 
echo json_encode($config, JSON_UNESCAPED_UNICODE);
// echo json_encode($config);

?>
