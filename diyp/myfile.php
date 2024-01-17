<?php
error_reporting(1);
session_start();
/**
 * SuExplorer.php
 * 在线php/ini/conf/sh等脚本文件编辑器, 不依赖ftp和服务器帐号(单页绿色文件,方便部署)
 * @since 1.0 <2015-5-11> SoChishun <14507247@qq.com> Added.
 * @since 2.0 <2015-7-24> SoChishun 
 *      1.重命名为SuExplorer.php
 *      2.改进若干外观样式
 *      3.新增登录验证模块
 *      4.新增删除功能
 * @since 3.0 <2015-10-7> SoChishun
 *      1.新增在线压缩和解压功能
 *      2.新增chomd权限设置功能
 *      3.新增rename重命名功能
 *      4.新增新建文件和目录功能
 *      5.类SuFileEditor重构为SuExplorer,类方法改为静态方法
 *      6.新增主配置文件功能
 *      7.重构页面逻辑，改为脚本混合代码，便于阅读
 *      8.基于绝对路径操作改为基于网站根目录的相对路径操作
 *  @since 3.1 <2016-9-13> SoChishun
 *      1. 新增文件上传功能
 * @since 3.2 <2017-8-23> SoChishun
 *      1. 修正无法查看脚本文件的问题
 *      2. 对html输出增加htmlspecialchars过滤功能
 */
// 程序版本号 [2015-10-7] Added.
$version = '3.2';
// session键名 [2015-10-7] Added.
$sess_id = 'sess_suexplorer';

// 权限规则 [2015-10-7] Added.
$prules = array('delfile', 'deldir', 'savefile', 'newfile', 'mkdir', 'renamefile', 'renamedir', 'chomdfile', 'chomddir', 'zip', 'unzip');

// 主配置 [2015-10-7] Added.
$config = array(
    /* 用户配置 */
    'users' => array(
        'admin' => array('admin123', array('allow' => array(), 'forbit' => array()))
    ),
);

// 登录信息 [2015-10-7] Added.
$login_data = isset($_SESSION[$sess_id]) ? $_SESSION[$sess_id] : false;

