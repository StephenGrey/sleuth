# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from __future__ import print_function
from __future__ import absolute_import
import hashlib,datetime,os
from . import indexSolr as i
from .models import File,Collection,Index
from ownsearch.hashScan import HexFolderTable as hex
from ownsearch.hashScan import hashfile256 as hexfile
from ownsearch.hashScan import pathHash
import ownsearch.solrJson as s
from . import solrcursor as curs
from ownsearch.hashScan import FileSpecTable as filetable
#from documents import views as v
from django.utils import timezone
import pytz #support localising the timezone
from configs import  config
from datetime import datetime, date, time
import subprocess
from subprocess import Popen, PIPE, STDOUT
from fnmatch import fnmatch
from . import updateSolr as u
from django.db.models import Count

docstore=config['Models']['collectionbasepath'] #get base path of the docstore


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
        print((file.id,file.filepath))
        hex=hexfile(file.filepath)
        #print (result)
        result=s.hashlookup(hex)
        if len(result)>0:
           print(result[0]['id'])
        
def extract(path,coreid):
    #path=files[id].filepath
    mycore=s.getcores()[coreid]
    print(path)
    contentsHash=hexfile(path)
    result=i.extract(path,contentsHash,mycore,test=False)
    print(result)

def rawextract():
    sp,statusOK=i.postSolr(args,path,mycore)
    return sp,statusOK
    
    
def pathhash(path):
    print(path)
    m=hashlib.md5()
    print(m)
    m.update(path.encode('utf-8'))  #cope with unicode filepaths
    return m.hexdigest()

def hexexists(hex,solrurl):
    url=solrulr+u'/select?fl=id,tika_metadata_resourcename&q=extract_id:'+hex
    ses=s.SolrSession()
    res=ses.get(url)
    return res

def post(path,solrurl):
    url=solrurl+u'/update/extract?commit=true'
    simplefilename=path.encode('ascii','ignore')
    ses=s.SolrSession()
    with open(path,'rb') as f:
            file = {'myfile': (simplefilename,f)}
            res=ses.post(url, files=file)
    return res


def failedscans(collection=''):
    failures=[]
    if collection:
        d=File.objects.filter(indexedTry=True,collection=collection)
    else:
        d=File.objects.filter(indexedTry=True)
    for f in d:
        print((f.collection, f.filename, f.filepath, f.filesize))
        print(("FileID: "+str(f.id)+"UpdateMeta: "+str(f.indexUpdateMeta), "Indexed Success: "+str(f.indexedSuccess), "Indexed Try :"+str(f.indexedTry), f.last_modified, f.solrid))
        failures.append(f)
    return failures

def copyfiles(files,destination): #take a list of file objects and copy actual files to folder
    assert os.path.exists(destination)
    assert os.path.isdir(destination)
    try:
        for f in files:
            existpath=f.filepath
            os.system('cp \"'+existpath+'\" \"'+destination+'\"/')
    except Exception as e:
        print (e)
        return False
    return True


def listc():
    for collection in Collection.objects.all():
        print((collection.id, collection.path,collection.indexedFlag,collection.core))

def makecollection(path):
    sc=SolrCore.objects.get(id='2')
    c=Collection(path=path,indexedFlag=False,core=sc)
    c.save()
    return c
    
def listf(collectionID):
    listfiles=File.objects.filter(collection=collectionID)
    for file in listfiles:
        print(('FIlename'+file.filename,'FileExt'+file.fileext,'Path:'+file.filepath,'SolrID:'+file.solrid,'Indexed?'+str(file.indexedSuccess),'IndexedTry'+str(file.indexedTry),'Contents:'+file.hash_contents,'Path:'+file.hash_filename))
        
def coll(ID):
    return Collection.objects.get(id=ID)
    
def collection2solrcore(collection):
    id=str(collection.core.id)
    mycore=s.getcores()[id]
    return mycore
    
def fields(obj):
    return obj._meta.get_fields()
    
def clear_indexTry(collection,ext=''):
    """reset flag that shows extracting already attempted"""
    if ext:
        listfiles=File.objects.filter(collection=collection,fileext=ext)
    else:
        listfiles=File.objects.filter(collection=collection)
    for file in listfiles:
       file.indexedTry=False
       file.save()

def clear_indexedSuccess(collection,ext=''):
    """reset flag to show successful extraction"""
    if ext:
        listfiles=File.objects.filter(collection=collection,fileext=ext)
    else:
        listfiles=File.objects.filter(collection=collection)
    for file in listfiles:
       file.indexedSuccess=False
       file.save()



def ckdates(collection):
    count=0
    mycore=collection2solrcore(collection)
    listfiles=File.objects.filter(collection=collection) #,indexUpdateMeta=True)
    for file in listfiles:
        count+=1
        if count>20:  #arbitrary limit for testing
            break
        lastm=file.last_modified
        id=file.solrid
        #print (file.filename,lastm, id)
        if id:
            solrresult=s.getcontents(id,core=mycore)
            if solrresult:
                solrdoc=solrresult[0]
                solrdoc.pop('rawtext')
                solrdate=solrdoc['date']
                if solrdate:
                    parse1=datetime.strptime(solrdate, "%Y-%m-%dT%H:%M:%SZ")
                    parsesolrdate=pytz.timezone("Europe/London").localize(parse1, is_dst=True)
                    print(('id:'+id,'SOLR date:'+str(parsesolrdate),'DATABASE date:'+str(lastm),lastm-parsesolrdate))
                else:
                    print(('no date in solr', id))#print (solrdoc)
# id,tika_metadata_last_modified, last_modified, tika_metadata_resourcename, tika_metadata_date, date                    
def times(path):
    return os.path.getmtime(path)
            

def tps():  #test sub process
    args=["java","-version"] #,"2>&1"]
    result=Popen(args, stderr=PIPE,shell=False,stdout=PIPE)
    print(vars(result))
    print(('STDOUT:',result.stdout.read()))
    print ('STDERR:')
    while True:
        line = result.stderr.readline()
        if line != '':
    #the real code does filtering here
            print("test:", line.rstrip())
        else:
            break
    if result==0:
        print ('Successful')
    return result
    
def listmeta(collection):
    listfiles=File.objects.filter(collection=collection)
    core=collection2solrcore(collection)
    for file in listfiles:
#         print('FIlename'+file.filename,'FileExt'+file.fileext,'Path:'+file.filepath,'SolrID:'+
       res=s.getmeta(file.solrid,core)
       if res:
           print((file.solrid,'Date: '+str(res[0].get('date','no date'))))
       #'Indexed?'+str(file.indexedSuccess),'IndexedTry'+str(file.indexedTry),'Contents:'+file.hash_contents,'Path:'+file.hash_filename)

def addparenthashes(mycore,maxcount=10,test=False):
    upd=u.AddParentHash(mycore,maxcount=maxcount,test_run=test)
    

def list_fails(collection):
    listfiles=File.objects.filter(collection=collection,indexedSuccess=False)
    
    ext_totals=listfiles.values('fileext').annotate(total=Count('fileext')).order_by('-total')
    
    for sums in ext_totals:
        ext=sums['fileext']
        total=sums['total']
        
        print(f'{ext} {total}')
    

