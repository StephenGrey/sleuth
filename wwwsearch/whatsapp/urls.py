
from django.conf.urls import url
from django.contrib import admin
from . import views

urlpatterns = [
    url(r'^$', views.home,name='home'),
    url(r'^(?P<filter1>.*)/(?P<filter2>.*)$', views.messages, name='messages'),    
    url(r'^(?P<filter1>.*)$', views.messages, name='messages'),
]

