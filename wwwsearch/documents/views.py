# -*- coding: utf-8 -*-
"""PROCESS SOLR INDEX: 
EXTRACT FILES TO INDEX AND UPDATE INDEX """
from __future__ import unicode_literals, print_function
from __future__ import absolute_import
from django.http import HttpResponse
#from django.core.urlresolvers import reverse #DEPRACATED Django 2.0
from django.urls import reverse
from .forms import IndexForm
from django.shortcuts import render, redirect
from django.utils import timezone
import pytz #support localising the timezone
from .models import Collection,File,Index
from ownsearch.hashScan import HexFolderTable as hex
from ownsearch.hashScan import hashfile256 as hexfile
from ownsearch.hashScan import FileSpecTable as filetable
from ownsearch.pages import directory_tags
import datetime, hashlib, os, logging, requests
from . import indexSolr, updateSolr, solrICIJ, solrDeDup, solrcursor,correct_paths,documentpage
import ownsearch.solrJson as solr

from django.contrib.admin.views.decorators import staff_member_required
log = logging.getLogger('ownsearch.docs.views')
from usersettings import userconfig as config
from django.template import loader

BASEDIR=config['Models']['collectionbasepath'] #get base path of the docstore


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

@staff_member_required()
def listfiles(request):
    #get the core , or set the the default    
    page=documentpage.CollectionPage()
    page.getcores(request.user,request.session.get('mycore')) #arguments: user, storedcore
    if not page.stored_core:
        log.warning("Accessing listfiles before selecting index")
        return HttpResponse( "No index selected...please go back")
    
    mycore=page.cores.get(int(page.coreID)) # get the working core
    log.info('using index: {}'.format(getattr(mycore,'name','')))
    try:
        if request.method == 'POST' and 'list' in request.POST and 'choice' in request.POST:
            #get the files in selected collection
            if True:
                selected_collection=int(request.POST[u'choice'])
                thiscollection=Collection.objects.get(id=selected_collection)
                collectionpath=thiscollection.path
                filelist=File.objects.filter(collection=thiscollection)
                #print(filelist)
                return render(request, 'documents/listdocs.html',{'results':filelist,'collection':collectionpath })
