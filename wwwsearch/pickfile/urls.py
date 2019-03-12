from django.urls import path
from django.conf.urls import url

from . import views

urlpatterns = [
#    url(r'^ajax$',views.dups_api,name='dups_api'),
#    url(r'^files_api$',views.file_dups_api,name='files_dups_api'),
#    url(r'^files/(?P<_hash>.*)$',views.file_dups,name='file_dups'),
#    url(r'^folder/(?P<path>.*)&dups$',views.index,{'duplist':True},name='dups_index_dups'),
#    url(r'^folder/(?P<path>.*)$',views.index,name='dups_index'),
#    url('^&dups$', views.index, {'duplist':True},name='index_base_dups'),
    url(r'^(?P<path>.*)&next_url=(?P<next_url>.*)$',views.pick_folder,name='picker_path_next'),
    url(r'^(?P<path>.*)$',views.pick_folder,name='picker_path'),
    url('^$', views.pick_folder, name='picker'),

]
