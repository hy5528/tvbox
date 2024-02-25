
var rule = {
    title:'好听轻音乐',
    host:'http://www.htqyy.com/',
    url:'/fyclass',
    class_name:'好听轻音乐精选',
    class_url:'/top',
    推荐:'*',
      一级:"js:var items=[];pdfh=jsp.pdfh;pdfa=jsp.pdfa;pd=jsp.pd;var html=request(input);var tabs=pdfa(html,'body&&#body.center .topL li:gt(0):lt(6)');tabs.forEach(function(it){var pz=pdfh(it,'a&&Text');var img=pd(it,'img&&src');var url=pd(it,'a&&href');items.push({title:pz,pic_url:img,url:url})});setResult(items);",
      二级:{
	          title:".title a&&Text;.artistName a&&Text",
            img:".poster img&&src",
            desc:";;;.pic a&&title;.game-info-container div:eq(2)&&Text",
	          content:".albumName a&&title",
	          tabs:"js:TABS=['【轻音乐精选】']",
	          lists:'#body.center #musicList.s li', 
           list_text:'a&&Text',
           list_url:'a&&href'	
          },
    搜索:'',
}
