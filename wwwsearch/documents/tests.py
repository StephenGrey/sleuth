# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import hashlib,requests,datetime,os
from django.test import TestCase
import indexSolr as i
from models import File,Collection
from ownsearch.hashScan import HexFolderTable as hex
from ownsearch.hashScan import hashfile256 as hexfile
from ownsearch.hashScan import pathHash
import ownsearch.solrSoup as s
import solrcursor as curs
from ownsearch.hashScan import FileSpecTable as filetable
from django.utils import timezone
import pytz #support localising the timezone
from usersettings import userconfig as config
from datetime import datetime, date, time
import subprocess

def metaupdate():
    docstore=config['Models']['collectionbasepath'] #get base path of the docstore
    collection=Collection.objects.get(id=2)
    #print collection.core
    cores=s.getcores() #fetch dictionary of installed solr indexes (cores)
    mycore=cores[collection.core.coreID]
    filelist=File.objects.filter(collection=collection)
    for file in filelist:
        if file.indexUpdateMeta:
            #print file.filename, file.filepath,'ID:'+
            print()
            print('ID:'+file.solrid)
            #,'PATHHASH'+file.hash_filename
            print'Solr meta data needs update'
            results=s.getcontents(file.solrid,core=mycore)
            if len(results)>0:
                result=results[0]
                olddocsize=int(result['solrdocsize'])
                olddocpath=result['docpath']
                oldlastmraw=result['date']
                oldlastmparse=datetime.strptime(oldlastmraw, "%Y-%m-%dT%H:%M:%SZ")
                #convert the Z into UTC timezone
                oldlastmodified=pytz.timezone("Europe/London").localize(oldlastmparse, is_dst=True)
#                rawtext=result['rawtext']
                olddocname=result['docname']
                #print olddocsize,olddocpath,olddocname
                relpath=os.path.relpath(file.filepath,start=docstore) #extract the relative path from the docstore
                if olddocpath != relpath:
                    print('need to update filepath')
                    print('old',olddocpath,'new',relpath)
                if olddocsize != file.filesize:
                    print('need to update filesize')
                    print('old',olddocsize,'new',file.filesize)
                if oldlastmodified != file.last_modified:
                    newlastmodified=file.last_modified.strftime("%Y-%m-%dT%H:%M:%SZ")
                    print('need to update last_modified from '+oldlastmraw+' to '+newlastmodified)
            else:
                print ('file not found')
#            hashcontents=result['hashcontents']


def listmeta():
    collection=Collection.objects.get(id=2)
    filelist=File.objects.filter(collection=collection)
    for file in filelist:
        if not file.indexedSuccess:
            print file.filename, 'ID:'+file.solrid,'PATHHASH'+file.hash_filename
            print'Needs to be Indexed'
        if file.indexUpdateMeta:
            print file.filename, 'ID:'+file.solrid,'PATHHASH'+file.hash_filename
            print'Solr meta data needs update'

def testchanges():
    collection=Collection.objects.get(id=2)
    change=changes(collection)
    updates(change,collection)
    return

def updates(change,collection):
    filelist=File.objects.filter(collection=collection)
    newfiles=change['newfiles']
    deletedfiles=change['deletedfiles']
    movedfiles=change['movedfiles']
    unchanged=change['unchanged']
    changedfiles=change['changedfiles']

    #UPDATE DATABASE WITH NEW FILES    
    if newfiles:
        print(len(newfiles),' new files')
        for path in newfiles:
            if os.path.exists(path)==True: #check file exists
                # Get file specs
                filename=os.path.basename(path)
                shortName, fileExt = os.path.splitext(filename)
                filelen=os.path.getsize(path) #get file length
                modTime = os.path.getmtime(path) #last modified time
                lastmod=datetime.datetime.fromtimestamp(modTime)
                lastmodified=pytz.timezone("Europe/London").localize(lastmod, is_dst=True)
                hash=hexfile(path) #GET THE HASH OF FULL CONTENTS
                pathhash=pathHash(path) #get the HASH OF PATH
                print path,filename,shortName,fileExt,filelen,lastmodified,hash

                #now create new entry in File database
                f=File(hash_contents=hash,filepath=path)
                f.last_modified=lastmodified
                f.collection=collection
                f.filesize=filelen
                f.filename=filename
                f.fileext=fileExt
                f.hash_filename=pathHash(path)
                f.indexedSuccess=False #NEEDS TO BE INDEXED IN SOLR
                f.save()
            else:
                print('ERROR: ',path,' does not exist')
    if movedfiles:
        print(len(movedfiles),' to move')
        for newpath,oldpath in movedfiles:
            print newpath,oldpath
            file=filelist.get(filepath=oldpath)
            #print matchfiles
            #update correctfilepath
            file.filepath=newpath
            file.hash_filename=pathHash(newpath)
            #if the file has been already indexed, flag to correct solr index meta
            if file.indexedSuccess:
                file.indexUpdateMeta=True  #flag to correct solrindex
                print('update meta')
            file.save()  
    return
    