#            except:
#                return HttpResponse( "Error...please go back")
    #SCAN DOCUMENTS IN A COLLECTION on disk hash contents and meta and update after changes.
        elif request.method == 'POST' and 'scan' in request.POST and 'choice' in request.POST:
            selected_collection=int(request.POST[u'choice'])
            thiscollection=Collection.objects.get(id=selected_collection)
            collectionpath=thiscollection.path
            #>> DO THE SCAN ON THIS COLLECTION
            if True:
                mycore.ping()
                scanfiles=updateSolr.scandocs(thiscollection)
                newfiles,deletedfiles,movedfiles,unchangedfiles,changedfiles=scanfiles
                if sum(scanfiles)>0:
                    return HttpResponse (" <p>Scanned "+str(sum(scanfiles))+" docs<p>New: "+str(newfiles)+"<p>Deleted: "+str(deletedfiles)+"<p> Moved: "+str(movedfiles)+"<p>Changed: "+str(changedfiles)+"<p>Unchanged: "+str(unchangedfiles))
                else:
                    return HttpResponse (" Scan Failed!")
    #INDEX DOCUMENTS IN COLLECTION IN SOLR
        elif request.method == 'POST' and 'index' in request.POST and 'choice' in request.POST:
            if True:
                #print('try to index in Solr')
                mycore.ping()
                selected_collection=int(request.POST[u'choice'])
                thiscollection=Collection.objects.get(id=selected_collection)
                icount,iskipped,ifailed,skippedlist,failedlist=indexdocs(thiscollection,mycore) #GO INDEX THE DOCS IN SOLR
                return HttpResponse ("Indexing.. <p>indexed: {} <p>skipped: {}<p>{}<p>failed: {}<p>{}".format(icount,iskipped,skippedlist,ifailed,failedlist))

    #INDEX VIA ICIJ 'EXTRACT' DOCUMENTS IN COLLECTION IN SOLR
        elif request.method == 'POST' and 'indexICIJ' in request.POST and 'choice' in request.POST:
            if True:
                #print('try to index in Solr')
                mycore.ping()
                selected_collection=int(request.POST[u'choice'])
                thiscollection=Collection.objects.get(id=selected_collection)
                icount,iskipped,ifailed,skippedlist,failedlist=indexdocs(thiscollection,mycore,forceretry=True,useICIJ=True) #GO INDEX THE DOCS IN SOLR
                return HttpResponse ("Indexing with ICIJ tool.. <p>indexed: {} <p>skipped: {}<p>{}<p>failed: {}<p>{}".format(icount,iskipped,skippedlist,ifailed,failedlist))
    
    #INDEX VIA ICIJ 'EXTRACT' DOCUMENTS IN COLLECTION IN SOLR ::: NO OCR PROCES
        elif request.method == 'POST' and 'indexICIJ_NO_OCR' in request.POST and 'choice' in request.POST:
            if True:
                #print('try to index in Solr')
                mycore.ping()
                selected_collection=int(request.POST[u'choice'])
                thiscollection=Collection.objects.get(id=selected_collection)
                icount,iskipped,ifailed,skippedlist,failedlist=indexdocs(thiscollection,mycore,forceretry=True,useICIJ=True,ocr=False) #GO INDEX THE DOCS IN SOLR
                return HttpResponse ("Indexing with ICIJ tool (no OCR).. <p>indexed: {} <p>skipped: {}<p>{}<p>failed: {}<p>{}".format(icount,iskipped,skippedlist,ifailed,failedlist))    
    
    
    #CURSOR SEARCH OF SOLR INDEX
        elif request.method == 'POST' and 'solrcursor' in request.POST and 'choice' in request.POST:
            #print('try cursor scan of Solr Index')
            if True:
                mycore.ping()
                selected_collection=int(request.POST[u'choice'])
                thiscollection=Collection.objects.get(id=selected_collection)
            #print (thiscollection,mycore)
                match,skipped,failed=indexcheck(thiscollection,mycore) #GO SCAN THE SOLR INDEX
                return HttpResponse ("Checking solr index.. <p>files indexed: "+str(match)+"<p>files not found:"+str(skipped)+"<p>errors:"+str(failed))
    #REMOVE DUPLICATES FROM SOLR INDEX
        elif request.method == 'POST' and 'dupscan' in request.POST:
            print('try scanning for duplicates')
            if True:
                mycore.ping()
            #print (thiscollection,mycore)
                dupcount,deletecount=solrDeDup.filepathdups(mycore,delete=True) #GO REMOVE DUPLICATES
                return HttpResponse ("Checking solr index for duplicate paths/filenames in solr index \""+str(mycore)+"\"<p>duplicates found: "+str(dupcount)+"<p>files removed: "+str(deletecount))
     #CHECK PATHS
        elif request.method== 'POST' and 'path-check' in request.POST and 'choice' in request.POST:
            if True:
                mycore.ping()
                selected_collection=int(request.POST[u'choice'])
                thiscollection=Collection.objects.get(id=selected_collection)
                correct_paths.check(mycore,thiscollection)
                return HttpResponse('checked paths')
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


#@staff_member_required()
#def list_solrfiles(request,path=''):
#    """display list of files in solr index"""
#
#    ##TODO duplication - 
#    """get the core , or set the the default """
#    thisuser=request.user
#    storedcoreID=int(request.session.get('mycore'))
#    try:
#        authcores=authorise.AuthorisedCores(thisuser,storedcore=storedcoreID)
#        coreID=authcores.mycoreID
#        if 'mycore' not in request.session:  #set default if no core selected
#            request.session['mycore']=coreID
#    except authorise.NoValidCore as e:
#        log.warning('Cannot find any valid coreID in authorised corelist')
#        return HttpResponse('Missing any config data for any authorised index: contact administrator')
#
#    log.debug('CORE ID: {}'.format(coreID))
#    
#    if request.method=='POST': #if data posted # switch core
#        #print('post data')
#        form=IndexForm(request.POST)
#        log.debug('Form: {} Valid: {} Post data: {}'.format(form.__dict__,form.is_valid(),request.POST))
#        if form.is_valid():
#            coreID=form.cleaned_data['corechoice']
#            log.debug('change core to {}'.format(coreID))
#            request.session['mycore']=coreID
#            authcores.mycore=authcores[coreID]
#        else:
#            log.debug('posted form is not valid')
#
#    else:
#        form=IndexForm(initial={'corechoice':coreID})
#        log.debug('Core set in request: {}'.format(request.session['mycore']))
#    
#    mycore=authcores.mycore
#    log.debug('mycore: {}'.format(mycore))
#    searchterm="extract_paths:{}".format(path)
#    result=solrcursor.cursor(mycore,searchterm=searchterm,keyfield="docname")
#    log.debug(result)
#    
#    return render(request,'filedisplay/solr_listindex.html',
#          {'result': result,
#          	'form':form,
##          	'rootpath':rootpath, 'tags':tags, 'form':form, 'path':path
#          })

