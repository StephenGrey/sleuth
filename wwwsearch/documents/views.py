# -*- coding: utf-8 -*-
from __future__ import unicode_literals, print_function
from django.http import HttpResponse
from .forms import IndexForm
from django.shortcuts import render, redirect
from django.utils import timezone
import pytz #support localising the timezone
from models import Collection,File
from ownsearch.hashScan import HexFolderTable as hex
from ownsearch.hashScan import hashfile256 as hexfile
from ownsearch.hashScan import FileSpecTable as filetable
import datetime, hashlib, os, logging, requests
import indexSolr, updateSolr
import ownsearch.solrSoup as solr
import solrcursor
from django.contrib.admin.views.decorators import staff_member_required
log = logging.getLogger('ownsearch')
from usersettings import userconfig as config

#set up solr indexes
cores=solr.getcores()
defaultcoreID=config['Solr']['defaultcoreid']
if defaultcoreID not in cores:
   defaultcoreID=cores.keys()[0]  #take any old core, if default not found

@staff_member_required()
def index(request):
    #get the core , or set the the default
    if 'mycore' not in request.session:  #set default if no core selected
        request.session['mycore']=defaultcoreID
    coreID=request.session.get('mycore')
    if request.method=='POST': #if data posted # switch core
#        print('post data')
        form=IndexForm(request.POST)
        if form.is_valid():
            coreID=form.cleaned_data['CoreChoice']
#            print ('change core to',coreID)
            request.session['mycore']=coreID
    else:
#        print(request.session['mycore'])
        form=IndexForm(initial={'CoreChoice':coreID})
#        print('Core set in request: ',request.session['mycore'])
    latest_collection_list = Collection.objects.filter(core=coreID)
    return render(request, 'documents/scancollection.html',{'form': form, 'latest_collection_list': latest_collection_list})

def listfiles(request):
#        print('Core set in request: ',request.session['mycore'])
    cores=solr.getcores() #fetch dictionary of installed solr indexes (cores)
    if 'mycore' in request.session:
        coreID=request.session['mycore'] #currentlyselected core
    else:
        print ('ERROR no stored core in session')
        return HttpResponse( "No index selected...please go back")
#        coreID=defaultcore
    mycore=cores[coreID] # get the working core
    print ('using', mycore.name)
    if request.method == 'POST' and 'list' in request.POST and 'choice' in request.POST:
        #get the files in selected collection
        try:
            selected_collection=int(request.POST[u'choice'])
            thiscollection=Collection.objects.get(id=selected_collection)
            collectionpath=thiscollection.path
            filelist=File.objects.filter(collection=thiscollection)
            #print(filelist)
            return render(request, 'documents/listdocs.html',{'results':filelist,'collection':collectionpath })
        except:
            return HttpResponse( "Error...please go back")
#SCAN DOCUMENTS IN A COLLECTION on disk hash contents and meta and update after changes.
    elif request.method == 'POST' and 'scan' in request.POST and 'choice' in request.POST:
        selected_collection=int(request.POST[u'choice'])
        thiscollection=Collection.objects.get(id=selected_collection)
        collectionpath=thiscollection.path
        #>> DO THE SCAN ON THIS COLLECTION
        try:
            mycore.ping()
            scanfiles=updateSolr.scandocs(thiscollection)
            newfiles,deletedfiles,movedfiles,unchangedfiles,changedfiles=scanfiles
            if sum(scanfiles)>0:
                return HttpResponse (" <p>Scanned "+str(sum(scanfiles))+" docs<p>New: "+str(newfiles)+"<p>Deleted: "+str(deletedfiles)+"<p> Moved: "+str(movedfiles)+"<p>Changed: "+str(changedfiles)+"<p>Unchanged: "+str(unchangedfiles))
            else:
                return HttpResponse (" Scan Failed!")
        except solr.SolrConnectionError:
            return HttpResponse("No connection to Solr index: (re)start Solr server")
