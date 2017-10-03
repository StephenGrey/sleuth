# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import requests, os, logging
import json, collections
import ownsearch.solrSoup as s
from datetime import datetime, date, time
from models import File,Collection
from ownsearch.hashScan import HexFolderTable as hex
from ownsearch.hashScan import hashfile256 as hexfile
from ownsearch.hashScan import pathHash
from ownsearch.hashScan import FileSpecTable as filetable
from django.utils import timezone
import pytz #support localising the timezone
log = logging.getLogger('ownsearch')
from usersettings import userconfig as config

docstore=config['Models']['collectionbasepath'] #get base path of the docstore


def scandocs(collection,deletes=True):
    change=changes(collection)  #get dictionary of changes to file collection
    
    #make the changes to file database
    try:
        updates(change,collection) 
    except Exception as e:
        print ('failed to make updates to file database')
        print('Error: ',str(e))
        return
    #remove deleted files from the index
    #(only remove from database when successfully removed from solrindex, so if solr is down won't lose sync)
    if deletes and change['deletedfiles']:
        try:
            removedeleted(change['deletedfiles'],collection)
        except Exception as e:
            print('failed to remove deleted files from solr index') 
            print('Error: ',str(e))

    #alters meta in the the solr index (via an atomic update)
    try:
        metaupdate(collection) 
    except Exception as e:
        print ('failed to make update updates to solr metadata')
        print('Error: ',str(e),e)
        return
    listchanges=countchanges(change)
    return listchanges #newfiles,deleted,moved,unchanged,changedfiles


def test():
    cores=s.getcores() #fetch dictionary of installed solr indexes (cores)
    mycore=cores['1']
    print (mycore.name)
    id='68some ID jkljas'
    changes=[('tika_metadata_content_length',100099)]

    data=makejson(id,changes)
    response,updatestatus=post_jsonupdate(data,mycore)
    checkstatus=checkupdate(id,changes,mycore)
    return updatestatus,checkstatus

def removedeleted(deletefiles,collection):
    cores=s.getcores() #fetch dictionary of installed solr indexes (cores)
    mycore=cores[collection.core.coreID]
    filelist=File.objects.filter(collection=collection)
    for path in deletefiles:
        file=filelist.get(filepath=path)
        #first remove from solrindex
        response,status=delete(file.solrid,mycore)
        if status:
        #if no error then remove from file database
            file.delete()
            print('Deleted '+path)
    return

def checkupdate(id,changes,mycore):
    #check success
    print id
    status=True
    res,numbers=s.solrSearch('id:'+id,'',0,core=mycore)
    #print (changes,res)
    for field,value in changes:
        newvalue=res[0][field]
        #print newvalue,value
        if newvalue==value:
            print(field+'  successfully updated to '+str(value))
        else:
            print(field+' not updated; currentvalue: '+res[0][field])
            status=False
    return status

def update(id,changes,mycore):  #solrid, list of changes [(field,value),(field2,value)],core
    data=makejson(id,changes)
    response,status=post_jsonupdate(data,mycore)
    checkupdate(id,changes,mycore)
    return response,status

def makejson(solrid,changes):
    a=collections.OrderedDict()  #keeps the JSON file in a nice order
    a['id']=solrid 
    for field,value in changes:
        a[field]={"set":value}
    data=json.dumps([a])
    return data

def delete(solrid,mycore):
    data=deletejson(solrid)
    response,status=post_jsonupdate(data,mycore)
    return response,status

def deletejson(solrid):
    a=collections.OrderedDict()  #keeps the JSON file in a nice order
    a['delete']={'id':solrid}
    data=json.dumps(a)
    return data
"""
 "delete": { "id":"ID" },
"""

