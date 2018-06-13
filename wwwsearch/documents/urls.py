from django.conf.urls import url

from . import views

urlpatterns = [
    url(r'^$', views.index, name='docs_index'),
    url(r'list/$', views.listfiles, name='listfiles'),
    url(r'^files/(?P<path>.*)$',views.file_display,name='listfiles'),
    url(r'^files',views.file_display,name='listfiles_base'),

#    url(r'filters=((.*)&.*)$', views.testlist, name='testview'),
#    url(r'^scandocs/$',views.scandocs,name='scandocs'),
]
