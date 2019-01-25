


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

menu.style.display="none"

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


//file right-click menu
$('.du').contextmenu(function(event)
	{
	if(clicked){
    clicked.style.fontWeight="normal"; //clear previous highlight
		};
  clicked=this
  var item_id = this.id;
  var hash_id= $(this).attr('src');
  var size=$(this).attr('size');
  $(".menu-hash").html('<b>Hash:</b>...'+hash_id.substring(50));
	this.style.fontWeight="bold";
	$(".menu-path").html("<b>File:</b> "+this.id);
	$(".menu-size").html("<b>Size:</b> "+size);
	$(".menu-scans").html('<p><b>MASTER</b>: Scanned: '+$(this).attr('master_scan')+' Changed:'+$(this).attr('master_changed')+' Dups: '+$(this).attr('m_dup')+' ('+$(this).attr('m_dups')+')');	
	$(".menu-localscans").html('<p><b>SCAN FOLDER</b>: Scanned: '+$(this).attr('local_scan')+' Duplicate: '+$(this).attr('l_dup')+' Changed:'+$(this).attr('local_changed')+' Dups:'+$(this).attr('l_dup')+' ('+$(this).attr('l_dups')+')'+' Found in Master: '+$(this).attr('hash_in_master'));	
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
  alert(dataform)
  
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

