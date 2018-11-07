# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import os
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.shortcuts import render, redirect
from . import pages
from documents import file_utils
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from dups import forms
import configs

import logging,json
log = logging.getLogger('ownsearch.dups.views')

dupsconfig=configs.config.get('Dups')
DEFAULT_MASTERINDEX_PATH=dupsconfig.get('masterindex_path') if dupsconfig else None
MEDIAROOT=dupsconfig.get('rootpath') if dupsconfig else None

#log.debug(MEDIAROOT)
#log.debug(DEFAULT_MASTERINDEX_PATH)

@staff_member_required()
def index(request,path=''):
    """display files in a directory"""
    
    local_scanpath=request.session.get('scanfolder')
    masterindex_path=request.session.get('masterfolder',DEFAULT_MASTERINDEX_PATH)
    log.debug(f'Masterindex path: {masterindex_path}')
    log.debug(f'path: {path}')
    log.debug(f'Mediaroot: {MEDIAROOT}')
    
    if not MEDIAROOT or not masterindex_path:
    	    return HttpResponse ("Missing 'Dups' configuration information in user.settings : set the 'rootpath' and 'masterindex_path' variables")
    
    if request.method == 'POST':
       if 'scan' in request.POST:
           log.debug('scanning')
           local_scanpath=request.POST.get('local-path')
           if not os.path.exists(os.path.join(MEDIAROOT,local_scanpath)):
               log.debug('scan request sent non-existent path')
               return redirect('dups_index',path=path)
           specs=file_utils.BigFileIndex(os.path.join(MEDIAROOT,local_scanpath))
           #print(specs.files)
           specs.hash_scan()
           request.session['scanfolder']=local_scanpath
           return redirect('dups_index',path=path)

       elif 'masterscan' in request.POST:
           full_masterpath=os.path.join(MEDIAROOT,masterindex_path)
           log.debug(f'scanning master: {full_masterpath}')
           masterspecs=file_utils.BigFileIndex(full_masterpath)
           masterspecs.hash_scan()
           request.session['masterfolder']=masterindex_path
           return redirect('dups_index',path=path)           

    page=pages.FilesPage()
    page.scanpath=local_scanpath
    #page.masterform=forms.MasterForm()
    
    log.debug(f'stored scanpath: {page.scanpath}')
    if page.scanpath:
        try:
            page.specs=file_utils.StoredBigFileIndex(os.path.join(MEDIAROOT,page.scanpath))
        except:
            page.specs=None
    else:
        page.specs=None
        
    try:
        page.masterspecs=file_utils.StoredBigFileIndex(os.path.join(MEDIAROOT,masterindex_path))
    except:
        page.masterspecs=None
    
    if os.path.exists(os.path.join(MEDIAROOT,path)):
        page.masterpath=masterindex_path
        log.debug(f'Path{path} Master: {masterindex_path}')
        page.masterpath_url=f'/dups/folder/{masterindex_path}'
        if masterindex_path:
            page.inside_master=path.startswith(masterindex_path)
        try:
            c = file_utils.index_maker(path,'',specs=page.specs,masterindex=page.masterspecs,rootpath=MEDIAROOT)
        except file_utils.EmptyDirectory as e:
            c= None
        log.debug(c)
        if path:
            rootpath=path
            tags=file_utils.directory_tags(path)
        else:
            rootpath=""
            tags=None
        return render(request,'dups/listindex.html',
                                   {'page': page, 'subfiles': c, 'rootpath':rootpath, 'tags':tags,  'path':path})
    else:
        return redirect('dups_index',path='')


@login_required
def dups_api(request):
    """ajax API to update data"""
    jsonresponse={'saved':False,'message':'Unknown error'}
    try:
        if not request.is_ajax():
            return HttpResponse('API call: Not Ajax')
        else:
            if request.method == 'POST':
                log.debug('Raw Data: {}'.format(request.body))
                response_json = json.dumps(request.POST)
                data = json.loads(response_json)
                log.debug ("Json data: {}.".format(data))
                if data.get('folder_type')=='local':
                    request.session['scanfolder']=data.get('folder_path')
                    jsonresponse={'saved':True}
                if data.get('folder_type')=='master':
                    new_masterindex_path=data.get('folder_path')
                    request.session['masterfolder']=new_masterindex_path
                    jsonresponse={'saved':True}
                    if new_masterindex_path != DEFAULT_MASTERINDEX_PATH:
                       configs.userconfig.update('Dups','masterindex_path',new_masterindex_path)
                log.debug('Json response:{}'.format(jsonresponse))
            else:
                log.debug('Error: Get to API')
    except Exception as e:
        log.debug(e)
    return JsonResponse(jsonresponse)