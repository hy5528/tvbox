
<?php 
// xml2db.php 联网获取xml格式的节目表存如sqlite数据库,为本地提供DIYP epg接口服务
// author: aming.ou
// http://127.0.0.1/xml2db.php       同步xml数据
// http://127.0.0.1/xml2db.php?db=1  仅创建数据库,不同步xml数据
$save_all = 1; // 1 保存全量节目单, 0 仅保存list中频道相关的节目单
$empty_tmp = 1; // 1 入库后清除临时表的数据, 0 保留临时表的数据,建议调测期间设置为0, 调测完毕后修改为1,减少存储空间
$deleteoffset = -8; // 清理xx天前的节目数据
error_reporting(0); // 禁止输出错误提示
$displayname = 'display-name';
$n = 0;
$inserttype = 'ignore'; // replace  or ignore
$db = !empty($_GET["db"]) ? $_GET["db"] : '0';
$start = microtime(true);

class ChannelDB extends SQLite3
{
	function __construct()
	{
		$isnew = 1;
		$f = 'channel_epg.db';
		if (file_exists($f))
		{
			$isnew = 0;
		}
		$this->open($f);
		$this->busyTimeout(60000); // 10 seconds
		if ($isnew > 0)
		{ 
			// 初始化数据库
			$this->exec("BEGIN TRANSACTION;");
			$this->exec("CREATE TABLE 'list' (item text, title text, epg text, url text, isdel integer null default 120,constraint name_pk primary key (item,title,url))");
			$this->exec("CREATE TABLE if not exists 'access_log' (ip_address text, access_time text,url text)");
			$this->exec("CREATE TABLE if not exists 'epg_channel' ( `name` text, `channel_id` text,constraint name_pk primary key (name))");
			$this->exec("CREATE TABLE if not exists 'epg_programme' ( `title` text, `sdate` text, `sstart` text, `sstop` text, `channel` text, `sdesc` text, 'inserttime' text,constraint name_pk primary key (channel,sdate,sstart))");
			$this->exec("CREATE TABLE if not exists 'tmp_epg_channel' ( `name` text, `channel_id` text)");
			$this->exec("CREATE TABLE if not exists 'tmp_epg_programme' ( `title` text, `sdate` text, `sstart` text, `sstop` text, `channel` text, `sdesc` text, 'inserttime' text)"); 
			// 初始化频道表样例数据
			$this->exec("INSERT INTO `list` (`item`,`title`,`epg`,`url`,`isdel`) VALUES ('广东频道','广州综合','','http://nas.jdshipin.com:8801/gztv.php?id=zhonghe','90');");
			$this->exec("INSERT INTO `list` (`item`,`title`,`epg`,`url`,`isdel`) VALUES ('广东频道','广州新闻','','http://nas.jdshipin.com:8801/gztv.php?id=xinwen#http://113.100.193.10:9901/tsfile/live/1000_1.m3u8','90');");
			$this->exec("INSERT INTO `list` (`item`,`title`,`epg`,`url`,`isdel`) VALUES ('直播频道','CCTV2','','http://dbiptv.sn.chinamobile.com/PLTV/88888893/224/3221226195/index.m3u8?0.smil','120');");
			$this->exec("COMMIT;");
		}
	}
}
// 连接数据库
$config = array();
$channel = new ChannelDB();
// 开始事务处理
$channel->exec("BEGIN TRANSACTION;");
// ==========写入访问日志开始=========
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
$channel->exec("INSERT or ignore INTO access_log (ip_address,access_time,url) VALUES ('{$ip}','{$time}','{$source_link}');");
// ==========写入访问日志结束=========
if ( $db != '0' ){
	echo "only create db. please run again.";
	$channel->exec("INSERT or ignore INTO access_log (ip_address,access_time,url) VALUES ('{$ip}','{$time}','Create database');");
	exit;	
}
// 获取网页数据
function getContent($url)
{
	$process = curl_init($url);
	curl_setopt($process, CURLOPT_RETURNTRANSFER, 1);
	curl_setopt($process, CURLOPT_CONNECTTIMEOUT, 5); 
	curl_setopt($process, CURLOPT_TIMEOUT, 45); 
	// 设置启用SSL协议
	if (strtoupper(substr($url, 0, 5)) == 'HTTPS')
	{
		curl_setopt($process, CURLOPT_SSL_VERIFYPEER, 0);
		curl_setopt($process, CURLOPT_SSL_VERIFYHOST, 0);
	} 
	// 设置GZIP压缩
	$isgz = false;
	if (strtoupper(substr($url, -3)) == '.GZ')
	{
		curl_setopt($process, CURLOPT_ENCODING, 'gzip');
		$isgz = true;
	}
	curl_setopt($process, CURLOPT_USERAGENT, "Mozilla/5.0 (Windows NT 5.1; zh-CN) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/30.0.1599.101 Safari/537.36");
	$data = curl_exec($process);
	if (curl_errno($process))
	{
		echo curl_errno($process) . curl_error($process) . "<br>";
	}
	curl_close($process);
	if ($isgz)
	{
		$data = gzdecode($data);
	}
	unset($process);
	return $data;
}

