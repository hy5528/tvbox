<?php

// 数据库文件路径
$dbPath = 'channel_epg.db';

// 打开或创建SQLite数据库
$db = new SQLite3($dbPath);

// 准备创建表的SQL语句
$createTableSQL = <<<SQL
CREATE TABLE IF NOT EXISTS list (
    item TEXT,
    title TEXT,
    epg TEXT DEFAULT '',  -- epg字段默认为空字符串
    url TEXT,
    isdel INTEGER
);
SQL;
$db->exec($createTableSQL);

// 清空list表
$emptyTableSQL = "DELETE FROM list";
$db->exec($emptyTableSQL);

// 准备查询现有记录的SQL语句
$selectSQL = "SELECT url FROM list WHERE item = :item AND title = :title";
$selectStmt = $db->prepare($selectSQL);

// 准备更新现有记录的SQL语句
$updateSQL = "UPDATE list SET url = :new_url WHERE item = :item AND title = :title";
$updateStmt = $db->prepare($updateSQL);

// 准备插入新记录的SQL语句
$insertSQL = "INSERT INTO list (item, title, epg, url, isdel) VALUES (:item, :title, :epg, :url, :isdel)";
$insertStmt = $db->prepare($insertSQL);

// 网站数据源数组
$dataSources = [
    'https://ghproxy.net/https://github.com/hy5528/tvbox/blob/main/live.txt',
    'http://home.jundie.top:81/Cat/tv/live.txt'
];

// 初始化isdel计数器
$isdelCounter = 1;

foreach ($dataSources as $dataSource) {
    // 获取数据
    $data = file_get_contents($dataSource);

    // 将数据分割成行
    $lines = explode("\n", $data);

    // 当前分类项目
    $currentItem = '';

    foreach ($lines as $line) {
        $line = trim($line);
        if (empty($line)) continue; // 跳过空行

        if (strpos($line, '#genre#') !== false) {
            // 新的分类项目
            $currentItem = str_replace('#genre#', '', $line);
        } else {
            // 分割标题和URL
            $parts = explode(',', $line, 2);
            if (count($parts) == 2) {
                list($title, $url) = $parts;
                $title = trim($title);
                $url = trim($url);

                // 替换标题中的指定字符串
                $title = preg_replace('/CCTV\-(\d+)\s+.*/', 'CCTV$1', $title);
                $title = str_replace('CCTV-5+ 体育赛事', 'CCTV5+', $title); // 特殊处理CCTV-5+
                $title = str_replace('CCTV-4K 超高清', 'CCTV4K', $title); // 替换CCTV-4K
                $title = str_replace('CCTV-8K 超高清', 'CCTV8K', $title); // 替换CCTV-8K

                // 绑定参数并查询现有记录
                $selectStmt->bindValue(':item', $currentItem);
                $selectStmt->bindValue(':title', $title);
                $result = $selectStmt->execute();
                $existingRecord = $result->fetchArray(SQLITE3_ASSOC);

                if ($existingRecord) {
                    // 如果存在记录，则合并URLs
                    $existingUrls = explode('#', $existingRecord['url']);
                    if (!in_array($url, $existingUrls)) {
                        // 只有当URL不在现有URLs中时才合并
                        $newUrl = $existingRecord['url'] . '#' . $url;
                        $updateStmt->bindValue(':new_url', $newUrl);
                        $updateStmt->bindValue(':item', $currentItem);
                        $updateStmt->bindValue(':title', $title);
                        $updateStmt->execute();
                    }
                } else {
                    // 如果不存在记录，则插入新记录
                    $insertStmt->bindValue(':item', $currentItem);
                    $insertStmt->bindValue(':title', $title);
                    $insertStmt->bindValue(':epg', ''); // epg字段为空
                    $insertStmt->bindValue(':url', $url);
                    $insertStmt->bindValue(':isdel', $isdelCounter);
                    $insertStmt->execute();
                }
                
                // 递增isdel计数器
                $isdelCounter++;
            }
        }
    }
}

// 关闭数据库连接
$db->close();

echo "Data processed successfully.";

?>