def post_jsonupdate(data,mycore):
    updateurl=mycore.url+'/update/json?commit=true'
    url=updateurl
    headers={'Content-type': 'application/json'}
    try:
        res=requests.post(url, data=data, headers=headers)
        jres=res.json()
        status=jres['responseHeader']['status']
        if status==0:
            statusOK = True
        else:
            statusOK = False
        return res.json(), statusOK
    except Exception as e:
        print ('Exception: ',str(e))
        statusOK=False
        return '',statusOK
        
#update the metadata in the  model database
def metaupdate(collection):
    #print ('testing collection:',collection,'from core',collection.core,'core ID',collection.core.coreDisplayName)
    cores=s.getcores() #fetch dictionary of installed solr indexes (cores)
    mycore=cores[collection.core.coreID]
    #main code
    filelist=File.objects.filter(collection=collection)
    for file in filelist: #loop through files in collection
        if file.indexUpdateMeta: #do action if indexUpdateMeta flag is true
            print (file.filename, file.filepath)
            print()
            print('ID:'+file.solrid)
            #,'PATHHASH'+file.hash_filename
            print'Solr meta data needs update'
            #get solr data on file - and then modify if changed
            results=s.getcontents(file.solrid,core=mycore)  #get current contents of solr doc
            if len(results)>0:
                solrdoc=results[0]   #results come as a list so just take the first one
                #print (result)
                #parse existing solr data
                changes=parsechanges(solrdoc,file,mycore) #returns list of tuples [(field,newvalue),]
                if changes:
                    #make changes to the solr index
                    json2post=makejson(solrdoc['id'],changes)
                    response,updatestatus=post_jsonupdate(json2post,mycore)
                    if checkupdate(solrdoc['id'],changes,mycore):
                        print('solr successfullyupdated')
                        file.indexUpdateMeta=False
                        file.save()
                    else:
                        print('solr changes not successful')
                else:
                    print('Nothing to update!')
                    file.indexUpdateMeta=False
                    file.save()
                #remove indexUpdateMeta flag
            else:
                print ('[metaupdate]file not found in solr index')
#            hashcontents=result['hashcontents']

#take a solr result,compare with filedatabae, return change list [(field,newvalue),..]
def parsechanges(solrresult,file,mycore): 
    #print(solrresult)
    solrdocsize=solrresult['solrdocsize']
    if solrdocsize:
        olddocsize=int(solrresult['solrdocsize'])
    else:
        olddocsize=0
    olddocpath=solrresult['docpath']
    oldlastmraw=solrresult['date']
    if oldlastmraw:
        oldlastmparse=datetime.strptime(oldlastmraw, "%Y-%m-%dT%H:%M:%SZ")
        #convert the Z into UTC timezone
        oldlastmodified=pytz.timezone("Europe/London").localize(oldlastmparse, is_dst=True)
    else:
        oldlastmodified=''
    olddocname=solrresult['docname']
    #print olddocsize,olddocpath,olddocname
    #compare solr data with new metadata & make list of changes
    changes=[] #changes=[('tika_metadata_content_length',100099)]
    relpath=os.path.relpath(file.filepath,start=docstore) #extract the relative path from the docstore
    if olddocpath != relpath:
        print('need to update filepath')
        print('from old: ',olddocpath,'to new:',relpath)
        changes.append((mycore.docpath,relpath))
    if olddocsize != file.filesize:
        print('need to update filesize')
        print('old',olddocsize,'new',file.filesize)
        changes.append((mycore.docsizefield,file.filesize))
    newlastmodified=file.last_modified.strftime("%Y-%m-%dT%H:%M:%SZ")
#debug - timezones not quite fixed here
    if oldlastmraw !=newlastmodified:
#    oldlastmodified != file.last_modified:
        print (oldlastmodified,file.last_modified)
        print (oldlastmodified-file.last_modified)
        print('need to update last_modified from '+oldlastmraw+' to '+newlastmodified)
        changes.append((mycore.datefield,newlastmodified))
    newfilename=file.filename+file.fileext
    if olddocname != newfilename:
        print('need to update filename from'+olddocname+' to '+newfilename)
    return changes


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