// 节目总表地址列表
// $xmlurl = array("https://epg.erw.cc/e.xml.gz"); //openssl
// $xmlurl = array("http://epg.51zmt.top:8000/e.xml"); //当天51zmt央卫数 节目单
// $xmlurl = array("http://epg.51zmt.top:8000/e.xml", "http://epg.erw.cc/e.xml", "http://epg.112114.xyz/pp.xml"); //当天 央卫数 节目单
// $xmlurl = array("http://epg.51zmt.top:8000/cc.xml", "http://epg.erw.cc/cc.xml", "http://epg.112114.xyz/pp.xml"); //当天 央卫 节目单
$xmlurl = array("http://epg.112114.xyz/pp.xml.gz", "http://epg.51zmt.top:8000/e.xml.gz", "http://epg.erw.cc/e.xml.gz"); //gzip模式
// .
// 遍历xmlurl,同步epg xml数据源
foreach ($xmlurl as $url)
{ 
	// 清空临时表
	$channel->exec("delete from tmp_epg_channel");
	$channel->exec("delete from tmp_epg_programme"); 
	// 获取xml格式的节目单
	$data = getContent($url);
	if (!is_string($data))
	{
		echo "none. $url <br>" ;
		continue;
	}
	else
	{
		echo "200  $url <br>" ;
	} 
	// 解析xml数据
	$xml = simplexml_load_string($data);
	foreach ($xml->children() as $xmldata)
	{
		if ($xmldata->getName() == "channel")
		{
			$result = $channel->query("INSERT INTO tmp_epg_channel(name,channel_id) VALUES ('" . $xmldata->$displayname . "','" . $xmldata->attributes()->id . "')");

			if (!$result)
			{
				echo $n . ' - ' . $channel->lastErrorMsg() . '<br>';
			}
		}

		if ($xmldata->getName() == "programme")
		{
			$start_time = substr($xmldata->attributes()->start, 8, 2) . ":" . substr($xmldata->attributes()->start, 10, 2);
			$stop_time = substr($xmldata->attributes()->stop, 8, 2) . ":" . substr($xmldata->attributes()->stop, 10, 2);
			$jm_date = substr($xmldata->attributes()->stop, 0, 4) . "-" . substr($xmldata->attributes()->stop, 4, 2) . "-" . substr($xmldata->attributes()->stop, 6, 2);
			$n ++ ;

			$replacement = str_replace("'", " ", $xmldata->title);
			$sql = "INSERT INTO tmp_epg_programme(channel,sdate,sstart,sstop,title,sdesc,inserttime) VALUES ('" . $xmldata->attributes()->channel . "','" . $jm_date . "','" . $start_time . "','" . $stop_time . "','" . $replacement . "','','" . $time . "')";
			$result = $channel->query($sql);

			if (!$result)
			{
				echo $n . ' = ' . $channel->lastErrorMsg() . '<br>'; 
				// echo  $xmldata->title . "<br>";
			}
		}
	} 
	// 更新节目数据
	if ($n > 0)
	{ 
		// 写入日志
		$channel->exec("INSERT INTO access_log (ip_address,access_time,url) VALUES ('xml2db_ini','{$time}','{$n}');"); 
		// 把直播源list的频道追加/更新到epg频道表
		$channel->exec("insert or ignore into epg_channel select upper(a.name) as name ,upper(a.name) as channel_id from tmp_epg_channel a where upper(name) in (select upper(title) from list);"); 
		// 根据条件是否保存全量epg频道表
		$count = $channel->querySingle("SELECT count(*) FROM 'list'");
		if ($count == 0 or $save_all == 1)
		{
			$channel->exec("insert or ignore into epg_channel SELECT upper(a.name) as name ,upper(a.name) as channel_id FROM tmp_epg_channel a;");
		} 
		// 统计原节目单条目数
		$count = $channel->querySingle("SELECT count(*) FROM 'epg_programme'"); 
		// 追加节目单到epg_programme
		$channel->exec("insert or {$inserttype} into epg_programme SELECT c.title,c.sdate,c.sstart,c.sstop,upper(a.name) as channel,c.sdesc,c.inserttime FROM epg_channel a join tmp_epg_channel b on upper(a.name) = upper(b.name) join tmp_epg_programme c on b.channel_id= c.channel;"); 
		// 统计节目单增加条目数
		$count = $channel->querySingle("SELECT count(*) FROM 'epg_programme'") - $count;
		$channel->exec("INSERT INTO access_log (ip_address,access_time,url) VALUES ('xml2db_add','{$time}','{$count}');");
		echo "done, add " . $count . '<br>'; 
		// 清理历史数据
		// $currentDate = date('Y-m-d'); // 获取当前日期
		$currentDate = $channel->querySingle("SELECT max(sdate) FROM 'epg_programme'");
		$currentDate = (strtotime($currentDate) > strtotime(date("Y-m-d"))) ? date("Y-m-d") : $currentDate;
		$newDate = strtotime($currentDate) + ($deleteoffset * 24 * 60 * 60);
		$formattedNewDate = date('Y-m-d', $newDate);
		echo 'epg_programme dates:' . $currentDate . ' <- ' . $formattedNewDate . '<br>';
		$channel->exec("delete from `epg_programme` where sdate < '{$formattedNewDate}';");
		echo 'Delete ' . $channel->changes() . ' records from epg_programme <br>';
		if ($empty_tmp == 1)
		{ 
			// 清空临时表
			$channel->exec("delete from tmp_epg_channel");
			$channel->exec("delete from tmp_epg_programme");
		}
	}
	else
	{
		echo "none.";
	}
}
$executionTime = number_format(microtime(true) - $start, 4);
$channel->exec("INSERT INTO access_log (ip_address,access_time,url) VALUES ('xml2db_cost','{$time}','{$executionTime}');");
// 写入硬盘
$channel->exec("COMMIT;");
$channel->close();
echo 'fetch xml epg data total cost ' . $executionTime . ' s.';

?>
