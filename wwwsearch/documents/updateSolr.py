# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import requests, os, logging
import json, collections
import ownsearch.solrJson as s
import documents.solrcursor as sc
from datetime import datetime, date, time
from models import File,Collection
from ownsearch.hashScan import HexFolderTable as hex
from ownsearch.hashScan import hashfile256 as hexfile
from ownsearch.hashScan import pathHash
from ownsearch.hashScan import FileSpecTable as filetable
from django.utils import timezone
import pytz #support localising the timezone
log = logging.getLogger('ownsearch.updateSolr')
from usersettings import userconfig as config

docstore=config['Models']['collectionbasepath'] #get base path of the docstore

#SCAN AND MAKE UPDATES TO BOTH LOCAL FILE META DATABASE AND SOLR INDEX
def scandocs(collection,deletes=True):
    change=changes(collection)  #get dictionary of changes to file collection (compare disk folder to meta database)
    
    #make any changes to local file database
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
        doc=res[0]
        for field,value in changes:
            #print('Change',field,value)
            
            newvalue=doc.__dict__.get(field,doc.data.get(field,''))
            if newvalue:
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
    a['extract_id']=solrid 
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
    a['delete']={'extract_id':solrid}
    data=json.dumps(a)
    return data
"""
 "delete": { "id":"ID" },
"""

def post_jsonupdate(data,mycore,timeout=10):
    updateurl=mycore.url+'/update/json?commit=true'
    url=updateurl
    headers={'Content-type': 'application/json'}
    try:
        res=requests.post(url, data=data, headers=headers,timeout=timeout)
        jres=res.json()
        status=jres['responseHeader']['status']
        if status==0:
            statusOK = True
        else:
            statusOK = False
        return res.json(), statusOK
    except Exception as e:
        print ('Exception: ',str(e))
        return '',False

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
        if file.indexUpdateMeta and file.solrid: #do action if indexUpdateMeta flag is true; and there is a stored solrID
            #print (file.filename, file.filepath)
            #print()
            print('ID:'+file.solrid)
            print(file.__dict__)
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
                    json2post=makejson(solrdoc.id,changes,mycore)
                    log.debug('{}'.format(json2post)) 
#                    response,updatestatus=post_jsonupdate(json2post,mycore)
                    if checkupdate(solrdoc.id,changes,mycore):
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

#take a Solr Result object,compare with file database, return change list [(standardisedfield,newvalue),..]
def parsechanges(solrresult,file,mycore): 
    #print(solrresult)
    solrdocsize=solrresult.data['solrdocsize']
    olddocsize=int(solrdocsize) if solrdocsize else 0
    olddocpath=solrresult.data['docpath']
    olddate=solrresult.date 
    if olddate:
        try:
            oldlastmodified=s.parseISO(olddate)#convert raw time text from solr into time object
        except s.iso8601.ParseError as e:
            log.debug('date stored in solr cannot be parsed')
            oldlastmodified=''
        except Exception as e:
            log.debug('Error with date stored in solr {}, {}'.format(olddate, e))
            oldlastmodified=''
    else:
        oldlastmodified='' 
    olddocname=solrresult.docname
#    print olddocsize,olddocpath,olddocname, oldlastmodified
    #compare solr data with new metadata & make list of changes
    changes=[] #changes=[('tika_metadata_content_length',100099)]
    relpath=os.path.relpath(file.filepath,start=docstore) #extract the relative path from the docstore
    if olddocpath != relpath:
        log.info('need to update filepath from old: {} to new: {}'.format(olddocpath,relpath))
        changes.append(('docpath',relpath))
    if olddocsize != file.filesize:
        log.info('need to update filesize from old {} to new {}'.format(olddocsize,file.filesize))
        changes.append(('solrdocsize',file.filesize))
    newlastmodified=s.timestringGMT(file.last_modified)
#    file.last_modified.strftime("%Y-%m-%dT%H:%M:%SZ")
    if olddate !=newlastmodified:
        log.info('need to update last_modified from \"{}\"  to \"{}\"'.format(oldlastmodified, newlastmodified))
        changes.append(('date',newlastmodified))
    newfilename=file.filename
    if olddocname != newfilename:
        log.info('need to update filename from {} to {}'.format(olddocname,newfilename))
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
        log.debug('{} changed file(s) '.format(len(changedfiles)))
        for filepath in changedfiles:
            log.debug('{}'.format(filepath))
            file=filelist.get(filepath=filepath)
            updatesuccess=updatefiledata(file,filepath)

            #check if contents have changed and solr index needs changing
            oldhash=file.hash_contents
            newhash=hexfile(filepath)
            if newhash!=hexfile:
                #contents change, flag for index
                file.indexedSuccess=False
                file.hash_contents=newhash
