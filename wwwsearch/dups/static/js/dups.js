
$('.glyphicon-duplicate').click(function(e) {
    //alert('clicked this');
    
    
    var $this = $(this);
    var _src = $(this).closest("div[src]").attr('src');
    //$.post( ,{'hash':'a hash'}, function(data)
  	window.location.href = "/dups/files/"+_src;
  	
  	//works:
 /* 	$.get("/dups/files_api", { "hash": _src},function(data)
  	{
  	if (data.dups=='')
  		{
  		console.log(data.message);
  		alert(data.message);
  		}
  	else
  		{
  		alert(data.dups);	
  		};
  	},'json' // I expect a JSON response
  	);*/
	});

$('.glyphicon-saved').click(function(e) {
    //alert('clicked this');
    var $this = $(this);
    var _src = $(this).closest("div[src]").attr('src');
    //$.post( ,{'hash':'a hash'}, function(data)
  	window.location.href = "/dups/files/"+_src;
  	
	});

$('.btn').click(function(e) {
	//alert('clicked');
	});

$('.flip').click(function(e) {
//    alert('clicked this')
    var $this = $(this);
    $this.next('div.subdir').slideToggle('fast');
    $this.toggleClass('show');
    if ($this.hasClass('show')) {
        $this.html('<span style="font-size:12px">[hide}</span>');
    } else {
        $this.html(' +');
			};

		});

const menu = document.querySelector(".menu");

let menuVisible = false;
let clicked=false

if (menu !== null) {
menu.style.display="none"
};

const toggleMenu = command => {
//  var menu=document.getElementById('foo')
  menu.style.display = command === "show" ? "block" : "none";
  menuVisible = !menuVisible;
};

const setPosition = ({ top, left }) => {
//  console.log(left)
//  console.log(`${top}px`)
  menu.style.left = `${left-30}px`;
  menu.style.top = `${top-80}px`;
  toggleMenu('show');
};

const folderActions = (clicked) => 
 {
	clicked.style.fontWeight="bold";
	var item_id = clicked.id;
	
	$(".menu-path").html("<b>Folder:</b> "+clicked.id);
	$(".menu").attr("data-id",clicked.id);
	$(".scan-folder").show();
	$(".master-folder").show();
	$(".menu-hash").hide();
	$(".menu-size").hide();
	$(".menu-scans").hide();	
	$(".menu-localscans").hide();	
	var rect = clicked.getBoundingClientRect();

  const origin = {
  	left: rect.left,
  	top: rect.top+window.scrollY
  };
    setPosition(origin);
    event.preventDefault();
    menuVisible = true;
 };

const yes_icon='<span class="glyphicon glyphicon-ok"></span>'
const no_icon='<span class="glyphicon glyphicon-remove"></span>'
//file right-click menu
$('.du').contextmenu(function(event)
	{
	if(clicked){
    clicked.style.fontWeight="normal"; //clear previous highlight
		};
  clicked=this
  var item_id = this.id;
  var hash_id= $(this).attr('src');
  var hash_url_str="<a href='/dups/files/"+hash_id
  var size=$(this).attr('size');
  var master_scan=$(this).attr('master_scan');
  var master_scan_icon=no_icon;
  if (master_scan=="True")
	{
	   master_scan_icon=yes_icon
	};
  var master_changed=$(this).attr('master_changed');
  var master_changed_icon=no_icon;
  if (master_changed=="True")
	{
	   master_changed_icon=yes_icon
	};
  var master_dups=$(this).attr('m_dup')
  var master_dups_icon=no_icon;
  var master_dups_count=''
  if (master_dups=="True"){
  	master_dups_icon=yes_icon;
	master_dups_count=' ('+$(this).attr('m_dups')+')'
	};
   
  $(".menu-hash").html('<b>Hash:</b>...'+hash_id.substring(50));
  this.style.fontWeight="bold";
	$(".menu-path").html("<b>File:</b> "+this.id);
	$(".menu-size").html("<b>Size:</b> "+size);
	$(".menu-scans").html('<p><b>MASTER</b>: Scanned: '+master_scan_icon+' Changed:'+master_changed_icon+' Dups: '+master_dups_icon+master_dups_count);	
	
	var local_scan=$(this).attr('local_scan');
	var local_scan_icon=no_icon;
	if (local_scan=="True"){local_scan_icon=yes_icon;};
	var local_changed=$(this).attr('local_changed');
	var local_changed_icon=no_icon;
	if (local_changed){local_changed_icon=yes_icon};
	var local_dups=$(this).attr('l_dup');
	var local_dups_icon=no_icon;
	var local_dups_count='';
	var in_master=$(this).attr('hash_in_master');
	var in_master_icon=no_icon;
	if (in_master=="True"){in_master_icon=yes_icon;};
	

	var list_dups_str=""
	if (in_master=="True" || local_dups=="True" || master_dups=="True")
	{	
	list_dups_str=hash_url_str+"'>List Duplicates</a>";
	};
	if (local_dups=="True"){
  	local_dups_icon=yes_icon;
	local_dups_count=hash_url_str+"'>("+$(this).attr('l_dups')+")</a>"
	};
	$(".menu-localscans").html('<p><b>SCAN FOLDER</b>: Scanned: '+local_scan_icon+' Duplicate: '+local_dups_icon+' Changed:'+local_changed_icon+' Dups:'+local_dups_icon+local_dups_count+' Found in Master: '+in_master_icon+' <p>'+list_dups_str);	
	$(".scan-folder").hide();
	$(".master-folder").hide();
	var rect = this.getBoundingClientRect();
  event.preventDefault();
  event.stopPropagation();
//  alert('context');
  const origin = {
  	left: rect.left,
  	top: rect.top+window.scrollY
  };
    setPosition(origin);
    menuVisible = true;
  });

