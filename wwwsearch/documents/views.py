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

import pytz #support localising the timezone
from .models import Collection,File,Index,UserEdit
from ownsearch.hashScan import HexFolderTable as hex
from ownsearch.hashScan import hashfile256 as hexfile
from ownsearch.hashScan import FileSpecTable as filetable
from .file_utils import directory_tags
import datetime, hashlib, os, logging, requests, json
from . import indexSolr, updateSolr, solrDeDup, solrcursor,correct_paths,documentpage,file_utils
import ownsearch.solrJson as solr

from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
log = logging.getLogger('ownsearch.docs.views')
from usersettings import userconfig as config

BASEDIR=config['Models']['collectionbasepath'] #get base path of the docstore


class NoIndexSelected(Exception):
    pass
    

@staff_member_required()
def index(request):
    """ Display collections, options to scan,list,extract """
    try:
        #get the core , or set the the default    
        page=documentpage.CollectionPage()
        page.getcores(request.user,request.session.get('mycore')) #arguments: user, storedcore
        page.chooseindexes(request.method,request_postdata=request.POST)
        page.get_collections() #filter authorised collections
    #        log.debug('Core set in request: {}'.format(request.session['mycore']))
        log.debug('CORE ID: {} COLLECTIONS: {}'.format(page.coreID,page.authorised_collections))    
        
        request.session['mycore']=page.coreID
        return render(request, 'documents/scancollection.html',{'form': page.form, 'latest_collection_list': page.authorised_collections})
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
def listfiles(request):

    page=documentpage.CollectionPage()
    
    try:
        mycore=getcores(page,request)
    except NoIndexSelected:
        return redirect('docs_index')
    
    try:
        if request.method == 'POST' and 'choice' in request.POST:
            selected_collection=int(request.POST[u'choice'])
            thiscollection=Collection.objects.get(id=selected_collection)
            collectionpath=thiscollection.path
            
            if 'list' in request.POST:
            #get the files in selected collection
                filelist=File.objects.filter(collection=thiscollection)
                return render(request, 'documents/listdocs.html',{'results':filelist,'collection':collectionpath })

    #SCAN DOCUMENTS IN A COLLECTION on disk hash contents and meta and update after changes.
            elif 'scan' in request.POST:
            #>> DO THE SCAN ON THIS COLLECTION
                mycore.ping()
                scanner=updateSolr.scandocs(thiscollection)
                if not scanner.scan_error:
                    return HttpResponse (" <p>Scanned {} docs<p>New: {} <p>Deleted: {}<p> Moved: {}<p>Unchanged: {}<p>Changed: {}".format(scanner.scanned_files,  scanner.new_files_count,scanner.deleted_files_count,scanner.moved_files_count,scanner.unchanged_files_count,scanner.changed_files_count))
                else:
                    return HttpResponse ("Scan Failed!")
    #INDEX DOCUMENTS IN COLLECTION IN SOLR
            elif 'index' in request.POST:
                mycore.ping()
                ext=indexSolr.Extractor(thiscollection,mycore) #GO INDEX THE DOCS IN SOLR
                return HttpResponse ("Indexing.. <p>indexed: {} <p>skipped: {}<p>{}<p>failed: {}<p>{}".format(ext.counter,ext.skipped,ext.skippedlist,ext.failed,ext.failedlist))
                
    #INDEX VIA ICIJ 'EXTRACT' DOCUMENTS IN COLLECTION IN SOLR
            elif 'indexICIJ' in request.POST:
                #print('try to index in Solr')
                mycore.ping()
                ext=indexSolr.Extractor(thiscollection,mycore,forceretry=True,useICIJ=True) #GO INDEX THE DOCS IN SOLR
                return HttpResponse ("Indexing with ICIJ tool.. <p>indexed: {} <p>skipped: {}<p>{}<p>failed: {}<p>{}".format(ext.counter,ext.skipped,ext.skippedlist,ext.failed,ext.failedlist))
    
    #INDEX VIA ICIJ 'EXTRACT' DOCUMENTS IN COLLECTION IN SOLR ::: NO OCR PROCES
            elif 'indexICIJ_NO_OCR' in request.POST :
                mycore.ping()                
                ext=indexSolr.Extractor(thiscollection,mycore,forceretry=True,useICIJ=True,ocr=False) #GO INDEX THE DOCS IN SOLR
                return HttpResponse ("Indexing with ICIJ tool (no OCR).. <p>indexed: {} <p>skipped: {}<p>{}<p>failed: {}<p>{}".format(ext.counter,ext.skipped,ext.skippedlist,ext.failed,ext.failedlist))    
    
    
    #CURSOR SEARCH OF SOLR INDEX
            elif 'solrcursor' in request.POST:
                mycore.ping()
                match,skipped,failed=indexcheck(thiscollection,mycore) #GO SCAN THE SOLR INDEX
                return HttpResponse ("Checking solr index.. <p>files indexed: "+str(match)+"<p>files not found:"+str(skipped)+"<p>errors:"+str(failed))

     #CHECK PATHS
            elif 'path-check' in request.POST:
                mycore.ping()
                correct_paths.check_solrpaths(mycore,thiscollection)
                return HttpResponse('checked paths')

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
    return render(request,'filedisplay/solr_listindex.html',
          {'result': result, 'form':page.form, 'path':page.docpath, 'tags':tags,
          })
