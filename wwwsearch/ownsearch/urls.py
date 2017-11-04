from django.conf.urls import url
from . import views

urlpatterns = [
    url(r'^$', views.do_search, name='searchview'),
    url(r'^searchterm=(?P<searchterm>.*)&(?P<direction>next)afterpage=(?P<page>\d+)&sorttype=(?P<sorttype>.*)$', views.do_search, name='nextpageview'),
    url(r'^searchterm=(?P<searchterm>.*)&(?P<direction>back)frompage=(?P<page>\d+)&sorttype=(?P<sorttype>.*)$', views.do_search, name='backpageview'),
    url(r'^doc=(?P<doc_id>.*)&searchterm=(?P<searchterm>.*)$', views.get_content, name='contentview'),
    url(r'^download=(?P<doc_id>.*)&(?P<hashfilename>.*)$', views.download, name='download'),
   ]

