from django.conf.urls import url

from . import views
from . import api

urlpatterns = [
    url(r'^$', views.index, name='docs_index'),
    url(r'list/$', views.listfiles, name='listfiles'),
    url(r'^files/(?P<path>.*)$',views.file_display,name='listfiles'),
    url(r'^files',views.file_display,name='listfiles_base'),
    url(r'^api/changes/(?P<user_edit_id>.*)$',api.api_changes,name='api_changes'),
    url(r'^api/tasks/(?P<job>.*)$',api.api_task_progress,name='api_tasks'),
    url(r'^api/cleartasks$',api.api_clear_tasks,name='clear_tasks'),
    url(r'^indexedfiles/(?P<path>.*)$',views.list_solrfiles,name='list_solrfiles'),
#    url(r'^indexedfiles',views.list_solrfiles,name='list_solrfiles_base'),

#    url(r'filters=((.*)&.*)$', views.testlist, name='testview'),
#    url(r'^scandocs/$',views.scandocs,name='scandocs'),
]
