# -*- coding: utf-8 -*-
from __future__ import unicode_literals, print_function
from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.utils import timezone
import pytz #support localising the timezone
from models import Collection,File
from ownsearch.hashScan import HexFolderTable as hex
import datetime, hashlib, os, logging
import indexSolr
import solrcursor
from django.contrib.admin.views.decorators import staff_member_required
log = logging.getLogger('ownsearch')
from usersettings import userconfig as config

@staff_member_required()
def index(request):
    latest_collection_list = Collection.objects.all()
    return render(request, 'documents/scancollection.html',{'latest_collection_list': latest_collection_list})

def listfiles(request):
    if request.method == 'POST' and 'list' in request.POST and 'choice' in request.POST:
        try:
            selected_collection=int(request.POST[u'choice'])
            thiscollection=Collection.objects.get(id=selected_collection)
            collectionpath=thiscollection.path
            filelist=File.objects.filter(collection=thiscollection)
        except:
            return HttpResponse( "Error...please go back")
#SCAN DOCUMENTS IN A COLLECTION
    elif request.method == 'POST' and 'scan' in request.POST and 'choice' in request.POST:
        selected_collection=int(request.POST[u'choice'])
        thiscollection=Collection.objects.get(id=selected_collection)
        collectionpath=thiscollection.path
        #>> DO THE SCAN ON THIS COLLECTION
        scancount,skipcount=scandocs(thiscollection)
        if scancount>0 or skipcount>0:
             return HttpResponse (" Scanned "+str(scancount)+" docs and skipped "+str(skipcount)+ " docs.")
        else:
             return HttpResponse (" Scan Failed!")
#INDEX DOCUMENTS IN COLLECTION IN SOLR
    elif request.method == 'POST' and 'index' in request.POST and 'choice' in request.POST:
        print('try to index in Solr')
        selected_collection=int(request.POST[u'choice'])
        thiscollection=Collection.objects.get(id=selected_collection)
        icount,iskipped,ifailed=indexdocs(thiscollection)
        return HttpResponse ("Indexing.. indexed: "+str(icount)+"  skipped:"+str(iskipped)+"   failed:"+str(ifailed))
#CURSOR SEARCH OF SOLR INDEX
    elif request.method == 'POST' and 'solrcursor' in request.POST and 'choice' in request.POST:
        print('try cursor scan of Solr Index')
        selected_collection=int(request.POST[u'choice'])
        thiscollection=Collection.objects.get(id=selected_collection)
        match,skipped,failed=indexcheck(thiscollection)
        return HttpResponse ("Checking solr index.. files indexed: "+str(match)+"  files not found:"+str(skipped)+"   errors:"+str(failed))
    else:
        return redirect('index')
    return render(request, 'documents/listdocs.html',{'results':filelist,'collection':collectionpath })


#checking for what files in existing solrindex
def indexcheck(collection):
    #get the basefilepath
    docstore=config['Models']['collectionbasepath'] #get base path of the docstore
    #first get solrindex ids and key fields
    try:
        indexpaths=solrcursor.cursor()
        #print(indexpaths)
    except Exception as e:
        print('failed to retreieve solr index')
        print (str(e))
        return 'Failed to get index'
    #now compare file list with solrindex
    if True:
        counter=0
        skipped=0
        failed=0
        resultlist=[]
        #print(collection)
        filelist=File.objects.filter(collection=collection)
        #main loop
        for file in filelist:
            relpath=os.path.relpath(file.filepath,start=docstore) #extract a relative path from the docstore
            #print (file.filepath,relpath)
            if relpath in indexpaths:
                solrdata=indexpaths[relpath]
                #print('Solr data:',solrdata)
                #print ('PATH :'+file.filepath+' indexed successfully', 'Solr \'id\': '+solrdata['id'])
                file.indexedSuccess=True
                file.solrid=solrdata['id']
                file.save()
                counter+=1
                resultlist.append()
            else:
                #print (file.filepath,'.. not indexed')
                file.indexedSuccess=False
                file.save()
                skipped+=1
        return counter,skipped,failed


def indexdocs(collection,forceretry=False): #index into Solr documents not already indexed
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
                skipped+=1
            elif file.indexedTry==True and forceretry==False:
                #skip this file, tried before and not forceing retry
                skipped+=1
            else: #do try this file
                result=indexSolr.extract(file.filepath)
                if result is True:
                    counter+=1
                    #print ('PATH :'+file.filepath+' indexed successfully')
                    file.indexedSuccess=True
                    file.save()
                else:
                    #print ('PATH : '+file.filepath+' indexing failed')
                    failed+=1
                    file.indexedTry=True  #set flag to say we've treid
                    file.save()
        return counter,skipped,failed

def scandocs(collection):
    if True: 
        counter=0
        skipped=0
        #print(collection)
        dict=hex(collection.path)
        for hash in dict:
            if File.objects.filter(hash_contents = hash).exists():
                skipped+=1
                file=File.objects.get(hash_contents = hash)
                #lastm=dict[hash][0][4]
                #lastmod=datetime.datetime.fromtimestamp(lastm)
                #print(dict[hash][0][2],lastm,lastmod)
                #lastmodified=pytz.timezone("Europe/London").localize(lastmod,is_dst=True)
                #print('skipped:',file.filename)
                pass
            else:
                counter+=1
                docpath=dict[hash][0][0]
                lastm=dict[hash][0][4]
                filesize=dict[hash][0][1]
                filename=dict[hash][0][2]
                fileext=dict[hash][0][3]
                #print(lastm)
                lastmod=datetime.datetime.fromtimestamp(lastm)
                lastmodified=pytz.timezone("Europe/London").localize(lastmod, is_dst=True)
                #print(hash,docpath,lastmodified)
                f=File(hash_contents=hash,filepath=docpath,last_modified=lastmodified)
                #hex returns this dict: hex:[[path, filesize, filename, ext, lastmodified]]
                f.collection=collection
                f.filesize=filesize
                f.filename=filename
                f.fileext=fileext
                f.hash_filename=pathHash(docpath)
                #print ('hash',f.hash_filename,'docpath',docpath)
                f.save()       
#    except UnicodeError as e:
#        log.error=str(e)
#        print ('Error in getting hash dictionary')
#        print (str(e))
#        counter=0
#        skipped=0
    return counter,skipped
    
def pathHash(path):
    m=hashlib.md5()
    m.update(path.encode('utf-8'))  #encoding avoids unicode error for unicode paths
    return m.hexdigest()

