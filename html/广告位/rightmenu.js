// JavaScript Document
$(document).ready(function () {
    //qrcode hover
    $(".wp_celan_content .pqr").hover(
            function () {
                var width=0;
                var bel=$(this).find("b")
                bel.show();
                $(this).find("b .qrbox").each(function(){
                    width+=$(this).width();
                })
                if(bel.width()<width){
                    bel.width(width+20);
                }
                $('.wp_celan_content').css('z-index', '1000000')
            },
            function () {
                $(this).find("b").hide();
                $('.wp_celan_content').css('z-index', '10000')
            }
        );
    
    //左侧栏
    if($.sidebar_aleft) {
	$(".wp_celan_content").css({ "left": "0px" });
    }else $(".wp_celan_content").animate({ "right": ($('#scroll_container').width() - $('#scroll_container_bg').width())+"px" });

    var wp_celan_meau_control = 1;
    if (wp_celan_meau_control == "1") {
        $(".wp_celan_content_open").show();
        $(".wp_celan_content_open").hide();
        $('#wp_celan_meau').show();
    }
    $(function () {
        //滚轮上行后显示
        $('#scroll_container').scroll(function () {
            if ($('#scroll_container').scrollTop() > 150) {
            }else{
            }
        })

        $('.wp_celan_content p.ptop').click(function () {
            if (!$("html,body").is(":animated")) {
                $('#scroll_container').animate({ scrollTop: 0 }, 800);
            }
            return false;
        })
    })

    //客服列表滚动条
    //kf topHeight
    var height = $(window).height();
    // pwb,pqr,ptop height
    var plist_h = (69*5)-69;
    $('.wp_celan_content p:first').css('marginTop', ((height-plist_h-120)/2)+'px');
    var kf_detail = $('#wp_celan_meau .wp_celan_detailcontent .detail_info').outerHeight();
    var detail_top = (height-kf_detail)/2;
    $('#wp_celan_meau .wp_celan_detailcontent').css('paddingTop', detail_top+'px');
        $('.wp_celan_content p.pwb').css('bottom', '92px')
        $('.wp_celan_content p.pqr').css('bottom', '50px')
    //关闭详情内容动作
    $('.wp_celan_content p.pwb,.wp_celan_content p.pqr,.wp_celan_content p.ptop').click(function () {
        $('.rm_login').stop().fadeOut(200);
		$('.wp_celan_detailcontent').css('z-index', '10');
		if($.sidebar_aleft) $('.wp_celan_detailcontent,.rm_bz,.rm_kf').stop().animate({ left: '-291px' }, 300);
        else $('.wp_celan_detailcontent,.rm_bz,.rm_kf').stop().animate({ right: '-291px' }, 300);
		$('.wp_celan_content').find('.s_arrow').css("display","none");
		$('.wp_celan_content').find('p.p3').css("background", "none");
    });
    $('#wp_celan_meau').siblings().click(function () {
		$('.rm_login').stop().fadeOut(200);
		$('.wp_celan_detailcontent').css('z-index', '10');
		if($.sidebar_aleft) $('.wp_celan_detailcontent,.rm_bz,.rm_kf').stop().animate({ left: '-291px' }, 300);
		else $('.wp_celan_detailcontent,.rm_bz,.rm_kf').stop().animate({ right: '-291px' }, 300);
		//kf_close
		$('.wp_celan_content').find('.s_arrow').css("display","none");
		$('.wp_celan_content').find('p.p3').css("background", "none");
    })
	
    //客服列表事件
    $("#wp_celan_meau .wp_celan_detailcontent .detail_info li a").hover(
	    function () {
		if ($(this).attr('class') == "qq") {
		    $(this).find('.detail_kf_ico_qq').css({"background":"url("+$.sidebar_pathimg+"icon_view_qq_h.png)"});
		    $(this).find('.detail_kf_ico_qq_on').css({"background":"url("+$.sidebar_pathimg+"icon_view_qq_h.png)"});
		}
        if ($(this).attr('class') == "whatsapp") {
		    $(this).find('.detail_kf_ico_8').css({"background":"url("+$.sidebar_pathimg+"icon_view_8_h.png)"});
		    $(this).find('.detail_kf_ico_8_on').css({"background":"url("+$.sidebar_pathimg+"icon_view_8_h.png)"});
		}
		if ($(this).attr('class') == "skype") {
		    $(this).find('.detail_kf_ico_skype').css({"background":"url("+$.sidebar_pathimg+"icon_view_skype_h.png)"});
		}
		if ($(this).attr('class') == "ww") {
		    $(this).find('.detail_kf_ico_ww').css({"background":"url("+$.sidebar_pathimg+"icon_view_ww_h.png)"});
		    $(this).find('.detail_kf_ico_ww_online').css({"background":"url("+$.sidebar_pathimg+"icon_view_ww_h.png)"});
		}
		if ($(this).attr('class') == "custom") {
			var def=$(this).find("img").attr("data-over");
			$(this).find("img").attr("src",def);
		}
	    },
	    function () {
		if ($(this).attr('class') == "qq") {
		    $(this).find('.detail_kf_ico_qq').css({"background-image":"url("+$.sidebar_pathimg+"icon_view_qq.png)","background-color":"#d1d1cf"});
		    $(this).find('.detail_kf_ico_qq_on').css({"background-image":"url("+$.sidebar_pathimg+"icon_view_qq.png)","background-color":$.sidebar_menuclolr});
		}
		if ($(this).attr('class') == "skype") {
		    $(this).find('.detail_kf_ico_skype').css({"background-image":"url("+$.sidebar_pathimg+"icon_view_skype.png)","background-color":"#d1d1cf"});
		}
        if ($(this).attr('class') == "whatsapp") {
		    $(this).find('.detail_kf_ico_8').css({"background-image":"url("+$.sidebar_pathimg+"icon_view_8.png)","background-color":"#d1d1cf"});
		}
		if ($(this).attr('class') == "ww") {
		    $(this).find('.detail_kf_ico_ww').css({"background-image":"url("+$.sidebar_pathimg+"icon_view_ww.png)","background-color":$.sidebar_menuclolr});
		    $(this).find('.detail_kf_ico_ww_online').css({"background-image":"url("+$.sidebar_pathimg+"icon_view_ww.png)","background-color":$.sidebar_menuclolr});
		}
		if ($(this).attr('class') == "custom") {
			
			var hov=$(this).find("img").attr("data-out");
			$(this).find("img").attr("src",hov);
		}
	    }
    );
    var ww = $(window).width();
    if (ww <= 1360) {

    } else {
    }
    //关闭登录窗口

//skin02 js
$('li.sgotopdd img.hover').click(function () {
	if (!$("html,body").is(":animated")) {
		$('#scroll_container').animate({ scrollTop: 0 }, 800);
	}
	return false;
})

$('.wpsidebar02 li.smessage img.hover').click(function () {
	if ($.sidebar_linkstr.message.linkurl) {
		if($.sidebar_linkstr.message.target=='_blank'){
			var newwindow=window.open('about:blank');
			newwindow.location.href=$.sidebar_linkstr.message.linkurl;
			return '';
		}
		location.href=$.sidebar_linkstr.message.linkurl;
	}
	return false;
})

$('.wpsidebar02 li.shelp img.hover').click(function () {
	if ($.sidebar_linkstr.help.linkurl) {
		if($.sidebar_linkstr.help.target=='_blank'){
			var newwindow=window.open('about:blank');
			newwindow.location.href=$.sidebar_linkstr.help.linkurl;
			return '';
		}
		location.href=$.sidebar_linkstr.help.linkurl;
	}
	return false;
})

$('.wpsidebar02 li.sgotop img.hover,.wpsidebar03 .sgotop img.img_active').click(function () {
	if (!$("html,body").is(":animated")) {
		$('#scroll_container').animate({ scrollTop: 0 }, 500);
	}
	return false;
})
$('.wpsidebar03 .gobottom img.img_active').click(function(){
	if (!$("html,body").is(":animated")){
		$('#scroll_container').animate({ scrollTop:$('#scroll_container_bg').height()}, 500);
	}
	return false;
})
})

