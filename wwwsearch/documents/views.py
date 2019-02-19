# -*- coding: utf-8 -*-
"""PROCESS SOLR INDEX: 
EXTRACT FILES TO INDEX AND UPDATE INDEX """
from __future__ import unicode_literals, print_function
from __future__ import absolute_import
from django.http import HttpResponse,JsonResponse
#from django.core.urlresolvers import reverse #DEPRACATED Django 2.0
from django.urls import reverse
from .forms import IndexForm
from django.shortcuts import render, redirect
from django.utils import timezone
import ast
import pytz #support localising the timezone
from .models import Collection,File,Index,UserEdit
from ownsearch.hashScan import HexFolderTable as hex
from ownsearch.hashScan import hashfile256 as hexfile
from ownsearch.hashScan import FileSpecTable as filetable
from .file_utils import directory_tags
import datetime, hashlib, os, logging, requests, json 
from . import indexSolr, updateSolr, index_check, solrDeDup, solrcursor,correct_paths,documentpage,redis_cache,file_utils
import ownsearch.solrJson as solr
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
log = logging.getLogger('ownsearch.docs.views')
import configs
from watcher import watch_dispatch

BASEDIR=configs.config['Models']['collectionbasepath'] #get base path of the docstore
r=redis_cache.redis_connection

class NoIndexSelected(Exception):
    pass
    
@staff_member_required()
def index(request):
    """ Display collections, options to scan,list,extract """
    try:
        page=documentpage.CollectionPage()
        job_id=request.session.get('tasks')
        page.maxsize=indexSolr.MAXSIZE_MB
        page.timeout=indexSolr.TIMEOUT
        try:
            page.selected_collection=int(request.session.get('collection_selected'))
        except:
            page.selected_collection=None
        log.info(f'Stored jobs: {job_id}')                
        if job_id:
            job=f'SB_TASK.{job_id}'
            log.debug(f'job: {job}')
            page.results=watch_dispatch.get_extract_results(job)
            #log.debug(f'task results: {page.results}')
            page.job=job
        else:
            page.results=None
            page.job=None
        #get the core , or set the the default    

        page.getcores(request.user,request.session.get('mycore')) #arguments: user, storedcore
        page.chooseindexes(request.method,request_postdata=request.POST)
        page.get_collections() #filter authorised collections
    #        log.debug('Core set in request: {}'.format(request.session['mycore']))
        log.debug('CORE ID: {} COLLECTIONS: {}'.format(page.coreID,page.authorised_collections)) 
        request.session['mycore']=page.coreID

        return render(request, 'documents/scancollection.html',{'page': page})
    except Exception as e:
        log.error('Error: {}'.format(e))
        return HttpResponse('Can\'t find core/collection - retry')

def getcores(page,request):
    """get the core , or set the the default """   
    page.getcores(request.user,request.session.get('mycore')) #arguments: user, storedcore
    if not page.stored_core:
        log.warning("Accessing listfiles before selecting index")
        raise NoIndexSelected("No index selected")
    mycore=page.cores.get(int(page.coreID)) # get the working core
    log.info('using index: {}'.format(getattr(mycore,'name','')))
    return mycore

@staff_member_required()
def display_results(request,job_id=''):
    
    results=r.hgetall(job_id)
    #log.debug(results)
    if not results:
        return HttpResponse('No results to display')
    
    try:
        failed=results.get('failed_list')
        if failed:
            failed=json.loads(failed)
            #failed=ast.literal_eval(json.loads(failed))
    except KeyError:
        failed=None
    results['failed_list']=failed
    log.debug(f'Failed list {failed}')
    
    skipped=results.get('skipped_list')
    if skipped:
        results['skipped_list']=json.loads(skipped)
        #ast.literal_eval()
    #log.debug(f'Skipped list: {skipped}')
#    results['failed_list']=[('/Volumes/Crypt/ownCloud/testfolder/willerby.TIF', 'Solr post timeout')]
    #log.debug(results)
    return render(request,'documents/results.html',
          {'job_id':job_id, 'results':results})