@staff_member_required()
def file_display(request,path=''):
    """display files in a directory"""
    
    def index_maker(path,index_collections):
        def _index(root,depth,index_collections):
            #print ('Root',root)
            if depth<2:
                files = os.listdir(root)
                for mfile in files:
                    t = os.path.join(root, mfile)
                    relpath=os.path.relpath(t,BASEDIR)
                    if os.path.isdir(t):
                        subfiles=_index(os.path.join(root, t),depth+1,index_collections)
                        #print(root,subfiles)
                        yield loader.render_to_string('filedisplay/p_folder.html',
                                                       {'file': mfile,
                                                       	'filepath':relpath,
                                                       	'rootpath':path,
                                                        'subfiles': subfiles,
                                                        	})
                        continue
                    else:
                        stored,indexed=model_index(t,index_collections)
                        #log.debug('Local check: {},indexed: {}, stored: {}'.format(t,indexed,stored))
                        yield loader.render_to_string('filedisplay/p_file.html',{'file': mfile, 'local_index':stored,'indexed':indexed})
                        continue
        basepath=os.path.join(BASEDIR,path)
        log.debug('Basepath: {}'.format(basepath))
        if os.path.isdir(basepath):
            return _index(basepath,0,index_collections)
        else:
            return "Invalid directory"
    
    #get the core , or set the the default    
    page=documentpage.FilesPage()
    page.getcores(request.user,request.session.get('mycore')) #arguments: user, storedcore
    page.chooseindexes(request.method,request_postdata=request.POST)
    page.get_collections() #filter authorised collections
#        log.debug('Core set in request: {}'.format(request.session['mycore']))
    log.debug('CORE ID: {}'.format(page.coreID))    
        
    c = index_maker(path,page.authorised_collections)
    if path:
        rootpath=path
        tags=directory_tags(path)
    else:
        rootpath=""
        tags=None
    return render(request,'filedisplay/listindex.html',
                               {'subfiles': c, 'rootpath':rootpath, 'tags':tags, 'form':page.form, 'path':path})

def model_index(path,index_collections,hashcheck=False):
    """check if file scanned into model index"""
    stored=File.objects.filter(filepath=path, collection__in=index_collections)
    if stored:
        indexed=stored.exclude(solrid='')
        return stored,indexed
    else:
        return None,None


#checking for what files in existing solrindex
def indexcheck(collection,thiscore):

    #get the basefilepath
    docstore=config['Models']['collectionbasepath'] #get base path of the docstore

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
            relpath=os.path.relpath(file.filepath,start=docstore) #extract the relative path from the docstore
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
                    print('solrdata:',vars(solrdata))
                    file.indexedSuccess=True
                    file.solrid=solrdata.id
                    file.save()
                    counter+=1
                    print ('PATH :'+file.filepath+' indexed successfully (HASHMATCH)', 'Solr \'id\': '+solrdata.id)
                #NO MATCHES< RETURN FAILURE
                else:
                    log.info(file.filepath+'.. not found in Solr index')
                    file.indexedSuccess=False
                    file.solrid='' #wipe any stored solr id; DEBUG: this wipes also oldsolr ids scheduled for delete
                    file.save()
                    skipped+=1
        return counter,skipped,failed