#INDEX DOCUMENTS IN COLLECTION IN SOLR
    elif request.method == 'POST' and 'index' in request.POST and 'choice' in request.POST:
        try:
            #print('try to index in Solr')
            mycore.ping()
            selected_collection=int(request.POST[u'choice'])
            thiscollection=Collection.objects.get(id=selected_collection)
            icount,iskipped,ifailed=indexdocs(thiscollection,mycore) #GO INDEX THE DOCS IN SOLR
            return HttpResponse ("Indexing.. <p>indexed: "+str(icount)+"<p>skipped:"+str(iskipped)+"<p>failed:"+str(ifailed))
        except indexSolr.ExtractInterruption as e:
            return HttpResponse ("Indexing interrupted -- Solr Server not available. \n"+e.message)
        except solr.SolrConnectionError as e:
            #print (e)
            return HttpResponse("No connection to Solr index: (re)start Solr server")
        except requests.exceptions.RequestException as e:
            print ('caught requests connection error')
            return HttpResponse ("Indexing interrupted -- Solr Server not available")

#CURSOR SEARCH OF SOLR INDEX
    elif request.method == 'POST' and 'solrcursor' in request.POST and 'choice' in request.POST:
        #print('try cursor scan of Solr Index')
        try:
            mycore.ping()
            selected_collection=int(request.POST[u'choice'])
            thiscollection=Collection.objects.get(id=selected_collection)
        #print (thiscollection,mycore)
            match,skipped,failed=indexcheck(thiscollection,mycore) #GO SCAN THE SOLR INDEX
            return HttpResponse ("Checking solr index.. <p>files indexed: "+str(match)+"<p>files not found:"+str(skipped)+"<p>errors:"+str(failed))
        except solr.SolrConnectionError:
            return HttpResponse("No connection to Solr index: (re)start Solr server")
    else:
        return redirect('index')
#    return render(request, 'documents/listdocs.html',{'results':filelist,'collection':collectionpath })



#checking for what files in existing solrindex
def indexcheck(collection,thiscore):

    #get the basefilepath
    docstore=config['Models']['collectionbasepath'] #get base path of the docstore

    #first get solrindex ids and key fields
    try:#make a dictionary of filepaths from solr index
        indexpaths=solrcursor.cursor(thiscore)
    except Exception as e:
        print('Failed to retrieve solr index')
        print (str(e))
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
            #print (file.filepath,relpath)

	#INDEX CHECK: METHOD ONE : IF RELATIVE PATHS STORED MATCH
            if relpath in indexpaths:  #if the path in database in the solr index
                solrdata=indexpaths[relpath]
                #print ('PATH :'+file.filepath+' indexed successfully', 'Solr \'id\': '+solrdata['id'])
                file.indexedSuccess=True
                file.solrid=solrdata['id']
                file.save()
                counter+=1
        #INDEX CHECK: METHOD TWO: CHECK IF FILE STORED IN SOLR INDEX UNDER CONTENTS HASH                
            else:
                #print('trying hash method')
                #is there a stored hash, if not get one
                if not hash:
                    hash=hexfile(file.filepath)
                    file.hash_contents=hash
                    file.save()
                #now lookup hash in solr index
                solrresult=solr.hashlookup(hash,thiscore)
                #print(solrresult)
                if len(solrresult)>0:
                    #if some files, take the first one
                    solrdata=solrresult[0]
                    #print('solrdata:',solrdata)
                    file.indexedSuccess=True
                    file.solrid=solrdata['id']
                    file.save()
                    counter+=1
                    #print ('PATH :'+file.filepath+' indexed successfully (HASHMATCH)', 'Solr \'id\': '+solrdata['id'])
                #NO MATCHES< RETURN FAILURE
                else:
                    print (file.filepath,'.. not found in Solr index')
                    file.indexedSuccess=False
                    file.solrid='' #wipe any stored solr id; DEBUG: this wipes also oldsolr ids scheduled for delete
                    file.save()
                    skipped+=1
        return counter,skipped,failed