def updates(change,collection):
    filelist=File.objects.filter(collection=collection)
    newfiles=change['newfiles']
#    deletedfiles=change['deletedfiles']
    movedfiles=change['movedfiles']
#    unchanged=change['unchanged']
    changedfiles=change['changedfiles']

    #UPDATE DATABASE WITH NEW FILES    
    if newfiles:
        print(len(newfiles),' new files')
        for path in newfiles:
            if os.path.exists(path)==True: #check file exists
                #now create new entry in File database
                newfile=File(collection=collection)
                updatefiledata(newfile,path,makehash=True)
                newfile.indexedSuccess=False #NEEDS TO BE INDEXED IN SOLR
                newfile.save()
            else:
                print('ERROR: ',path,' does not exist')
    if movedfiles:
        print(len(movedfiles),' to move')
        for newpath,oldpath in movedfiles:
            print newpath,oldpath

            #get the old file and then update it
            file=filelist.get(filepath=oldpath)
            updatesuccess=updatefiledata(file,newpath) #check all metadata;except contentsHash
            #if the file has been already indexed, flag to correct solr index meta
            if file.indexedSuccess:
                file.indexUpdateMeta=True  #flag to correct solrindex
                print('update meta')
            file.save()
            
    if changedfiles:
        print(str(len(changedfiles))+' changed file(s)')
        for filepath in changedfiles:
            print(filepath)
            file=filelist.get(filepath=filepath)
            updatesuccess=updatefiledata(file,filepath)
            
            #check if contents have changed and solr index needs changing
            oldhash=file.hash_contents
            newhash=hexfile(filepath)
            if newhash!=hexfile:
                #contents change, flag for index
                file.indexedSuccess=False
                file.hash_contents=newhash
                #no change in contents - no need to flag for index
            #else if the file has been already indexed, flag to correct solr index meta
            elif file.indexedSuccess==True:
                file.indexUpdateMeta=True  #flag to correct solrindex
            file.save()
    return

#calculate all the metadata and update database; default don't make hash
def updatefiledata(file,path,makehash=False):
    try:
        file.filepath=path #get the HASH OF PATH
        file.hash_filename=pathHash(path)
        filename=os.path.basename(path)
        file.filename=filename
        shortName, fileExt = os.path.splitext(filename)
        file.fileext=fileExt    
        modTime = os.path.getmtime(path) #last modified time
        lastmod=datetime.fromtimestamp(modTime)
        file.last_modified=pytz.timezone("Europe/London").localize(lastmod, is_dst=True)
        if makehash:
            hash=hexfile(path) #GET THE HASH OF FULL CONTENTS
            file.hash_contents=hash
        file.filesize=os.path.getsize(path) #get file length
        file.save()
        return True
    except Exception as e:
        print ('Failed to update file database data for ',path)
        print ('Error in updatefiledata(): ',str(e))
        return False

def changes(collection):
    filedict=filetable(collection.path) #get files and specs inside a folder (and subfolders)
    filelist=File.objects.filter(collection=collection)
    unchanged,changedfiles,missingfiles,newfileshash,movedfiles,newfiles,deletedfiles=[],[],{},{},[],[],[]
    #loop through files in the database
    #print filedict,filelist
    for file in filelist:
        path=file.filepath
        lastm=file.last_modified
        hash=file.hash_contents
        size=file.filesize
        #grab and remove the filepath from filedict if in database
        latest_file=filedict.pop(path, None)
        if latest_file:  #if stored path exists in current folder
                latest_lastm=latest_file[4]
                latest_lastmod=datetime.fromtimestamp(latest_lastm)
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

    #make contents hash of left (found on disk, not in database)
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
  
def countchanges(changes):
    return [len(changes['newfiles']),len(changes['deletedfiles']),len(changes['movedfiles']),len(changes['unchanged']),len(changes['changedfiles'])]