#MAIN METHOD FOR EXTRACTING DATA
def indexdocs(collection,mycore,forceretry=False,useICIJ=False,ocr=True): #index into Solr documents not already indexed
    #need to check if mycore and collection are valid objects
    if isinstance(mycore,solr.SolrCore) == False or isinstance(collection,Collection) == False:
        log.warning('indexdocs() parameters invalid')
        return 0,0,0,[],[]
    if True:
        counter=0
        skipped=0
        failed=0
        skippedlist,failedlist=[],[]
        #print(collection)
        filelist=File.objects.filter(collection=collection)
        #main loop
        for file in filelist:
            if file.indexedSuccess:
                #skip this file, it's already indexed
                #print('Already indexed')
                skipped+=1
                skippedlist.append(file.filepath)
            elif file.indexedTry==True and forceretry==False:
                #skip this file, tried before and not forceing retry
                log.info('Skipped on previous index failure; no retry: {}'.format(file.filepath))
                skipped+=1
                skippedlist.append(file.filepath)
            elif indexSolr.ignorefile(file.filepath) is True:
                #skip this file because it is on ignore list
                log.info('Ignoring: {}'.format(file.filepath))
                skipped+=1
                skippedlist.append(file.filepath)
            else: #do try to index this file
                log.info('Attempting index of {}'.format(file.filepath))
                #print('trying ...',file.filepath)
                #if was previously indexed, store old solr ID and then delete if new index successful
                oldsolrid=file.solrid
                #get source
                try:
                    sourcetext=file.collection.source.sourceDisplayName
                except:
                    sourcetext=''
                    log.debug('No source defined for file: {}'.format(file.filename))
                #getfile hash if not already done
                if not file.hash_contents:
                    file.hash_contents=hexfile(file.filepath)
                    file.save()
                #now try the extract
                if useICIJ:
                    log.info('using ICIJ extract method..')
                    result = solrICIJ.ICIJextract(file.filepath,mycore,ocr=ocr)
                    if result is True:
                        try:
                            new_id=solr.hashlookup(file.hash_contents,mycore).results[0].id #id of the first result returned
                            file.solrid=new_id
                            log.info('(ICIJ extract) New solr ID: '+new_id)
                        except:
                            log.warning('Extracted doc not found in index')
                            result=False
                    if result is True:
                    #post extract process -- add meta data field to solr doc, e.g. source field
                        try:
                            sourcetext=file.collection.source.sourceDisplayName
                        except:
                            sourcetext=''
                        if sourcetext:
                            try:
                                result=solrICIJ.postprocess(new_id,sourcetext,file.hash_contents,mycore)
                                if result==True:
                                    log.debug('Added source: \"{}\" to docid: {}'.format(sourcetext,new_id))
                            except Exception as e:
                                log.error('Cannot add meta data to solrdoc: {}, error: {}'.format(new_id,e))
                else:
                    try:
                        result=indexSolr.extract(file.filepath,file.hash_contents,mycore,sourcetext=sourcetext)
                    except solr.SolrCoreNotFound as e:
                        raise indexSolr.ExtractInterruption('Indexing interrupted after '+str(counter)+' files extracted, '+str(skipped)+' files skipped and '+str(failed)+' files failed.')
                    except solr.SolrConnectionError as e:
                        raise indexSolr.ExtractInterruption('Indexing interrupted after '+str(counter)+' files extracted, '+str(skipped)+' files skipped and '+str(failed)+' files failed.')
                    except requests.exceptions.RequestException as e:
                        raise indexSolr.ExtractInterruption('Indexing interrupted after '+str(counter)+' files extracted, '+str(skipped)+' files skipped and '+str(failed)+' files failed.')               
         
                if result is True:
                    counter+=1
                    #print ('PATH :'+file.filepath+' indexed successfully')
                    if not useICIJ:
                        file.solrid=file.hash_filename  #extract uses hashfilename for an id , so add it

                    file.indexedSuccess=True
                    #now delete previous solr doc (if any): THIS IS ONLY NECESSARY IF ID CHANGES  
                    log.info('Old ID: '+oldsolrid+' New ID: '+file.solrid)
                    if oldsolrid and oldsolrid!=file.solrid:
                        log.info('now delete old solr doc'+str(oldsolrid))
                        #DEBUG: NOT TESTED YET
                        response,status=updateSolr.delete(oldsolrid,mycore)
                        if status:
                            log.info('Deleted solr doc with ID:'+oldsolrid)
                    file.save()
                else:
                    log.info('PATH : '+file.filepath+' indexing failed')
                    failed+=1
                    file.indexedTry=True  #set flag to say we've tried
                    log.debug('Saving updated file info in database')
                    file.save()
                    failedlist.append(file.filepath)
        return counter,skipped,failed,skippedlist,failedlist
    
def pathHash(path):
    m=hashlib.md5()
    m.update(path.encode('utf-8'))  #encoding avoids unicode error for unicode paths
    return m.hexdigest()

   