#                file.indexUpdateMeta=True  #flag to correct solrindex
            #the solrid field is not cleared = the index process can check if it exists and delete the old doc
            #else-if the file has been already indexed, flag to correct solr index meta
            elif file.indexedSuccess==True:
                file.indexUpdateMeta=True  #flag to correct solrindex
            #else no change in contents - no need to flag for index
            file.save()
    return

#calculate all the metadata and update database; default don't make hash
def updatefiledata(file,path,makehash=False):
    try:
        file.filepath=path #
        file.hash_filename=pathHash(path) #get the HASH OF PATH
        filename=os.path.basename(path)
        file.filename=filename
        shortName, fileExt = os.path.splitext(filename)
        file.fileext=fileExt    
        modTime = os.path.getmtime(path) #last modified time
        file.last_modified=s.timestamp2aware(modTime)
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
                latest_lastmodified=s.timestamp2aware(latest_file[4]) #gets last modified info as stamp, makes GMT time object
                latestfilesize=latest_file[1]
                if lastm==latest_lastmodified and latestfilesize==size:
                    #print(path+' hasnt changed')
                    unchanged.append(path)
                else:
                    #print(path+' still there but has changed')
                    changedfiles.append(path)
                    log.debug('Changed file: \nStored date: {} New date {}\n Stored filesize: {} New filesize: {}'.format(lastm,latest_lastmodified,size,latestfilesize))
                #print(path,lastm-latest_lastmodified)
        else: #file has been deleted or moved
            #print(path+' is missing')
            missingfiles[path]=hash

    #make contents hash of files remaining of list on disk(found on disk, not in database)
    for newpath in filedict:
        #print (newpath+' is new')
        newhash=hexfile(newpath)
        #print(newhash)
        newfileshash[newhash]=newpath

    #now work out which new files have been moved
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
    
    log.info('NEWFILES>>>>>{}'.format(newfiles))
    log.info('DELETEDFILES>>>>>>>{}'.format(deletedfiles))
    log.info('MOVED>>>>:{}'.format(movedfiles))
    #print('NOCHANGE>>>',unchanged)
    log.info('CHANGEDFILES>>>>>>{}'.format(changedfiles))
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

#POST EXTRACTION PROCESSING

#ADD ADDITIONAL METADATA TO SOLR RECORDS 
#NB the following is imported elsewhere
def updatetags(solrid,mycore,value=['test','anothertest'],standardfield='usertags1field',newfield=False):
    #check the parameters
    field=mycore.__dict__.get(standardfield,standardfield) #decode the standard field, or use the name'as is'.
    if newfield==False:
        try:
            assert s.fieldexists(field,mycore) #check the field exists in the index
        except AssertionError as e:
            log.info('Field \"{}\" does not exist in index'.format(field))
            return False
    #make the json
    doc=collections.OrderedDict()  #keeps the JSON file in a nice order
    doc['extract_id']=solrid
    doc[field]={"set":value}
    jsondoc=json.dumps([doc])
    log.debug('Json to post: {}'.format(jsondoc))

    #post the update
    result,status=post_jsonupdate(jsondoc,mycore,timeout=10)
    
    #check the result
    log.info('Solr doc update: result: {}, status: {}'.format(result,status))
    
    return status

#ADD A SOURCE RETROSPECTIVELY
def updatefield(mycore,newvalue):
    counter=0
    maxcount=30000
    res=False
    args='&fl=extract_id,database_originalID, sb_filename'
    while True:
        res = sc.cursornext(mycore,searchterm='*',highlights=False,lastresult=res)
        if res == False:
            break
        #ESCAPE ROUTES ;
        if not res.results:
            break
        counter+=1
        if counter>maxcount:
            break
#        print(res.results)

        for doc in res.results:
            solrid=doc.id
#            print(solrid)
            #EXAMPLE FILTER = TEST IF ANY DATA IN FIELD - DATABASE_ORIGINALID _ AND UPDATE OTHERS
            searchterm=r'extract_id:"'+solrid+r'"'
            jres=s.getJSolrResponse(searchterm,args,core=mycore)
            results=s.SolrResult(jres,mycore).results[0]
            data_id=results.data.get('database_originalID','NONE')
            
            if data_id=='NONE':
#            	data_id=='' or data_id=='NONE':
                try: 
                    #print(solrid)
                    #print (results.__dict__)
                    deleteres=delete(solrid,mycore)
                    if deleteres:
                        print('deleted {}'.format(solrid))
#                    result=updatetags(solrid,mycore,value=newvalue,standardfield='sourcefield',newfield=False)
#                    if result == False:
#                        print('Update failed for solrID: {}'.format(solrid))
                except Exception as e:
                    print(e)                	
                except Exception as e:
                    print(e)
                    print('no solr doc found for post ',post.id,post.name)        
            else:
                #print('skipped solrid: {} dataID: {}'.format(solrid,data_id))
                pass