def indexdocs(collection,mycore,forceretry=False): #index into Solr documents not already indexed
    #need to check if mycore and collection are valid objects
    if isinstance(mycore,solr.SolrCore) == False or isinstance(collection,Collection) == False:
        print('indexdocs() parameters invalid')
        return 0,0,0
    if True:
        counter=0
        skipped=0
        failed=0
        #print(collection)
        filelist=File.objects.filter(collection=collection)
        #main loop
        for file in filelist:
            if file.indexedSuccess:
                #skip this file, it's already indexed
                #print('Already indexed')
                skipped+=1
            elif file.indexedTry==True and forceretry==False:
                #skip this file, tried before and not forceing retry
                #print('Previous failed index attempt, not forcing retry:',file.filepath)
                skipped+=1
            else: #do try to index this file
                print('Attempting index of',file.filepath)
                #print('trying ...',file.filepath)
                #if was previously indexed, store old solr ID and then delete if new index successful
                oldsolrid=file.solrid
                #getfile hash if not already done
                if not file.hash_contents:
                    file.hash_contents=hexfile(file.filepath)
                    file.save()
                #now try the extract
                try:
                    result=indexSolr.extract(file.filepath,file.hash_contents,mycore)
                except requests.exceptions.RequestException as e:
                    raise indexSolr.ExtractInterruption('Indexing interrupted after '+str(counter)+' files extracted, '+str(skipped)+' files skipped and '+str(failed)+' files failed.')               
                if result is True:
                    counter+=1
                    #print ('PATH :'+file.filepath+' indexed successfully')
                    file.solrid=file.hash_filename  #extract users hashfilename for an id , so add it
                    file.indexedSuccess=True
                    #now delete old solr doc 
                    if oldsolrid and oldsolrid!=file.solrid:
                        print('now delete old solr doc',oldsolrid)
                    file.save()
                else:
                    print ('PATH : '+file.filepath+' indexing failed')
                    failed+=1
                    file.indexedTry=True  #set flag to say we've treid
                    file.save()
        return counter,skipped,failed

#def scandocs(collection):
#    if True: 
#        counter=0
#        skipped=0
##        print(collection)
##        dict=hex(collection.path) #makes a dictionary keyed by hash of file contents
#        dict=filetable(collection.path) #make a dictionary of filespecs, keyed to path
##           >>>>>>>filespecs are a list [path]=[[path,filelen,shortName,fileExt,modTime]]
#        for path in dict:
#            if File.objects.filter(filepath = path).exists():
#                skipped+=1
#                file=File.objects.get(filepath = path)
#                print('Skipped/file already logged:',file.filename)
#                #reset index try to allow another attempt
#                file.indexedTry=False
#                file.save()
#                pass
#            else:
#                counter+=1
#                #print(lastm)
#                docpath=path
#                hash=hexfile(path) #GET THE HASH OF FULL CONTENTS
##                print(hash,docpath,lastmodified)
#                f=File(hash_contents=hash,filepath=docpath)
#                lastm=dict[path][4]
#                lastmod=datetime.datetime.fromtimestamp(lastm)
#                lastmodified=pytz.timezone("Europe/London").localize(lastmod, is_dst=True)
#                f.last_modified=lastmodified
#                f.collection=collection
#                f.filesize=dict[path][1]
#                f.filename=dict[path][2]
#                f.fileext=dict[path][3]
#                f.hash_filename=pathHash(docpath)
#                #print ('hash',f.hash_filename,'docpath',docpath)
#                f.save()
#
#    return counter,skipped
    
def pathHash(path):
    m=hashlib.md5()
    m.update(path.encode('utf-8'))  #encoding avoids unicode error for unicode paths
    return m.hexdigest()

