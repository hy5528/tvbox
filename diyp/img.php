<?php
/**
 * php抓取bing每日图片并保存到服务器
 * https://www.computer26.com/windows/13146.html , https://blog.csdn.net/weixin_35342955/article/details/115564707
 * http://cn.bing.com/HPImageArchive.aspx?format=js&idx=0&n=1 , https://github.com/mike126126/bing
 * https://www4.bing.com/HPImageArchive.aspx?format=js&idx=0&n=1
 */
error_reporting(1);
$path = 'imgs'; //设置图片缓存文件夹
$isrange = false; //是否随机返回图片
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
	curl_setopt($process, CURLOPT_USERAGENT, "Mozilla/5.0 (Windows NT 5.1; zh-CN) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/30.0.1599.101 Safari/537.36");
	$data = curl_exec($process);
	curl_close($process);
	unset($process);
	return $data;
}

/**
 * 远程抓取图片并保存
 * 
 * @param  $url 图片url
 * @param  $filename 保存名称和路径
 */

function grabImage($url,$path,$filename = "")
{
	if ($url == "")
	{
		return false; //如果$url地址为空，直接退出
	} 
	// 如果没有指定新的文件名
	if ($filename == "")
	{
		$ext = strrchr($url, "."); //得到$url的图片格式
		$filename = date("Ymd") . $ext; //用天月面时分秒来命名新的文件名
	}
	ob_start(); //打开输出
	readfile('http' . substr($url,4,100)); //输出图片文件
	$img = ob_get_contents(); //得到浏览器输出
	ob_end_clean(); //清除输出并关闭
	$size = strlen($img); //得到图片大小
	$fp2 = @fopen($path  . '/' . $filename, "a");

	fwrite($fp2, $img); //向当前目录写入图片文件，并重新命名
	fclose($fp2);

	return $filename; //返回新的文件名
}

/**
 * 随机目录下的图片
 */
function rangeimg($dir = './imgs')
{
	$handle = opendir($dir);
	$imgs = array();
	while ($file = readdir($handle))
	{
		if ($file != "." && $file != ".." && !is_dir($file))
		{
			$imgs[] = $file;
		}
	}
	closedir($handle);
	if (count($imgs) > 0)
	{
		$i = rand(0, (count($imgs) - 1));
		return $imgs[$i];
	}
	else
	{
		return '';
	}
}

$filename = date("Ymd") . '.jpg'; //用年月日来命名新的文件名
// 如果文件不存在，则说明今天还没有进行缓存
if (!file_exists($path . '/' . $filename))
{ 
	// 如果目录不存在
	if (!file_exists($path))
	{
		mkdir($path, 0777); //创建缓存目录
	}

	$url = 'http://cn.bing.com/HPImageArchive.aspx?format=js&idx=0&n=1'; //读取必应api，获得相应数据
	$data = getContent($url);
	if (!is_string($data))
	{
		echo "none. $url <br>" ;
	}
	else
	{
		echo "200  $url <br>" ;
	}
	$str = json_decode($data, true);
	$imgurl = 'https://cn.bing.com' . $str['images'][0]['url']; //获取图片url
	$filename = grabImage($imgurl, $path, $filename); //读取并保存图片
}

if (!$isrange && file_exists($path . '/' . $filename))
{
	$imgurl = $path . '/' . $filename; //图片路径
}
else
{
	$filename = rangeimg($path);
	if ($filename == '')
	{
		$imgurl = 'http://img.infinitynewtab.com/InfinityWallpaper/2_14.jpg'; //默认图片路径
	}
	else
	{
		$imgurl = $path . '/' . $filename;
	}
}
// echo $imgurl;
header("Location: {$imgurl}"); // 跳转至目标图像


?>