$action = I('action');
$view = I('view');
$path = I('path', '/'); // urldecode($_GET['path']) $_SERVER['DOCUMENT_ROOT']
$parent_path = path_getdir($path);
switch ($action) {
    case 'login': // 用户登录
        if (!SuExplorer::user_login($config, $sess_id, $msg)) {
            redirect('?r=fail', 1, $msg);
        } else {
            redirect('?r=ok');
        }
        break;
    case 'logout': // 注销登录
        SuExplorer::user_logout($sess_id);
        redirect('?r=ok');
        break;
    case 'del': // 删除路径(文件或目录)
        if (!SuExplorer::act_delete_path($path, $msg)) {
            redirect('?path=' . $path, 1, $msg);
        } else {
            redirect('?path=' . path_getdir($path), 1, '恭喜,操作成功!');
        }
        break;
    case 'savefile': // 保存文件
    case 'save_newfile': // 新建文件
        if (!SuExplorer::act_save_file($msg)) {
            redirect('?path=' . $path, 1, $msg);
        } else {
            redirect('?path=' . $path, 1, '恭喜,操作成功!');
        }
        break;
    case 'save_newdir': // 新建目录
        if (!SuExplorer::act_save_newdir($msg)) {
            redirect('?path=' . $path, 1, $msg);
        } else {
            redirect('?path=' . $path, 1, '恭喜,操作成功!');
        }
        break;
    case 'upload_file': // 上传文件
        if (!SuExplorer::act_upload_file($msg)) {
            redirect('?path=' . $path, 1, $msg);
        } else {
            redirect('?path=' . $path, 1, '恭喜,文件上传成功!');
        }
        break;
    case 'rename_path': // 重命名路径(文件或目录)
        if (!SuExplorer::act_rename_path($msg)) {
            redirect('?path=' . $path, 1, $msg);
        } else {
            redirect('?path=' . pathinfo($path, PATHINFO_DIRNAME), 1, '恭喜,操作成功!');
        }
        break;
    case 'chmod_path': // 修改权限(文件或目录)
        if (!SuExplorer::act_chmod_path($msg)) {
            redirect('?path=' . $path, 1, $msg);
        } else {
            redirect('?path=' . $path, 1, '恭喜,操作成功!');
        }
        break;
    case 'zip': // 压缩
        if (!SuExplorer::act_zip($msg)) {
            redirect('?path=' . $path, 1, $msg);
        } else {
            redirect('?path=' . $path, 1, '恭喜,操作成功!');
        }
        break;
    case 'unzip': // 解压缩
        if (!SuExplorer::act_unzip($msg)) {
            redirect('?path=' . $path, 1, $msg);
        } else {
            redirect('?path=' . $path, 1, '恭喜,操作成功!');
        }
        break;
}
?>
<!DOCTYPE html>
<html>
    <head>
        <meta charset="UTF-8">
        <title>SuExplorer-<?php echo $version ?></title>
        <script src="//code.jquery.com/jquery-1.11.3.min.js"></script>
        <style type="text/css">
            body {font-size:12px; color:#333;}
            a{text-decoration: none;}
            textarea{font-size:12px;line-height:18px; padding:5px;}
            th{font-weight: normal;}
            .userbar a:before{content: '['}
            .userbar a:after{content: ']'}
            .dir-contents{width:1050px; display:table;}
            .dir-contents a{ margin-right:20px;line-height:21px;text-decoration:none;float:left;}
            .blue{color:#0000DB}
            .lightblue{color:#1bd1a5}
            .purple{color:#9900ff}
            .green{color:#009900}
            .red{color:#F00}
            .grey {color:#999;}
            .nav { line-height: 18px;}
            .nav a { color:#333;}
            .nav a:before { content: ' » ' }
            .nav a:first-child:before {content: ''}
            .nav div { color:#CCC; border-bottom:solid 1px #CCC; margin-bottom:5px;}
        </style>
    </head>
    <body>
        <?php if ($login_data): ?>
            <!-- 用户信息栏 -->
            <div class="userbar">
                欢迎您, <?php echo $login_data['user_name'] ?> <a href="?action=logout">注销</a>
                <a href="?view=newfile&path=<?php echo $parent_path ?>">新建文件</a>
                <a href="?view=upload&path=<?php echo $parent_path ?>">上传文件</a>
                <a href="?view=newdir&path=<?php echo $parent_path ?>">新建目录</a>
                <a href="?view=zip&path=<?php echo $parent_path ?>">打包目录</a>
                <a href="?view=unzip&path=<?php echo $parent_path ?>">解压目录</a>
            </div>
            <!-- /用户信息栏 -->
            <!-- 路径栏 -->
            <div>
                <form method="get" action="#" id="frm-path">
                    <input type="text" name="path" value="<?php echo $path ?>" style="width:50%;color:#333;padding:0px 2px;" required="required" />
                    <input type="hidden" id="action" name="action" value="" />
                    <input type="hidden" id="do" name="do" value="" />
                    <button type="submit">转到</button>
                    <button type="button" onclick="return del_cofirm('frm-path', '删除');">删除</button>
                    <button type="button" data-path="<?php echo $path ?>" onclick="go_url(this, 'rename')">重命名</button>
                    <button type="button" data-path="<?php echo $path ?>" onclick="go_url(this, 'chmod')">权限</button>
                </form>
            </div>
            <!-- /路径栏 -->
            <div><?php SuExplorer::index($view, $path) ?></div>
            <!-- 脚本区 -->
            <script type="text/javascript">
                /**
                 * 删除确认
                 * @param {type} form_id
                 * @param {type} act_name
                 * @returns {Boolean}
                 * @since 1.0 <2015-10-7> SoChishun Added.
                 */
                function del_cofirm(form_id, act_name) {
                    if (!confirm('您确定要' + act_name + '吗?')) {
                        return false;
                    }
                    var i = 0;
                    function confirmx() {
                        i++;
                        return confirm(i + '.重要的操作要重复问三遍,您确定要' + act_name + '吗?');
                    }
                    while (i < 3) {
                        if (!confirmx()) {
                            return false;
                        }
                    }
                    document.getElementById("action").value = "del";
                    document.getElementById("do").value = "yes";
                    document.getElementById(form_id).submit();
                }
                /**
                 * 跳转到链接
                 * @param {HtmlButton} btn
                 * @since 1.0 <2015-10-9> SoChishun Added.
                 */
                function go_url(btn, view) {
                    location.href = '?path=' + $(btn).data('path') + '&view=' + view;
                }
            </script>
            <!-- /脚本区 -->
        <?php else: ?>
            <!-- 用户登录表单 -->
            <form method="post">
                <table>
                    <tr><th>用户名：</th><td><input type="text" name="uname" placeholder="用户名" required="required" /></td></tr>
                    <tr><th>密&nbsp;码：</th><td><input type="password" name="upwd" placeholder="密码" required="required" /></td></tr>
                </table>
                <input type="hidden" name="action" value="login" />
                <button type="submit">登录</button> <button type="reset">重置</button>
            </form>
            <!-- /用户登录表单 -->
        <?php endif; ?>
    </body>
</html>
<?php
/* * ****************************************************************************************************
  函数 :)
 * **************************************************************************************************** */

/**
 * 获取浏览器参数
 * @param string $name
 * @param mixed $defv
 * @return mixed
 * @since 1.0 <2015-8-13> SoChishun Added.
 */
function I($name, $defv = '') {
    if (isset($_GET[$name])) {
        return $_GET[$name];
    }
    return isset($_POST[$name]) ? $_POST[$name] : $defv;
}

/**
 * URL重定向
 * @param string $url 重定向的URL地址
 * @param integer $time 重定向的等待时间（秒）
 * @param string $msg 重定向前的提示信息
 * @return void
 * @since 1.0 <2015-10-7> from ThinkPHP
 */
function redirect($url, $time = 0, $msg = '') {
    //多行URL地址支持
    $url = str_replace(array("\n", "\r"), '', $url);
    if (empty($msg))
        $msg = "系统将在{$time}秒之后自动跳转到{$url}！";
    if (!headers_sent()) {
        // redirect
        if (0 === $time) {
            header('Location: ' . $url);
        } else {
            header("refresh:{$time};url={$url}");
            echo($msg);
        }
        exit();
    } else {
        $str = "<meta http-equiv='Refresh' content='{$time};URL={$url}'>";
        if ($time != 0)
            $str .= $msg;
        exit($str);
    }
}

/**
 * 获取文件扩展名类型
 * @param string $exten 扩展名(不带.)
 * @return string
 * @since 1.0 <2015-10-9> SoChishun Added.
 */
function get_exten_catetory($exten) {
    if ($exten) {
        $filetypes = array('zip' => array('zip', 'rar', '7-zip', 'tar', 'gz', 'gzip'), 'doc' => array('txt', 'rtf', 'doc', 'docx', 'ppt', 'pptx', 'xls', 'xlsx', 'wps', 'et'), 'script' => array('php', 'js', 'css', 'c'), 'image' => array('jpg', 'jpeg', 'png', 'gif', 'tiff', 'psd', 'bmp', 'ico'));
        foreach ($filetypes as $catetory => $extens) {
            if (in_array($exten, $extens)) {
                return $catetory;
            }
        }
    }
    return '';
}

/**
 * 绝对路径转相对路径
 * @param string $path
 * @return string
 * @since 1.0 <2015-10-9> SoChishun Added.
 */
function path_ator($path) {
    $root = $_SERVER['DOCUMENT_ROOT'];
    $path = substr($path, strlen($root));
    if ('/' != DIRECTORY_SEPARATOR) {
        $path = str_replace(DIRECTORY_SEPARATOR, '/', $path);
    }
    return $path;
}

/**
 * 相对路径转绝对路径
 * @param string $path
 * @return string
 * @since 1.0 <2015-10-9> SoChishun Added.
 */
function path_rtoa($path) {
    $root = $_SERVER['DOCUMENT_ROOT'];
    if ('/' != DIRECTORY_SEPARATOR) {
        $path = str_replace('/', DIRECTORY_SEPARATOR, $path);
    }
    return $root . $path;
}
function path_rt_oa($path) {
    $root = $_SERVER['DOCUMENT_ROOT'];
    if ('/' != DIRECTORY_SEPARATOR) {
        $path = str_replace('/', DIRECTORY_SEPARATOR, $path);
    }
    return '.' . $path;
}

/**
 * 获取文件的目录地址
 * @param string $path
 * @param boolean $is_r 是否相对路径
 * @return string
 * @since 1.0 <2015-10-9> SoChishun Added.
 */
function path_getdir($path, $is_r = true) {
    if (!$path || is_dir($is_r ? path_rtoa($path) : $path)) {
        return $path;
    }
    return pathinfo($path, PATHINFO_DIRNAME);
}

/**
 * 页面主类
 * @since 1.0 <2015-5-11> SoChishun <14507247@qq.com> Added.
 * @since 3.0 <2015-10-7> SoChishun 重构.
 */
class SuExplorer {

    /**
     * 版本号
     * @var string
     * @since 1.0 <2015-10-7> SoChishun Added.
     */
    CONST VERSION = '3.0.0';

    /**
     * 显示网站目录的项目内容
     * @since 1.0 <2015-5-11> SoChishun Added.
     */
    static function index($view, $path) {
        // 面包屑导航
        self::location_to_breadcrumb($path);
        // 视图显示
        switch ($view) {
            case 'newfile':
                self::view_create_file($path);
                break;
            case 'newdir':
                self::view_create_dir($path);
                break;
            case 'upload':
                self::view_upload_file($path);
                break;
            case 'rename':
                self::view_rename_path($path);
                break;
            case 'chmod':
                self::view_chmod_path($path);
                break;
            case 'zip':
                self::view_zip();
                break;
            case 'unzip':
                self::view_unzip();
                break;
            default:
                // 列出文件
                $sapath = path_rtoa($path);
                if (is_dir($sapath)) {
                    self::view_content_list($path);
                } else if (is_file($sapath)) {
                    self::view_edit_file($path);
                } else {
                    echo '<strong class="red">文件或目录不存在或已删除!</strong>';
                }
                break;
        }
    }

    /**
     * 用户登录操作
     * @param array $config
     * @param string $sess_id
     * @param string $msg 错误消息
     * @return boolean 
     * @since 1.0 <2015-10-9> SoChishun Added.
     */
    static function user_login($config, $sess_id, &$msg = '') {
        if (!$_POST || !isset($_POST['uname'])) {
            $msg = '表单数据无效!';
            return false;
        }
        $uname = $_POST['uname'];
        if (!array_key_exists($uname, $config['users'])) {
            $msg = '用户不存在';
            return false;
        }
        $login_data = $config['users'][$uname];
        if ($login_data[0] != $_POST['upwd']) {
            $msg = '密码错误!';
            return false;
        }
        $_SESSION[$sess_id] = array('user_name' => $uname, 'rules' => isset($login_data[1]) ? $login_data[1] : false);
        return true;
    }

    /**
     * 用户登出操作
     * @param string $sess_id
     * @return boolean 
     * @since 1.0 <2015-10-9> SoChishun Added.
     */
    static function user_logout($sess_id) {
        if (isset($_SESSION[$sess_id])) {
            unset($_SESSION[$sess_id]);
        }
        return true;
    }

    /**
     * 删除路径(文件或目录)
     * @param string $path 路径
     * @param string $msg 错误消息
     * @return boolean|string
     * @since 1.0 <2015-10-7> SoChishun Added.
     * @since 2.0 <2015-10-8> SoChishun 将delete_file和delete_dir合并到delete_path
     */
    static function act_delete_path($path, &$msg = '') {
        if ('yes' != I('do')) {
            // 为防止黑客破坏,删除操作需要手动增加参数do=yes
            $msg = '非法操作!';
            return false;
        }
        if ('/' == $path) {
            $msg = '根目录无法删除!';
            return false;
        }
        $path = path_rtoa($path);
        if (is_file($path)) {
            if (!@unlink($path)) {
                $msg = '文件删除失败!';
                return false;
            }
            return true;
        }
        if (is_dir($path)) {
            if (!@rmdir($path)) {
                $msg = '目录删除失败!(非空目录或权限不足)';
                return false;
            }
            return true;
        }
        $msg = '不是有效文件或目录!';
        return false;
    }

    /**
     * 保存(新)文件
     * @param type $msg
     * @return boolean
     * @since 1.0 <2015-10-7> SoChishun Added.
     */
    static function act_save_file(&$msg = '') {
        $filename = I('filename');
        if (!$filename || !strpos($filename, '.')) {
            $msg = '文件扩展名无效!';
            return false;
        }
        $content = I('content');
        $path = I('path');
        $path = path_rtoa($path);
        if (is_file($path)) {
            $path = path_getdir($path, false);
        }
        $newpath = $path . DIRECTORY_SEPARATOR . $filename;
        try {
            file_put_contents($newpath, $content);
            return true;
        } catch (Exception $ex) {
            $msg = $ex->getMessage();
            return false;
        }
    }

    /**
     * 保存新目录
     * @param string $msg 错误消息
     * @return boolean
     * @since 1.0 <2015-10-8> SoChishun Added.
     */
    static function act_save_newdir(&$msg = '') {
        $filename = I('filename');
        if (!$filename) {
            $msg = '目录名称无效';
            return false;
        }
        $path = path_rtoa(I('path'));
        $newpath = $path . DIRECTORY_SEPARATOR . $filename;
        try {
            mkdir($newpath, I('mode'));
            return true;
        } catch (Exception $ex) {
            $msg = $ex->getMessage();
            return false;
        }
    }

    /**
     * 上传文件
     * @param type $msg
     * @return boolean
     * @since 1.0 <2016-9-13> SoChishun Added.
     */
    static function act_upload_file(&$msg = '') {
        if ($_FILES["file"]["error"] > 0) {
            $msg = $_FILES["file"]["error"];
            return false;
        }

        $path = I('path');
        $path = path_rtoa($path);
        $filename = $_FILES["file"]["name"];
        if (file_exists($path . $filename)) {
            $msg = $filename . " 文件已存在!";
            return false;
        }
        move_uploaded_file($_FILES["file"]["tmp_name"], $path . $filename);
        return true;
    }

    /**
     * 重命名路径操作
     * @param string $msg 错误消息
     * @return boolean
     * @since 1.0 <2015-10-9> SoChishun Added.
     */
    static function act_rename_path(&$msg = '') {
        $filename2 = I('filename2');
        if (!$filename2) {
            $msg = '新名称未填写!';
            return false;
        }
        $path = path_rtoa(I('path'));
        if (is_file($path) && !strpos($filename2, '.')) {
            $msg = '文件扩展名无效!';
            return false;
        }
        try {
            $newname = pathinfo($path, PATHINFO_DIRNAME) . DIRECTORY_SEPARATOR . $filename2;
            @rename($path, $newname);
            return true;
        } catch (Exception $ex) {
            $msg = $ex->getMessage();
            return false;
        }
    }

    /**
     * 编辑权限操作
     * @param string $msg 错误消息
     * @return boolean
     * @since 1.0 <2015-10-9> SoChishun Added.
     */
    static function act_chmod_path(&$msg = '') {
        $mode = I('mode');
        if (!$mode) {
            $msg = '权限模式无效!';
            return false;
        }
        $path = path_rtoa(I('path'));
        try {
            chmod($path, $mode);
            return true;
        } catch (Exception $ex) {
            $msg = $ex->getMessage();
            return false;
        }
    }

    /**
     * 压缩操作
     * @param string $msg
     * @return boolean
     * @since 1.0 <2015-10-9> SoChishun Added.
     */
    static function act_zip(&$msg = '') {
        $filename = I('filename');
        $content = I('content');
        if (!$filename || !strpos($filename, '.')) {
            $msg = '压缩文件名无效!';
            return false;
        }
        if (!$content) {
            $msg = '压缩内容无效!';
            return false;
        }
        $include = array();
        $exclude = array();
        $paths = explode(PHP_EOL, $content);
        foreach ($paths as $path) {
            if (0 === strpos($path, 'exclude ')) {
                $exclude[] = trim(substr($path, 8));
            } else {
                $include[] = $path;
            }
        }
        if (!$include) {
            $msg = '压缩内容无效!';
            return false;
        }
        $zip = new ZipHelper();
        return $zip->zip($filename, $msg, $include, $exclude, I('rootpath'));
    }

    /**
     * 解压缩文件
     * @param type $msg
     * @return type
     */
    static function act_unzip(&$msg = '') {
        $root = I('root');
        $filename = I('filename');
        if (!$filename) {
            $msg = '压缩文件路径无效!';
            return false;
        }
        if (!$root) {
            $msg = '解压缩路径无效!';
            return false;
        }
        $zip = new ZipHelper();
        return $zip->unzip($filename, $root, $msg);
    }

    /**
     * 目录内容视图
     * @param type $path
     * @since 1.0 <2015-5-11> SoChishun Added.
     */
    static function view_content_list($path) {
        $files = self::get_dir_contents($path, array('name' => true, 'path' => false, 'real_path' => false, 'relative_path' => true, 'exten' => false, 'ctime' => false, 'mtime' => false, 'size' => false, 'is_dir' => true, 'is_file' => false, 'is_link' => true, 'is_executable' => true, 'is_readable' => false, 'is_writable' => false, 'filetype' => true));
        echo '<div class="dir-contents" title="蓝色表示目录,绿色表示可执行文件,浅蓝色表示链接文件,红色表示压缩文件,紫色表示图形文件,灰色表示其他文件">';
        foreach ($files as $file) {
            if ($file['is_dir']) {
                echo '<a href="?path=' . $file['relative_path'] . '" class="blue"><strong>' . $file['name'] . '</strong></a>';
            } else {
                $class = '';
                if ($file['is_link']) {
                    $class = 'lightblue';
                } else if ($file['is_executable']) {
                    $class = 'green';
                } else {
                    switch ($file['filetype']) {
                        case 'zip':
                            $class = 'red';
                            break;
                        case 'image':
                            $class = 'purple';
                            break;
                        default:
                            $class = 'grey';
                            break;
                    }
                }
                echo '<a href="?path=' . $file['relative_path'] . '" class="' . $class . '">' . $file['name'] . '</a>';
            }
        }
        echo '<div style="clear:both"></div></div>';
    }

    /**
     * 文件内容编辑视图
     * @param type $path
     * @since 1.0 <2015-5-11> SoChishun Added.
     */
    static function view_edit_file($path) {
        $sapath = path_rtoa($path);
        if (!is_file($sapath)) {
            return;
        }
        $category = get_exten_catetory(pathinfo($path, PATHINFO_EXTENSION));
        switch ($category) {
            case 'doc':
            case 'script':
                $btns = '<button type="submit">保存</button><button type="reset">重置</button>';
                if (!is_writable($sapath)) {
                    echo '<div style="color:#F00">文件不可写</div>';
                    $btns = '';
                }
                echo '<div>
                    <form method="post">
                        ', $btns, '<div><textarea name="content" cols="60" rows="36" style="width:90%">' . htmlspecialchars(file_get_contents($sapath)) . '</textarea></div>', $btns, '
                        <input type="hidden" name="action" value="savefile" />
                        <input type="hidden" name="filename" value="' . basename($path) . '" />
                        <input type="hidden" name="path" value="' . $path . '" />
                    </form>
                </div>';
                break;
            case 'image':
                echo '<img src="', $path, '" alt="" style="max-width:800px;max-height:640px;" /><br />';
                echo basename($path);
                echo ' <a href="', $path, '" target="_blank">[原图]</a>';
                break;
            default:
                echo basename($path);
                echo ' <a href="', $path, '" target="_blank">[下载]</a>';
                break;
        }
    }

    /**
     * 新增文件视图
     * @param string $path 路径
     * @since 1.0 <2015-10-8> SoChishun Added.
     */
    static function view_create_file($path) {
        echo '<div>
                    <form method="post">
                        <table>
                            <tr><th>文件名：</th><td><input type="text" name="filename" required="required" placeholder="如：newfile.txt" /></td></tr>
                            <tr><th valign="top">内容：</th><td><textarea name="content" cols="90" rows="12"></textarea></td></tr>
                            <tr><td>&nbsp;</td><td><button type="submit">创建文件</button><button type="reset">重置</button></td></tr>
                        </table>
                        <input type="hidden" name="action" value="save_newfile" />
                        <input type="hidden" name="path" value="' . $path . '" />
                    </form>
                </div>';
    }

    /**
     * 新增目录视图
     * @param string $path 路径
     * @since 1.0 <2015-10-8> SoChishun Added.
     */
    static function view_create_dir($path) {
        echo '<div>
                    <form method="post">
                        目录名：<input type="text" name="filename" required="required" /><br />
                        权限模式：<input type="text" name="mode" required="required" value="0777" /><br />
                        <button type="submit">创建目录</button> <button type="reset">重置</button>
                        <input type="hidden" name="action" value="save_newdir" />
                        <input type="hidden" name="path" value="' . $path . '" />
                    </form>
                </div>';
    }

    static function view_upload_file($path) {
        echo '<div>
                    <form method="post" enctype="multipart/form-data">
                        <table>
                            <tr><th>选择文件：</th><td><input type="file" name="file" required="required" /></td></tr>
                            <tr><td>&nbsp;</td><td><button type="submit">立即上传</button> <button type="reset">重置</button></td></tr>
                        </table>
                        <input type="hidden" name="action" value="upload_file" />
                        <input type="hidden" name="path" value="' . $path . '" />
                    </form>
                </div>';
    }

    /**
     * 重命名文件视图
     * @param string $path 路径
     * @since 1.0 <2015-10-8> SoChishun Added.
     */
    static function view_rename_path($path) {
        echo '<div>
                    <form method="post">
                        原名称：<input type="hidden" name="filename" value="' . basename($path) . '" />' . basename($path) . '<br />
                        新名称：<input type="text" name="filename2" required="required" /><br />
                        <button type="submit">重命名</button> <button type="reset">重置</button>
                        <input type="hidden" name="action" value="rename_path" />
                        <input type="hidden" name="path" value="' . $path . '" />
                    </form>
                </div>';
    }

    /**
     * 编辑权限视图
     * @param string $path 路径
     * @since 1.0 <2015-10-9> SoChishun Added.
     */
    static function view_chmod_path($path) {
        echo '<div>
                    <form method="post">
                        名称：' . basename($path) . '<br />
                        权限模式：<input type="text" name="mode" required="required" value="0777" /><br />
                        <button type="submit">设置</button> <button type="reset">重置</button>
                        <input type="hidden" name="action" value="chmod_path" />
                        <input type="hidden" name="path" value="' . $path . '" />
                    </form>
                </div>';
    }

    /**
     * 压缩文件视图
     * @since 1.0 <2015-10-9> SoChishun Added.
     */
    static function view_zip() {
        echo '<div>
                    <form method="post">
                        <table>
                            <tr><th>压缩文件名：</th><td><input type="text" name="filename" required="required" size="89" placeholder="绝对路径,如：C:\public\www\website1\newfile.zip" /></td></tr>
                            <tr><th valign="top">压缩内容：</th><td><textarea name="content" cols="90" rows="12" placeholder="每个路径一行,必需是绝对路径"></textarea></td></tr>
                            <tr><th>去除根路径：</th><td><input type="text" name="rootpath" size="89" placeholder="绝对路径,如：C:\public\www\website1" /></td></tr>
                            <tr><td>&nbsp;</td><td class="red">
                            注意，所有路径都必需是绝对路径!<br />
                            包含路径示例：C:\public\www\website1\app<br />
                            排除路径示例: exclude C:\public\www\website1\app\runtime<br />
                            如果填写跟路径地址,则压缩内容会自动去除跟路径信息(解压缩的时候,可以解压缩到任意目录下),如果根路径为空则保留根路径信息(解压缩的时候,无法解压缩到任意目录下,系统会自动创建和压缩前路径一样的目录)
                            </td></tr>
                            <tr><td>&nbsp;</td><td><button type="submit">创建压缩文件</button><button type="reset">重置</button></td></tr>
                        </table>                        
                        <input type="hidden" name="action" value="zip" />
                    </form>
                </div>';
    }

    /**
     * 解压缩文件视图
     * @since 1.0 <2015-10-9> SoChishun Added.
     */
    static function view_unzip() {
        echo '<div>
                    <form method="post">
                        <table>
                            <tr><th>压缩文件名：</th><td><input type="text" name="filename" required="required" size="89" placeholder="绝对路径,如：C:\public\www\website1\newfile.zip" /></td></tr>
                            <tr><th>解压缩路径：</th><td><input type="text" name="root" required="required" size="89" placeholder="绝对路径,如：C:\public\www\website1" /></td></tr>
                            <tr><td>&nbsp;</td><td><button type="submit">解压缩文件</button><button type="reset">重置</button></td></tr>
                        </table>
                        <input type="hidden" name="action" value="unzip" />
                    </form>
                </div>';
    }

    /**
     * 返回指定路径下的内容
     * @param string $directory 路径
     * @param array $config 选项
     * @return array
     * @throws Exception
     * @since 1.0 <2015-5-11> SoChishun Added.
     * @since 1.1 <2015-10-8> SoChishun 新增filetype文件类别属性
     */
    static function get_dir_contents($directory, $options = array()) {
        $config = array('name' => true, 'path' => true, 'real_path' => true, 'relative_path' => false, 'exten' => false, 'ctime' => false, 'mtime' => false, 'size' => false, 'is_dir' => true, 'is_file' => false, 'is_link' => false, 'is_executable' => false, 'is_readable' => false, 'is_writable' => false, 'filetype' => false);
        if ($options) {
            $config = array_merge($config, $options);
        }
        try {
            $dir = new DirectoryIterator(path_rtoa($directory));
        } catch (Exception $e) {
            throw new Exception($directory . ' is not readable');
        }
        $files = array();
        foreach ($dir as $file) {
            if ($file->isDot()) {
                continue;
            }
            if ($config['name']) {
                $item['name'] = $file->getFileName();
            }
            if ($config['path']) {
                $item['path'] = $file->getPath();
            }
            if ($config['real_path']) {
                $item['real_path'] = $file->getRealPath();
            }
            if ($config['relative_path']) {
                $item['relative_path'] = path_ator($file->getRealPath());
            }
            $exten = $file->getExtension();
            if ($config['exten']) {
                $item['exten'] = $exten;
            }
            if ($config['filetype']) {
                $item['filetype'] = get_exten_catetory($exten);
            }
            if ($config['mtime']) {
                $item['mtime'] = $file->getMTime();
            }
            if ($config['ctime']) {
                $item['ctime'] = $file->getCTime();
            }
            if ($config['size']) {
                $item['size'] = $file->getSize();
            }
            if ($config['is_dir']) {
                $item['is_dir'] = $file->isDir();
            }
            if ($config['is_file']) {
                $item['is_file'] = $file->isFile();
            }
            if ($config['is_link']) {
                $item['is_link'] = $file->isLink();
            }
            if ($config['is_executable']) {
                $item['is_executable'] = $file->isExecutable();
            }
            if ($config['is_readable']) {
                $item['is_readable'] = $file->isReadable();
            }
            if ($config['is_writable']) {
                $item['is_writable'] = $file->isWritable();
            }
            $files[] = $item;
        }
        return $files;
    }

    /**
     * 路径转为导航
     * @param string $path
     * @since 1.0 <2015-5-11> SoChishun Added.
     */
    static function location_to_breadcrumb($path) {
        echo '<div class="nav"><a href="?path=/">/</a>';
        if ('/' != $path) {
            $asubpath = explode('/', substr($path, 1));
            if ($asubpath) {
                $str = '';
                foreach ($asubpath as $sub) {
                    $str .= '/' . $sub;
                    echo '<a href="?path=', $str, '">', $sub, '</a>';
                }
            }
        }
        // echo '<div>', path_rtoa($path), '</div>';
		// 不显示根目录, 只显示相对路径,
		echo '<div>', path_rt_oa($path), '</div>';
        echo '</div>';
    }

}

/**
 * 压缩类
 * @since 1.0 <2015-10-9> SoChishun Added.
 */
class ZipHelper {

    /**
     * 解压缩之
     * @param type $filename
     * @param type $root
     * @param type $msg
     * @return boolean
     * @since 1.0 <2015-10-9> SoChishun Added.
     */
    function unzip($filename, $root, &$msg = '') {
        if (!$filename) {
            $msg = '压缩文件名无效!';
            return false;
        }
        $zip = new ZipArchive();
        $msg = $zip->open($filename);
        if (true !== $msg) {
            $msg = var_export($msg, true);
            return false;
        }
        $zip->extractTo($root);
        $zip->close();
        return true;
    }

    /**
     * 压缩之
     * @param type $filename
     * @param type $msg
     * @param type $include
     * @param type $exclude
     * @param string $trimpath
     * @param string $comment
     * @return boolean
     * @since 1.0 <2015-10-9> SoChishun Added.
     */
    function zip($filename, &$msg = '', $include = array(), $exclude = array(), $trimpath = '', $comment = 'default') {
        if (!$filename) {
            $msg = '压缩文件名无效!';
            return false;
        }
        if (!$include) {
            $msg = '压缩内容无效!';
            return false;
        }
        if ('default' == $comment) {
            $comment = basename($filename) . PHP_EOL . 'Generate at ' . date('Y-m-d H:i:s') . PHP_EOL . 'Powerd by SuExplorer.'; // 注释内容
        }
        try {
            $zip = new ZipArchive();
            $msg = $zip->open($filename, ZIPARCHIVE::OVERWRITE);
            if (true !== $msg) {
                $msg = var_export($msg, true);
                return false;
            }
            if ($comment) {
                $zip->setArchiveComment($comment);
            }
            if ($trimpath) {
                $trimpath = rtrim($trimpath, DIRECTORY_SEPARATOR) . DIRECTORY_SEPARATOR;
            }
            $substart = strlen($trimpath);
            foreach ($include as $source) {
                $this->zip_dir($zip, $source, $exclude, $substart);
            }
            $zip->close();
            return true;
        } catch (Exception $ex) {
            $msg = $ex->getMessage();
            return false;
        }
    }

    /**
     * 递归压缩整个目录
     * @param ZipArchive $zip
     * @param string $source 包含的路径
     * @param array $exclude 排除的路径
     * @param int $substart 开始截取的路径字符串(用于去除路径中的根目录路径)
     * @since 1.0 <2015-8-28> SoChishun Added.
     */
    function zip_dir(&$zip, $source, $exclude, $substart = 0) {
        if (is_dir($source)) {
            $source = rtrim($source, DIRECTORY_SEPARATOR);
            if ($handle = opendir($source)) {
                while (false !== ( $f = readdir($handle) )) {
                    if ('.' == $f || '..' == $f) {
                        continue;
                    }
                    $filename = $source . DIRECTORY_SEPARATOR . $f;
                    if (is_dir($filename)) {
                        if ($exclude && in_array($filename, $exclude)) {
                            continue;
                        }
                        $this->zip_dir($zip, $filename, $exclude, $substart);
                    } else {
                        if ($exclude && in_array($filename, $exclude)) {
                            continue;
                        }
                        $zip->addFile($filename, substr($filename, $substart));
                    }
                }
                closedir($handle);
            }
        } else {
            if ($exclude && in_array($source, $exclude)) {
                return;
            }
            $zip->addFile($source);
        }
    }
}
