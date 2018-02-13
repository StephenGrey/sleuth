# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import hashlib,requests,datetime,os
from django.test import TestCase
import indexSolr as i
from models import File,Collection,SolrCore
from ownsearch.hashScan import HexFolderTable as hex
from ownsearch.hashScan import hashfile256 as hexfile
from ownsearch.hashScan import pathHash
import ownsearch.solrSoup as s
import solrcursor as curs
from ownsearch.hashScan import FileSpecTable as filetable
from documents import views as v
from django.utils import timezone
import pytz #support localising the timezone
from usersettings import userconfig as config
from datetime import datetime, date, time
import subprocess
from subprocess import Popen, PIPE, STDOUT
from fnmatch import fnmatch
import updateSolr as u

docstore=config['Models']['collectionbasepath'] #get base path of the docstore

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
    res=requests.get(url)
    return res

def post(path,solrurl):
    url=solrurl+u'/update/extract?commit=true'
    simplefilename=path.encode('ascii','ignore')
    with open(path,'rb') as f:
            file = {'myfile': (simplefilename,f)}
            res=requests.post(url, files=file)
    return res


def failedscans(collection=''):
    failures=[]
    if collection:
        d=File.objects.filter(indexedTry=True,collection=collection)
    else:
        d=File.objects.filter(indexedTry=True)
    for f in d:
        print(f.collection, f.filename, f.filepath, f.filesize)
        print ("FileID: "+str(f.id)+"UpdateMeta: "+str(f.indexUpdateMeta), "Indexed Success: "+str(f.indexedSuccess), "Indexed Try :"+str(f.indexedTry), f.last_modified, f.solrid)
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
        print (collection.id, collection.path,collection.indexedFlag,collection.core)

def makecollection(path):
    sc=SolrCore.objects.get(id='2')
    c=Collection(path=path,indexedFlag=False,core=sc)
    c.save()
    return c
    
def listf(collectionID):
    listfiles=File.objects.filter(collection=collectionID)
    for file in listfiles:
        print('FIlename'+file.filename,'FileExt'+file.fileext,'Path:'+file.filepath,'SolrID:'+file.solrid,'Indexed?'+str(file.indexedSuccess),'IndexedTry'+str(file.indexedTry),'Contents:'+file.hash_contents,'Path:'+file.hash_filename)
        
def coll(ID):
    return Collection.objects.get(id=ID)
    
def collection2solrcore(collection):
    id=str(collection.core.id)
    mycore=s.getcores()[id]
    return mycore
    
def fields(obj):
    return obj._meta.get_fields()
    
def clearindexTry(collection,ext=''):
    if ext:
        listfiles=File.objects.filter(collection=collection,fileext=ext)
    else:
        listfiles=File.objects.filter(collection=collection)
    for file in listfiles:
       file.indexedTry=False
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
                    print ('id:'+id,'SOLR date:'+str(parsesolrdate),'DATABASE date:'+str(lastm),lastm-parsesolrdate)
                else:
                    print ('no date in solr', id)#print (solrdoc)
# id,tika_metadata_last_modified, last_modified, tika_metadata_resourcename, tika_metadata_date, date                    
def times(path):
    return os.path.getmtime(path)
    
def pingtest(mycore):
    try:
        mycore.ping()
    except s.SolrConnectionError as e:
        print e
        return e
        

def ICIJindex(collection,mycore): #indexdocs(collection,mycore,forceretry=False,useICIJ=False)
    counter,skipped,failed=v.indexdocs(collection,mycore,forceretry=True,useICIJ=True)
    return counter,skipped,failed



def tps():  #test sub process
    args=["java","-version"] #,"2>&1"]
#    args=[u'java', u'-jar', 'somepath', u'commit', u'-s', u'http://localhost:8983/solr/debugxx']
#    path=u'somefilen.docxXX'
#    args=[u'extract','spew','-o','solr','-s','http://localhost:8983/solr/coreexample',path] #1>&2']
#    args=[u'extract','commit',u'-s', u'http://localhost:8983/solr/corexample']
#    args=['ls','-lh']
    result=Popen(args, stderr=PIPE,shell=False,stdout=PIPE)
    print vars(result)
    print ('STDOUT:',result.stdout.read())
    print ('STDERR:')
    while True:
        line = result.stderr.readline()
        if line != '':
    #the real code does filtering here
            print "test:", line.rstrip()
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
           print(file.solrid,'Date: '+str(res[0].get('date','no date')))
       #'Indexed?'+str(file.indexedSuccess),'IndexedTry'+str(file.indexedTry),'Contents:'+file.hash_contents,'Path:'+file.hash_filename)