#          	'rootpath':rootpath, 'tags':tags, 'form':form, 

@staff_member_required()
def file_display(request,path=''):
    """display files in a directory"""

    #get the core , or set the the default    
    page=documentpage.FilesPage()
    page.getcores(request.user,request.session.get('mycore')) #arguments: user, storedcore
    page.chooseindexes(request.method,request_postdata=request.POST)
    page.get_collections() #filter authorised collections
#        log.debug('Core set in request: {}'.format(request.session['mycore']))
    log.debug('CORE ID: {}'.format(page.coreID))    
        
    c = file_utils.index_maker(path,page.authorised_collections)
    if path:
        rootpath=path
        tags=directory_tags(path)
    else:
        rootpath=""
        tags=None
    return render(request,'filedisplay/listindex.html',
                               {'subfiles': c, 'rootpath':rootpath, 'tags':tags, 'form':page.form, 'path':path})


#checking for what files in existing solrindex
def indexcheck(collection,thiscore):

    #first get solrindex ids and key fields
    try:#make a dictionary of filepaths from solr index
        indexpaths=solrcursor.cursor(thiscore)
    except Exception as e:
        log.warning('Failed to retrieve solr index')
        log.warning(str(e))
        return 0,0,0

    #now compare file list with solrindex
    if True:
        counter=0
        skipped=0
        failed=0
        #print(collection)
        filelist=File.objects.filter(collection=collection)

        #main loop - go through files in the collection
        for file in filelist:
            relpath=os.path.relpath(file.filepath,start=BASEDIR) #extract the relative path from the docstore
            hash=file.hash_contents #get the stored hash of the file contents
            #print (file.filepath,relpath,file.id,hash)

	#INDEX CHECK: METHOD ONE : IF RELATIVE PATHS STORED MATCH
            if relpath in indexpaths:  #if the path in database in the solr index
                solrdata=indexpaths[relpath][0] #take the first of list of docs with this path
                #print ('PATH :'+file.filepath+' found in Solr index', 'Solr \'id\': '+solrdata['id'])
                file.indexedSuccess=True
                file.solrid=solrdata.id
                file.save()
                counter+=1
        #INDEX CHECK: METHOD TWO: CHECK IF FILE STORED IN SOLR INDEX UNDER CONTENTS HASH                
            else:
                log.debug('trying hash method')
                #is there a stored hash, if not get one
                if not hash:
                    hash=hexfile(file.filepath)
                    file.hash_contents=hash
                    file.save()
                #now lookup hash in solr index
                log.debug('looking up hash : '+hash)
                solrresult=solr.hashlookup(hash,thiscore).results
                log.debug(solrresult)
                if len(solrresult)>0:
                    #if some files, take the first one
                    solrdata=solrresult[0]
                    log.debug('solrdata: {}'.format(vars(solrdata)))
                    file.indexedSuccess=True
                    file.solrid=solrdata.id
                    file.save()
                    counter+=1
                    log.debug(f'PATH : {file.filepath} indexed successfully (HASHMATCH) Solr \'id\': {solrdata.id}')
                #NO MATCHES< RETURN FAILURE
                else:
                    log.info(file.filepath+'.. not found in Solr index')
                    file.indexedSuccess=False
                    file.solrid='' #wipe any stored solr id; DEBUG: this wipes also oldsolr ids scheduled for delete
                    file.save()
                    skipped+=1
        return counter,skipped,failed

#    
#def pathHash(path):
#    m=hashlib.md5()
#    m.update(path.encode('utf-8'))  #encoding avoids unicode error for unicode paths
#    return m.hexdigest()
#
#   