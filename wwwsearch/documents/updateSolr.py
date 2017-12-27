# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import requests, os, logging
import json, collections
import ownsearch.solrJson as s
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

#SCAN AND MAKE UPDATES TO BOTH LOCAL FILE META DATABASE AND SOLR INDEX
def scandocs(collection,deletes=True):
    change=changes(collection)  #get dictionary of changes to file collection (compare disk folder to meta database)
    
    #make the changes to file database
    try:
        updates(change,collection) 
    except Exception as e:
        print ('failed to make updates to file database')
        print('Error: ',str(e))
        return [0,0,0,0,0]
    #remove deleted files from the index
    #(only remove from database when successfully removed from solrindex, so if solr is down won't lose sync)
    if deletes and change['deletedfiles']:
        try:
            removedeleted(change['deletedfiles'],collection)
        except Exception as e:
            print('failed to remove deleted files from solr index') 
            print('Error: ',str(e))

    #alters meta in the the solr index (via an atomic update)
#    try:
    if True:
        metaupdate(collection) 
#    except Exception as e:
#        print ('failed to make update updates to solr metadata')
#        print('Error: ',str(e),e)
#        return [0,0,0,0,0] 
    listchanges=countchanges(change)
    return listchanges #newfiles,deleted,moved,unchanged,changedfiles


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
    #print id
    status=True
    res=s.getmeta(id,mycore)
    #print (changes,res[0])
    if len(res)>0: #check there are solr docs returned
        for field,value in changes:
            #print('Change',field,value)
            if field in res[0]:
                newvalue=res[0][field] # mycore.fields[field]]
                if not isinstance(newvalue, basestring): #check for a list e.g date(not a string)
                    newvalue=newvalue[-1] if len(newvalue)>0 else '' #use the last in list
                #print (newvalue,value)
                if newvalue==value: 
                    print(field+' successfully updated to ',value)
                else:
                    print(field+' not updated; currentvalue: ',newvalue)
                    status=False
            else:
                print(field+' not found in solr result')
                status=False
    else:
        print('error finding solr result for id',id)
        status=False
    return status

def update(id,changes,mycore):  #solrid, list of changes [(standardfield,value),(field2,value)],core
    data=makejson(id,changes,mycore)
    response,status=post_jsonupdate(data,mycore)
    checkupdate(id,changes,mycore)
    return response,status

def makejson(solrid,changes,mycore):   #the changes use standard fields (e.g. 'date'); so parse into actual solr fields
    a=collections.OrderedDict()  #keeps the JSON file in a nice order
    a['id']=solrid 
    for field,value in changes:
        solrfield=mycore.__dict__.get(field,field) #if defined in core, replace with standard field, or leave unchanged
        a[solrfield]={"set":value}
    data=json.dumps([a])
    return data

#delete a file from solr index, return True if success
def delete(solrid,mycore):
    data=deletejson(solrid)
    response,status=post_jsonupdate(data,mycore)
    return response,status

#build json to delete a file from solr index
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

def post_jsondoc(data,mycore):
    updateurl=mycore.url+'/update/json/docs?commit=true'
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
            #print (file.filename, file.filepath)
            #print()
            print('ID:'+file.solrid)
            #,'PATHHASH'+file.hash_filename
            print'Solr meta data flagged for update'
            #get solr data on file - and then modify if changed
            results=s.getmeta(file.solrid,core=mycore)  #get current contents of solr doc, without full contents
            if len(results)>0:
                solrdoc=results[0] #results come as a list so just take the first one
                #parse existing solr data
                changes=parsechanges(solrdoc,file,mycore) #returns list of tuples [(field,newvalue),]
                if changes:
                    #make changes to the solr index
                    json2post=makejson(solrdoc['id'],changes,mycore)
                    response,updatestatus=post_jsonupdate(json2post,mycore)
                    if checkupdate(solrdoc['id'],changes,mycore):
                        print('solr successfully updated')
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

#take a solr result,compare with filedatabae, return change list [(standardisedfield,newvalue),..]
def parsechanges(solrresult,file,mycore): 
    #print(solrresult)
    solrdocsize=solrresult['solrdocsize'][-1] #solrdocsize is a list; take the last item
    olddocsize=int(solrdocsize) if solrdocsize else 0
    olddocpath=solrresult['docpath']
    olddate=solrresult['date'][-1] if len(solrresult['date'])>0 else ''#dates are multivalued;use the flast in list
    try:
        oldlastmodified=s.timefromSolr(olddate) #convert raw time text from solr into time object
    except Exception as e:
        print ('Error with date stored in solr',olddate, e)
        oldlastmodified='' 
    olddocname=solrresult['docname']
    #print olddocsize,olddocpath,olddocname

    #compare solr data with new metadata & make list of changes
    changes=[] #changes=[('tika_metadata_content_length',100099)]
    relpath=os.path.relpath(file.filepath,start=docstore) #extract the relative path from the docstore
    if olddocpath != relpath:
        print('need to update filepath')
        print('from old: ',olddocpath,'to new:',relpath)
        changes.append(('docpath',relpath))
    if olddocsize != file.filesize:
        print('need to update filesize')
        print('old',olddocsize,'new',file.filesize)
        changes.append(('solrdocsize',file.filesize))
    newlastmodified=s.timestringGMT(file.last_modified)
#    file.last_modified.strftime("%Y-%m-%dT%H:%M:%SZ")

#debug - timezones not quite fixed here
    if olddate !=newlastmodified:
#    oldlastmodified != file.last_modified:
        print(oldlastmodified,file.last_modified)
        print('need to update last_modified from '+str(oldlastmodified)+' to '+str(newlastmodified))
        changes.append(('date',newlastmodified))
    newfilename=file.filename
    if olddocname != newfilename:
        print('need to update filename from'+olddocname+' to '+newfilename)
        changes.append(('docname',newfilename))
    return changes



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
            #the solrid field is not cleared = the index process can check if it exists and delete it
            #else-if the file has been already indexed, flag to correct solr index meta
            elif file.indexedSuccess==True:
                file.indexUpdateMeta=True  #flag to correct solrindex
            #else no change in contents - no need to flag for index
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
        file.last_modified=pytz.timezone("Europe/London").localize(lastmod, is_dst=False)
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
    filedict=filetable(collection.path) #get specs of files in disk folder(and subfolders)
    filelist=File.objects.filter(collection=collection)
    unchanged,changedfiles,missingfiles,newfileshash,movedfiles,newfiles,deletedfiles=[],[],{},{},[],[],[]

    #loop through files in the database
    #print filedict,filelist
    for file in filelist:
        path=file.filepath
        lastm=file.last_modified
        hash=file.hash_contents
        size=file.filesize
        #grab and remove the filepath from filedict if already in database
        latest_file=filedict.pop(path, None)
        if latest_file:  #if stored path exists in current folder
                latest_lastm=latest_file[4] #gets last modified info
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

#TESTING
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

#def test(solrid,mycore=s.getcores()['3']):
##    cores=s.getcores() #fetch dictionary of installed solr indexes (cores)
##    mycore=cores['1']
#    print (mycore.name)
#    changes=[('solrdocsize',"100100")] #('date', '2017-09-15T18:08:24Z')] #
#    data=makejson(solrid,changes,mycore)
#    print(data)
#    response,updatestatus=post_jsonupdate(data,mycore)
#    print(response,updatestatus)
#    checkstatus=checkupdate(solrid,changes,mycore)
#    return updatestatus,checkstatus

