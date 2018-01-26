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

    url(r'^searchterm=(?P<searchterm>.*)&page=(?P<page_number>\d+)&sorttype=(?P<sorttype>.+)&filters=(?P<tag1field>.*)=(?P<tag1>.*)&(?P<tag2field>.*)=(?P<tag2>.*)&(?P<tag3field>.*)=(?P<tag3>.*)$', views.do_search, name='searchpagefilters'),
    url(r'^searchterm=(?P<searchterm>.*)&page=(?P<page_number>\d+)&sorttype=(?P<sorttype>.*)$', views.do_search, name='searchpageview'),

    url(r'^searchterm=(?P<searchterm>.*)&(?P<direction>back)frompage=(?P<page_number>\d+)&sorttype=(?P<sorttype>.+)&tag2=(?P<tag2>.*)$', views.do_search, name='backpageview'),
    url(r'^searchterm=(?P<searchterm>.*)&(?P<direction>back)frompage=(?P<page_number>\d+)&sorttype=(?P<sorttype>.+)&tag1=(?P<tag1>.*)$', views.do_search, name='backpageview'),
    url(r'^searchterm=(?P<searchterm>.*)&(?P<direction>back)frompage=(?P<page_number>\d+)&sorttype=(?P<sorttype>.*)$', views.do_search, name='backpageview'),
    url(r'^doc=(?P<doc_id>.*)&searchterm=(?P<searchterm>.*)&tagedit=(?P<tagedit>True)$', views.get_content, name='contentview'),
    url(r'^doc=(?P<doc_id>.*)&searchterm=(?P<searchterm>.*)$', views.get_content, name='contentview'),
    url(r'^download=(?P<doc_id>.*)&(?P<hashfilename>.*)$', views.download, name='download'),
   ]

urlpatterns += staticfiles_urlpatterns()
