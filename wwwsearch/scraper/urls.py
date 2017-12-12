from django.conf.urls import url
from . import views

urlpatterns = [
    url(r'^$', views.scrapeview, name='scrapeview'),
    url(r'^id=(?P<doc_id>.*)$', views.blogview, name='blogpostview'),
    ]