from django.conf.urls import url

from . import views
from . import api

urlpatterns = [
    url(r'^$', views.index, name='docs_index'),
    url(r'list/$', views.listfiles, name='listfiles'),
    url(r'admin/$', views.docadmin, name='docadmin'),
    url(r'makecollection/(?P<path>.*)&confirm$',views.make_collection,{'confirm':True},name='make_collection_confirm',),    
    url(r'makecollection/(?P<path>.*)$',views.make_collection,name='make_collection'),
    url(r'cancelcollection/(?P<path>.*)$',views.cancel_collection,name='cancel_collection'),
    url(r'results/(?P<job_id>.*)$', views.display_results, name='display_results'),
    url(r'listcollections$', views.list_collections, name='list_collections'),
    url(r'^files/(?P<path>.*)$',views.file_display,name='listfiles'),
    url(r'^files',views.file_display,name='listfiles_base'),
    url(r'^indexfile/(?P<folder_path>.*)&(?P<file_id>.*)$',views.index_file,name='index_file'),
    url(r'^api/changes/(?P<user_edit_id>.*)$',api.api_changes,name='api_changes'),
    url(r'^api/tasks/(?P<job>.*)$',api.api_task_progress,name='api_tasks'),
    url(r'^api/cleartasks$',api.api_clear_tasks,name='clear_tasks'),
    url(r'^api/clearduptasks$',api.api_clear_dup_tasks,name='clear_dup_tasks'),    
    url(r'^api/checkredis$',api.api_check_redis,name='redis_check'),
    url(r'^indexedfiles/(?P<path>.*)$',views.list_solrfiles,name='list_solrfiles'),
#    url(r'^indexedfiles',views.list_solrfiles,name='list_solrfiles_base'),

#    url(r'filters=((.*)&.*)$', views.testlist, name='testview'),
#    url(r'^scandocs/$',views.scandocs,name='scandocs'),
]
