# -*- coding: utf-8 -*-
"""DUPLICATES AND ORPHANS FINDER AND MEDIA SCANNER"""
from __future__ import unicode_literals
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.shortcuts import render, redirect
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from . import pages
from documents import file_utils, documentpage as pages
from dups import forms
import os, configs, logging,json
log = logging.getLogger('ownsearch.dups.views')

dupsconfig=configs.config.get('Dups')
DEFAULT_MASTERINDEX_PATH=dupsconfig.get('masterindex_path') if dupsconfig else None
MEDIAROOT=dupsconfig.get('rootpath') if dupsconfig else None

#log.debug(MEDIAROOT)
#log.debug(DEFAULT_MASTERINDEX_PATH)

@staff_member_required()
def index(request,path='',duplist=False):
    """display files in a directory"""

    log.debug(f'path: {path}')
    log.debug(f'Mediaroot: {MEDIAROOT}')
    
    path=os.path.normpath(path) if path else '' #cope with windows filepaths
    
    log.debug(f'Dups only: {duplist}')
    
    page=pages.FilesPage(request=request,default_master=DEFAULT_MASTERINDEX_PATH)
    
    
    if not MEDIAROOT or not page.masterindex_path:
    	    return HttpResponse ("Missing 'Dups' configuration information in user.settings : set the 'rootpath' and 'masterindex_path' variables")
    
    if request.method == 'POST':
       if 'scan' in request.POST:
           log.debug('scanning')
           page.local_scanpath=request.POST.get('local-path')
           page.local_scanpath=os.path.normpath(page.local_scanpath) if page.local_scanpath else ''
           if not os.path.exists(os.path.join(MEDIAROOT,page.local_scanpath)):
               log.debug('scan request sent non-existent path')
               return redirect('dups_index',path=path)
           specs=file_utils.BigFileIndex(os.path.join(MEDIAROOT,page.local_scanpath),label='local')
           #print(specs.files)
           specs.hash_scan()
           request.session['scanfolder']=page.local_scanpath
           return redirect('dups_index',path=path)

       elif 'masterscan' in request.POST:
           full_masterpath=os.path.join(MEDIAROOT,page.masterindex_path)
           full_masterpath=os.path.normpath(full_masterpath) if full_masterpath else ''
           log.debug(f'scanning master: {full_masterpath}')
           masterspecs=file_utils.BigFileIndex(full_masterpath,label='master')
           masterspecs.hash_scan()
           request.session['masterfolder']=page.masterindex_path
           return redirect('dups_index',path=path)           

    #page.masterform=forms.MasterForm()
    
    page.get_stored(MEDIAROOT)
    
    #log.debug(page.masterspecs)
    
    if os.path.exists(os.path.join(MEDIAROOT,path)):
        #page.masterpath=masterindex_path

        if page.masterindex_path:
            page.inside_master=path.startswith(page.masterindex_path)
        
        if duplist:
            #display only duplicates
            c=file_utils.check_master_dups_html(os.path.join(MEDIAROOT,path),scan_index=page.specs,master_index=page.masterspecs)            

        else:
            try:
                c = file_utils.Dups_Index_Maker(path,'',specs=page.specs,masterindex=page.masterspecs,rootpath=MEDIAROOT)._index
            except file_utils.EmptyDirectory as e:
                c= None
        #log.debug(c)
        
        
        if path:
            rootpath=path
            tags=file_utils.directory_tags(path)
        else:
            rootpath=""
            tags=None
        return render(request,'dups/listindex.html',
                                   {'page': page, 'subfiles': c, 'rootpath':rootpath, 'tags':tags,  'path':path,})
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
                folder_type=request.POST.get('folder_type')
                folder_path=request.POST.get('folder_path')
                folder_path=os.path.normpath(folder_path) if folder_path else '' #cope with windows filepaths
                log.debug(folder_type)
                log.debug(folder_path)
                if folder_type=='local':
                    request.session['scanfolder']=folder_path
                    jsonresponse={'saved':True}
                if folder_type=='master':
                    new_masterindex_path=folder_path
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
    
@staff_member_required()
def file_dups_api(request):
    """ajax API to get duplicates by hash"""
    jsonresponse={'dups':'', 'message':'No files or error'}
    try:
        if not request.is_ajax():
            return HttpResponse('API call: Not Ajax')
        else:
            log.debug(request.GET)

            if request.method == 'GET':
                _hash=request.GET.get('hash')
                if file_utils.safe_hash(_hash):
                    masterindex_path=request.session.get('masterfolder',DEFAULT_MASTERINDEX_PATH)
                    if masterindex_path:
                        masterspecs=file_utils.StoredBigFileIndex(os.path.join(MEDIAROOT,masterindex_path))
                        duplist=file_utils.specs_path_list(masterspecs,_hash)
                        log.debug(duplist)
                        jsonresponse={'dups':duplist}
                    else:
                        log.debug('no masterfolder stored')
                else:
                    log.debug('invalid hash')
            else:
                log.debug('Error: send a Get request')
    except Exception as e:
        log.debug(e)
    log.debug('Json response:{}'.format(jsonresponse))
    return JsonResponse(jsonresponse)
    
@staff_member_required()
def file_dups(request,_hash):
    duplist_master,duplist_local="",""
    page=pages.FilesPage(request=request,default_master=DEFAULT_MASTERINDEX_PATH)
    page.get_stored(MEDIAROOT)
    page.hash=None
    if file_utils.safe_hash(_hash):
        page.hash=_hash
        
        if request.method=='POST':
            checklist=request.POST.getlist('checked')
            if request.POST.get('delete-button')=='Delete':
                log.debug(f'Deleting: {checklist}')
                for f in checklist:
                    result=file_utils.delete_file(f)
                    log.info(f'Deleted: {f} Result: {result}')
                    if page.masterspecs:
                        page.masterspecs.delete_record(f)
                        
        log.debug(page.__dict__)
        if page.masterspecs:
            duplist_master=file_utils.specs_path_list(page.masterspecs,_hash)
            log.debug(duplist_master)
        if page.masterspecs:
            duplist_local=file_utils.specs_path_list(page.specs,_hash)
            log.debug(duplist_local)
        
        if duplist_local or duplist_master:
            return render(request,'dups/list_files.html',
                                   {'page': page, 'files_master': duplist_master,'files_local':duplist_local,})
        else:
            return HttpResponse('no dups')
    return HttpResponse('error')
    
    
    