@staff_member_required()
def listfiles(request):
    job_id=request.session.get('tasks')
    log.info(f'Stored jobs: {job_id}')
    page=documentpage.CollectionPage()
    page.maxsize=indexSolr.MAXSIZE_MB
    page.timeout=indexSolr.TIMEOUT
    try:
        mycore=getcores(page,request)
    except NoIndexSelected:
        return redirect('docs_index')
    
    try:
        if request.method == 'POST' and 'choice' in request.POST:
            selected_collection=int(request.POST[u'choice'])
            request.session['collection_selected']=selected_collection
            thiscollection=Collection.objects.get(id=selected_collection)
            collectionpath=thiscollection.path
            
            _OCR=True if 'ocr' in request.POST else False
            _FORCE_RETRY=True if 'force_retry' in request.POST else False
             
            if 'maxsize' in request.POST:
                _maxsizeMB=int(request.POST.get('maxsize'))
                if _maxsizeMB != page.maxsize:
                    page.maxsize=_maxsizeMB
                    log.debug(f'New maxsize set to {page.maxsize}')
                    _maxsize=_maxsizeMB*(1024**2) 
                    configs.userconfig.update('Solr','maxsize',str(_maxsizeMB))
                    indexSolr.MAXSIZE_MB=page.maxsize
                    indexSolr.MAXSIZE=_maxsize
            
            if 'timeout' in request.POST:
                timeout=int(request.POST.get('timeout'))
                if timeout != page.timeout:
                    page.timeout=timeout
                    log.debug(f'New maxsize set to {timeout}')
                    configs.userconfig.update('Solr','solrtimeout',str(timeout))
                    indexSolr.TIMEOUT=page.timeout
                                
            if 'list' in request.POST:
            #get the files in selected collection
                filelist=File.objects.filter(collection=thiscollection)
                return render(request, 'documents/listdocs.html',{'results':filelist,'collection':collectionpath })

    #SCAN DOCUMENTS IN A COLLECTION on disk hash contents and meta and update after changes.
            elif 'scan' in request.POST:
            #>> DO THE SCAN ON THIS COLLECTION
                mycore.ping()
                job_id=watch_dispatch.make_scan_job(thiscollection.id,_test=0)
                if job_id:
                    request.session['tasks']=job_id
                    return redirect('docs_index')
#                    return HttpResponse(f"Indexing task created: id \"{job_id}\"")
                else:
                    return HttpResponse("Scannning of this collection already queued")


    #INDEX DOCUMENTS IN COLLECTION IN SOLR
            elif 'index' in request.POST:
                mycore.ping()
                
                job_id=watch_dispatch.make_index_job(thiscollection.id,_test=0,force_retry=_FORCE_RETRY)
                #ext=indexSolr.Extractor(thiscollection,mycore) #GO INDEX THE DOCS IN SOLR
                request.session['tasks']=job_id
                return redirect('docs_index')
                                
    #INDEX VIA ICIJ 'EXTRACT' DOCUMENTS IN COLLECTION IN SOLR
            elif 'indexICIJ' in request.POST:
                mycore.ping()
                job_id=watch_dispatch.make_index_job(thiscollection.id,_test=0,force_retry=_FORCE_RETRY,use_icij=True,ocr=_OCR)
                request.session['tasks']=job_id
                return redirect('docs_index')                
                
            elif 'scan_extract' in request.POST:
                mycore.ping()
                job_id=watch_dispatch.make_scan_and_index_job(thiscollection.id,_test=0,force_retry=_FORCE_RETRY,use_icij=False,ocr=_OCR)
                request.session['tasks']=job_id
                return redirect('docs_index') 
    
    #CURSOR SEARCH OF SOLR INDEX
            elif 'solrcursor' in request.POST:
                mycore.ping()
                match,skipped,failed=index_check.index_check(thiscollection,mycore) #GO SCAN THE SOLR INDEX
                
                results={
                'task':'check_index',
                'indexed':match,
                'not_found':skipped,
                'errors':failed,
                'path': collectionpath,
                }
                
                return render(request,'documents/results.html',
                {
                'job_id':'', 
                'results':results
                })
     #CHECK PATHS
            elif 'path-check' in request.POST:
                mycore.ping()
                correct_paths.check_solrpaths(mycore,thiscollection)
                return HttpResponse('checked paths')

            else:
                return redirect('docs_index')


    #REMOVE DUPLICATES FROM SOLR INDEX
        elif request.method == 'POST' and 'dupscan' in request.POST:
            log.debug('try scanning for duplicates')
            if True:
                mycore.ping()
            #print (thiscollection,mycore)
                dupcount,deletecount=solrDeDup.filepathdups(mycore,delete=True) #GO REMOVE DUPLICATES
                return HttpResponse ("Checking solr index for duplicate paths/filenames in solr index \""+str(mycore)+"\"<p>duplicates found: "+str(dupcount)+"<p>files removed: "+str(deletecount))
        else:
            return redirect('docs_index')
    except solr.SolrConnectionError:
        return HttpResponse("No connection to Solr index: (re)start Solr server")
    except solr.SolrCoreNotFound:
        return HttpResponse("Solr index not found: check index name in /admin")
    except indexSolr.ExtractInterruption as e:
        return HttpResponse ("Indexing interrupted -- Solr Server not available. \n"+e.message)
    except requests.exceptions.RequestException as e:
        print ('caught requests connection error')
        return HttpResponse ("Indexing interrupted -- Solr Server not available")
    except NoIndexSelected:
        return HttpResponse( "No index selected...please go back")


