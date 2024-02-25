var rule = {
    title:'纯音乐',
    host:'http://m.htcyy.com/',
    url:'/fyclass',
    class_name:'纯音乐精选',
    class_url:'/top',
    推荐:'*',
      一级:"js:var items=[];pdfh=jsp.pdfh;pdfa=jsp.pdfa;pd=jsp.pd;var html=request(input);var tabs=pdfa(html,'body&&#main .layout.top li');tabs.forEach(function(it){var pz=pdfh(it,'.info a&&Text');var pk=pdfh(it,'.ew&&Text');var img=pd(it,'img&&src');var timer=pdfh(it,'.ew&&Text');var url=pd(it,'a&&href');items.push({desc:timer+'  ',title:pz+' '+pk,pic_url:img,url:url})});setResult(items);",
      二级:{
	      title:".info a&&Text;em&&Text",
          img:"img&&src",
          desc:";;;.pic a&&title;.game-info-container div:eq(2)&&Text",
	      content:"img&&alt",
	      tabs:"js:TABS=['【纯音乐精选】']",
	      lists:'#main .layout.hot li', 
          list_text:'a&&Text',
          list_url:'a:gt(0)&&href'	
         },
    搜索:'',
}
