# -*- coding: utf-8 -*-
"""PICK A DIRECTORY POPUP"""
from __future__ import unicode_literals, print_function
from __future__ import absolute_import
from django.http import HttpResponse
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render
from django.template import loader
from documents import documentpage,file_utils

import os, configs, logging
log = logging.getLogger('ownsearch.picker.views')
dupsconfig=configs.config.get('Dups')
MEDIAROOT=dupsconfig.get('rootpath') if dupsconfig else None


@staff_member_required()
def pick_folder(request,path='',next_url=''):
    default_destination=request.session.get('destination')
    if path=='' and default_destination:
        path=default_destination
    normpath=os.path.normpath(path) if path else '' #cope with windows filepaths
    log.info(f'Displaying folders below: {normpath} with next_url:  {next_url}')
    #get the core , or set the the default    
    page=documentpage.FilesPage(path=normpath)
    path_info=request.META.get('PATH_INFO')
    request.session["back_url"]=path_info  
    try:
        c = Folder_Index(normpath,None,False,rootpath=MEDIAROOT,next_url=next_url)._index
    except file_utils.EmptyDirectory:
        c=None
    if path:
        rootpath=normpath
        tags=file_utils.directory_tags(normpath)
    else:
        rootpath=""
        tags=None
    return render(request,'pickfile/filedisplay/listfolders.html',
         {'subfiles': c, 'rootpath':rootpath, 'tags':tags, 'path':path, 'next_url':next_url})

class Folder_Index(file_utils.Index_Maker):
	
    @staticmethod
    def file_html(mfile,_stored,_indexed,dupcheck,relpath,path):	
        return ""

    @staticmethod
    def folder_html_nosub(mfile,relpath,path,is_collection_root,is_inside_collection):
        return loader.render_to_string('pickfile/filedisplay/p_folder_nosub.html',
            {'file': mfile,
             'filepath':relpath,
             'rootpath':path,
             'is_collection_root':is_collection_root,
             'is_inside_collection':is_inside_collection,
            })
#