def changes(collection):
    filedict=filetable(collection.path) #get files and specs inside a folder (and subfolders)
    filelist=File.objects.filter(collection=collection)
    unchanged,changedfiles,missingfiles,newfileshash,movedfiles,newfiles,deletedfiles=[],[],{},{},[],[],[]

    #compare with stored version
    for file in filelist:
        path=file.filepath
        lastm=file.last_modified
        hash=file.hash_contents
        size=file.filesize

        latest_file=filedict.pop(path, None)
        if latest_file:  #if stored path exists in current folder
                latest_lastm=latest_file[4]
                latest_lastmod=datetime.datetime.fromtimestamp(latest_lastm)
                latest_lastmodified=pytz.timezone("Europe/London").localize(latest_lastmod, is_dst=True)
                latestfilesize=latest_file[1]
                if lastm==latest_lastmodified and latestfilesize==size:
                    #print(path+' hasnt changed')
                    unchanged.append(path)
                else:
                    #print(path+' still there but has changed')
                    changedfiles.append(path)
                #print(path,lastm-latest_lastmodified)
                #filename=filedict[path][2]
                #fileext=filedict[path][3]
        else: #file has been deleted or moved
            #print(path+' is missing')
            missingfiles[path]=hash

    #files left in file dictionary
    for newpath in filedict:
        #print (newpath+' is new')
        newhash=hexfile(newpath)
        #print(newhash)
        newfileshash[newhash]=newpath

    #now work out which of new files are moved
    for missingfilepath in missingfiles:
        missinghash=missingfiles[missingfilepath]
        newpath=newfileshash.pop(missinghash, None)
        if newpath:
            #print(os.path.basename(missingfilepath)+' has moved to '+os.path.dirname(newpath))
            movedfiles.append([newpath,missingfilepath])
        else: #remaining files are deleted
            deletedfiles.append(missingfilepath)
  
  #remaining files in newfilehash are new 
    for newhash in newfileshash:
        newpath=newfileshash[newhash]
        newfiles.append(newpath)
    
    print('NEWFILES>>>>>',newfiles)
    print('DELETEDFILES>>>>>>>',deletedfiles)
    print('MOVED>>>>:',movedfiles)
    #print('NOCHANGE>>>',unchanged)
    print('CHANGEDFILES>>>>>>',changedfiles)
    return {'newfiles':newfiles,'deletedfiles':deletedfiles,'movedfiles':movedfiles,'unchanged':unchanged,'changedfiles':changedfiles}
  
def checksolrcursor():
    mycore=s.SolrCore('docscan1')
    res=curs.cursor(mycore)
    return res

def checksolrlists(mycore):
    cursormark='*' 
    args=mycore.cursorargs+'&cursorMark='+cursormark
    res=curs.getSolrResponse('*',args,mycore)
    blocklist,resultsnumber=curs.listresults(res,mycore)
    result=res.response.result
    document={}
    for doc in result:
        for arr in doc:
            document[arr.attrs['name']]=arr.text
    return document

def listhexes():
    thiscollection=Collection.objects.all()[0]
    files=File.objects.filter(collection=thiscollection)
    for file in files:
        print (file.id,file.filepath)
        hex=hexfile(file.filepath)
        #print (result)
        result=s.hashlookup(hex)
        if len(result)>0:
           print(result[0]['id'])

        
#        print(file.filepath.encode('ascii','ignore')
#    h=i.pathHash(file.filepath)
#        m=hashlib.md5()
#        m.update(file.filepath.encode('utf-8'))  #cope with unicode filepaths
#        hex = m.hexdigest()
#        print (hex)

def extract(id):
    path=files[id].filepath
    print(path)
    result=i.extract(path)
    print(result)

# Create your tests here.

def pathhash(path):
    print(path)
    m=hashlib.md5()
    print(m)
    m.update(path.encode('utf-8'))  #cope with unicode filepaths
    return m.hexdigest()

def hexexists(hex,solrurl):
    url=solrulr+u'/select?fl=id,tika_metadata_resourcename&q=extract_id:'+hex
    res=requests.get(url)
    return res

def post(path,solrurl):
    url=solrurl+u'/update/extract?commit=true'
    simplefilename=path.encode('ascii','ignore')
    with open(path,'rb') as f:
            file = {'myfile': (simplefilename,f)}
            res=requests.post(url, files=file)
    return res

def testextract(path="somefile",coreID="3"):
    try:
        docstore=config['Models']['collectionbasepath'] #get base path of the docstore
        cores=s.getcores() #fetch dictionary of installed solr indexes (cores)
        mycore=cores[coreID]
        i.ping(mycore) #checks the connecton is alive
        contentsHash=hexfile(path)
        #print mycore.name,mycore.url
        #result=i.extract(path,contentsHash,mycore,test=False)
        result=trysub(path,mycore)
        return result
    except requests.exceptions.RequestException as e:
        print ('caught connection error')

def trysub(path,mycore):
    extractpath=config['Extract']['extractpath'] #get location of Extract java JAR
    solrurl=mycore.url
    target=path
    #extract via ICIJ extract
    args=["java","-jar", extractpath, "spew","-o", "solr", "-s"]
    args.append(solrurl)
    args.append(target)
    result=subprocess.call(args)
    print result
    #commit the results
    print ('commmitting ..')
    args=["java","-jar",extractpath,"commit","-s"]
    args.append(solrurl)
    result=subprocess.call(args)
    print result
    return


def failedscans():
   d=File.objects.filter(indexedTry=True)
   for f in d:
       print(f.collection, f.filename, f.filepath, f.filesize)
       print ("UpdateMeta: "+str(f.indexUpdateMeta), "Indexed Success: "+str(f.indexedSuccess), "Indexed Try :"+str(f.indexedTry), f.last_modified, f.solrid)