function sidebar_hides(sideDom,diff_width,init_right,hdom,hdomcontent,sidebar_aleft,skin){
	 
	var sideWidth = sideDom.width()+diff_width;
	var lrtag='';
	var initlr=0;
	if(sidebar_aleft) {
		lrtag='left'; 
		hdom.css({'border-radius':"0 5px 5px 0"});
		sideDom.animate({'left':(-sideWidth)+"px"},100, function() {			
			 $(this).show().css({"transition":"all 0.3s ease-out"});
		});
	}else{
		lrtag='right';
		hdom.css({'border-radius':"5px 0 0 5px"}).find("a").css({'transform':"rotate(180deg)"});
		sideDom.animate({'right':(-sideWidth)+"px"},100, function() {
			 $(this).show().css({"transition":"all 0.3s ease-out"});
		});
		initlr = init_right;
	}
 
	function hidesidebar(){
		// 鼠标移出页面左侧区域时
		sideDom.css(lrtag,(-sideWidth)+"px");
		if(skin=='01n'){
			$("#wp_celan_meau .wp_celan_content .pqr").find("b").hide();
			if($('#wp_celan_meau .wp_celan_content p.p3').find('.s_arrow').css('display') == 'block'){
				$('#wp_celan_meau .wp_celan_content p.p3').click();
			}
		}
		setTimeout(function(){
			hdom.fadeIn('slow');
		},200);
		
	}

	hdom.mouseover(function(){
		sideDom.css(lrtag,initlr+"px");
		$(this).fadeOut('fast');
	})
	
	var hidetimer;
	hdomcontent.hover(
		function(){
			clearTimeout(hidetimer);
		},
		function(){
			hidetimer=setTimeout(function(){
				hidesidebar()
			},500)
			
		}
	);
	if(skin=='01n'){
		$("#wp_celan_meau .detail_kf").find("a").click(function(){
			$("#wp_celan_meau .wp_celan_content .pqr").find("b").hide();
			if($('#wp_celan_meau .wp_celan_content p.p3').find('.s_arrow').css('display') == 'block'){
				$('#wp_celan_meau .wp_celan_content p.p3').click();
			}
		});
	}
	
}

