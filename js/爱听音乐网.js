var rule = {
    title:'爱听音乐网',
    host:'http://www.2t58.com',    
    url:'/fyclass',
    class_name:'榜单推荐',
    class_url:'/list/new.html',
    推荐:'*',
     一级:"js:var items=[];pdfh=jsp.pdfh;pdfa=jsp.pdfa;pd=jsp.pd;var html=request(input);var tabs=pdfa(html,'body&&.layui-container:eq(1) li:gt(0):lt(31)');tabs.forEach(function(it){var pz=pdfh(it,'a&&Text');var ps=pdfh(it,'a&&Text');var img=pd(it,'.pic img&&src');var url=pd(it,'a&&href');items.push({desc:ps,title:pz,pic_url:img,url:url})});setResult(items);",
     二级:{
          title:".name a&&Text;a&&Text",
          img:".pic img&&src",
          desc:";;;.pic a&&title;.game-info-container div:eq(2)&&Text",
	      content:".sm:eq(1)&&Text",
	      tabs:"js:TABS=['【音乐榜单】']",
	      lists:'.play_list li', 
          list_text:'a&&Text',
          list_url:'a&&href'	
         },
    搜索:'',
}
