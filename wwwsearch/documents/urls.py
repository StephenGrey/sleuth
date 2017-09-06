from django.conf.urls import url

from . import views

urlpatterns = [
    url(r'^$', views.index, name='index'),
    url(r'list/$', views.listfiles, name='listfiles'),
    url(r'^scandocs/$',views.scandocs,name='scandocs'),
]