@login_required
def list_solrfiles(request,path=''):
    """display list of files in solr index"""

    try:
        page=documentpage.SolrFilesPage(path=path)
        page.getcores(request.user,request.session.get('mycore')) #arguments: user, storedcore
        page.chooseindexes(request.method,request_postdata=request.POST)
        tags=page.dirpath_tags
        log.debug("Tags: {}".format(tags))
    except NoIndexSelected:
        return HttpResponse('No index selected')

    log.debug('mycore: {}'.format(page.mycore.name))
    searchterm=file_utils.pathHash(path)
    searcharg="{}:{}".format(page.mycore.parenthashfield,searchterm)
    log.debug(f'Searchterm: {searcharg}')
    result=solrcursor.cursor(page.mycore,searchterm=searcharg,keyfield="docname")
    log.debug(result)
    return render(request,'documents/filedisplay/solr_listindex.html',
          {'result': result, 'form':page.form, 'path':page.docpath, 'tags':tags,
          })
#          	'rootpath':rootpath, 'tags':tags, 'form':form, 

@staff_member_required()
def file_display(request,path=''):
    """display files in a directory"""
    path=os.path.normpath(path) if path else '' #cope with windows filepaths
    #get the core , or set the the default    
    page=documentpage.FilesPage()
    log.debug(request.POST)
    page.getcores(request.user,request.session.get('mycore')) #arguments: user, storedcore
    page.check_index=True if request.session.get('check_index') else False
    page.chooseindexes(request.method,request_postdata=request.POST)
    log.debug('CORE ID: {}'.format(page.coreID))
    request.session['mycore']=page.coreID
    request.session['check_index']=page.check_index
    page.get_collections() #filter authorised collections
#        log.debug('Core set in request: {}'.format(request.session['mycore']))
    path_info=request.META.get('PATH_INFO')
    request.session["back_url"]=path_info  
    
#    is_collection_root=None
#    is_inside_collection=None
    c = file_utils.Index_Maker(path,page.authorised_collections,check_index=page.check_index)._index
    if path:
        rootpath=path
        tags=directory_tags(path)
    else:
        rootpath=""
        tags=None
    return render(request,'documents/filedisplay/listindex.html',
         {'subfiles': c, 'rootpath':rootpath, 'tags':tags, 'form':page.form, 'path':path, 'check_index':page.check_index})


@staff_member_required()
def list_collections(request):
    """list and edit collections for an index"""
    page=documentpage.FilesPage()
    log.debug(request.POST)
    page.getcores(request.user,request.session.get('mycore')) #arguments: user, storedcore
    page.chooseindexes(request.method,request_postdata=request.POST)
    log.debug('CORE ID: {}'.format(page.coreID))
    request.session['mycore']=page.coreID
    page.get_collections() #filter authorised collections
#        log.debug('Core set in request: {}'.format(request.session['mycore']))
    path_info=request.META.get('PATH_INFO')
    request.session["back_url"]=path_info  
    
    if request.method=='POST':
        page.collection_updates(request.POST) #action any changes to collections
        return redirect('list_collections')
    else:
        return render(request,'documents/listcollections.html',
         {'page': page})




@staff_member_required()
def make_collection(request,path='',confirm=False):
        #get the core , or set the the default    
    path=os.path.normpath(path) if path else ''
    log.debug(f'Attempting to add collection with path {path}, confirmed: {confirm}, with rootpath {BASEDIR}')
    page=documentpage.MakeCollectionPage(relpath=path,rootpath=BASEDIR)
    path_info=request.session.get("back_url")
    page.live_update=request.session.get("live_update")
    page.back_url=path_info
    log.debug(request.POST)
    page.getcores(request.user,request.session.get('mycore')) #arguments: user, storedcore
    page.chooseindexes(request.method,request_postdata=request.POST)
    page.get_collections() #filter authorised collections
    page.make_sources(request.method,request_postdata=request.POST,source_initial=request.session.get('mysource'))
    #log.debug(f'{page.authorised_collections_relpaths}')
    log.debug(f'Live update {page.live_update}')
    try:
        page.check_path()
        if confirm:
            page.make_collection()
            page.live_update=None

    except documentpage.NoValidCollection as e:
        page.error=f"{e}"
    if page.error:
        log.debug(page.error)
    request.session['mycore']=page.coreID
    request.session['mysource']=page.sourceID
    request.session['live_update']=page.live_update
    return render(request,'documents/makecollection.html',
         {'path':path,'source_form':page.source_form,'form':page.form, 'index':page.mycore.name, 'error':page.error, 'back_url':page.back_url,'success':page.success})

@staff_member_required()
def cancel_collection(request,path=''):
    path=os.path.normpath(path) if path else '' #cope with windows filepaths
    return render(request,'documents/cancelcollection.html',
         {'path':path})