$('.bread1').contextmenu(function(event)
	{
	
	if(clicked){
    clicked.style.fontWeight="normal"; //clear previous highlight
		};
	clicked=this;
	folderActions(clicked);
	});



//folder right-click menu
$('.subfolder').contextmenu(function(event)
	{
	if(clicked){
    clicked.style.fontWeight="normal"; //clear previous highlight
		};
  clicked=this;
  folderActions(clicked);
  event.stopPropagation();
  });

	
//folder right-click menu
$('.folder-item').contextmenu(function(event)
	{
	if(clicked){
    clicked.style.fontWeight="normal"; //clear previous highlight
		};
  clicked=this;
  folderActions(clicked);
  });

$( ".move-button" ).click(
  function() {
  	const file_hash=$(".hash-value").attr('value');
  	newwindow=window.open("/picker/&next_url=/dups/files/"+file_hash,'box','height=400,width=300');
    if (window.focus) {newwindow.focus()}
    return false;
    
});

function HandlePopupResult(result) {
//    alert("result of popup is: " + result);
    $("#destination").attr("value",result);
    $("#to-do").attr("value","move");
    //alert($("#destination").attr("value"));
    $("#duplicates-form").submit();

}


$(".master-folder").click(
  function() {
  var folder = $(this).closest("div[data-id]").attr('data-id');
  $(".master-url").html("<a href='/dups/folder/"+folder+"'>"+folder+"</a>");
  var dataform=$('#master-folder-form').serialize();
//  var folder_mod="this+that space"//JSON.stringify(folder)
  var folder_clean = encodeURIComponent(folder); //deals with special characters in filepaths e.g + sign
  dataform=dataform+"&folder_type=master&folder_path="+folder_clean
  $.post( '/dups/ajax',dataform, function(data)
  	{
  	if (data.saved==false)
  		{
  		console.log(data.message);
  		alert('Failed to save');
  		}
  	else
  		{
  		//document.getElementById("form-errors-{{filter}}").innerHTML=' ';
  		};
  	},'json' // I expect a JSON response
  	);
});

$(".scan-folder").click(
  function() {
  var folder = $(this).closest("div[data-id]").attr('data-id');
  $(".local-url").html("<a href='/dups/folder/"+folder+"'>"+folder+"</a>");
  var dataform=$('#scan-folder-form').serialize();
  var folder_clean = encodeURIComponent(folder); //deals with special characters in filepaths e.g + sign
  dataform=dataform+"&folder_type=local&folder_path="+folder_clean
  //alert(dataform)
  
  $.post( '/dups/ajax',dataform, function(data)
  	{
  	if (data.saved==false)
  		{
  		//console.log(data.message);
  		alert('Failed to save');
  		}
  	else
  		{
  		document.getElementById("form-errors-{{filter}}").innerHTML='';
  		};
  	},'json' // I expect a JSON response
  	);
});

window.addEventListener("click", e => {
  if(menuVisible)
  {
  	toggleMenu("hide");
  	if(clicked){
    clicked.style.color="black";
		};
	}
});

