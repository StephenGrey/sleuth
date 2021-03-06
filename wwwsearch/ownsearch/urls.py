from django.conf.urls import url
from . import views
from django.contrib.staticfiles.urls import staticfiles_urlpatterns

urlpatterns = [
    url(r'^$', views.do_search, name='searchview'),
    url(r'^searchterm=(?P<searchterm>.*)&(?P<direction>next)afterpage=(?P<page_number>\d+)&sorttype=(?P<sorttype>.+)&filters=(?P<tag1field>.*)=(?P<tag1>.*)&(?P<tag2field>.*)=(?P<tag2>.*)&(?P<tag3field>.*)=(?P<tag3>.*)&(?P<tag4field>.*)=(?P<tag4>.*)$', views.do_search, name='nextpageview4'),
    url(r'^searchterm=(?P<searchterm>.*)&(?P<direction>next)afterpage=(?P<page_number>\d+)&sorttype=(?P<sorttype>.+)&filters=(?P<tag1field>.*)=(?P<tag1>.*)&(?P<tag2field>.*)=(?P<tag2>.*)&(?P<tag3field>.*)=(?P<tag3>.*)$', views.do_search, name='nextpageview3'),
    url(r'^searchterm=(?P<searchterm>.*)&(?P<direction>next)afterpage=(?P<page_number>\d+)&sorttype=(?P<sorttype>.+)&filters=(?P<tag1field>.*)=(?P<tag1>.*)&(?P<tag2field>.*)=(?P<tag2>.*)$', views.do_search, name='nextpageview2'),
    url(r'^searchterm=(?P<searchterm>.*)&(?P<direction>next)afterpage=(?P<page_number>\d+)&sorttype=(?P<sorttype>.+)&filters=(?P<tag1field>.*)=(?P<tag1>.*)$', views.do_search, name='nextpageview1'),
    url(r'^searchterm=(?P<searchterm>.*)&(?P<direction>next)afterpage=(?P<page_number>\d+)&sorttype=(?P<sorttype>.*)$', views.do_search, name='nextpageview'),

    url(r'''^searchterm=(?P<searchterm>.*)&page=(?P<page_number>\d+)&sorttype=(?P<sorttype>.+)&filters=(?P<tag1field>[\w\s]*)=(?P<tag1>[^=]*)'''
    r'''(?:&tag=(?P<tag2field>[^=]*)=(?P<tag2>[^&=]*|))?'''
    r'''(?:&tag=(?P<tag3field>[^=]*)=(?P<tag3>[^&=]*|))?''' 
    r'''(?:&start_date=(?P<start_date>[0-9]{8}|))?'''
    r'''(?:&end_date=(?P<end_date>[0-9]{8}|))?$'''
    	,
    views.do_search, name='searchpagefilters'),

    url(r'''^searchterm=(?P<searchterm>.*)&page=(?P<page_number>\d+)&sorttype=(?P<sorttype>\w+)'''
    r'''(?:&start_date=(?P<start_date>[0-9]{8}))?'''
    r'''(?:&end_date=(?P<end_date>[0-9]{8}))?$'''
    , views.do_search, name='searchpageview'),
 
	
    url(r'^searchterm=(?P<searchterm>.*)&(?P<direction>back)frompage=(?P<page_number>\d+)&sorttype=(?P<sorttype>.+)&tag2=(?P<tag2>.*)$', views.do_search, name='backpageview'),
    url(r'^searchterm=(?P<searchterm>.*)&(?P<direction>back)frompage=(?P<page_number>\d+)&sorttype=(?P<sorttype>.+)&tag1=(?P<tag1>.*)$', views.do_search, name='backpageview'),
    url(r'^searchterm=(?P<searchterm>.*)&(?P<direction>back)frompage=(?P<page_number>\d+)&sorttype=(?P<sorttype>.*)$', views.do_search, name='backpageview'),
    url(r'^doc=(?P<doc_id>.*)&searchterm=(?P<searchterm>.*)&tagedit=(?P<tagedit>True)$', views.get_content, name='contentview'),
    url(r'^doc=(?P<doc_id>.*)&searchterm=(?P<searchterm>.*)$', views.get_content, name='contentview'),

    url(r'^download=(?P<doc_id>.*)&(?P<hashfilename>.*)$', views.download, name='download'),
    url(r'^embed=(?P<doc_id>.*)&(?P<hashfilename>.*)&(?P<mimetype>.*)$', views.embed, name='embed'),
    
    url(r'^ajax/post_usertags$',views.post_usertags,name='post_usertags'),
    url(r'^ajax/check_solr$',views.check_solr,name='check_solr_api'),
    url(r'^ajax/check_bot$',views.check_bot,name='check_bot_api'),

   ]

urlpatterns += staticfiles_urlpatterns()
