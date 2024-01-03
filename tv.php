<?php 
header('Content-Type:text/plain');
$hf=substr($_GET["hf"]??date('YmdHi'),-6);
$r= str_split($hf,2);
$hff=time()-strtotime("".date('Y-m-')."$r[0] $r[1]:$r[2]:00")+100;
$hff=intval($hff/60);
$url="http://cfss.cc/ds/bst/bst.php?cdn=ts-gitv-sx-yh.189smarthome.com&hf=$hff&vid=cctv1hd8m/8000000&Bst.m3u8";
header("Location:$url");
exit; 
?>