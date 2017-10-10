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
from django.utils import timezone
import pytz #support localising the timezone
from usersettings import userconfig as config
from datetime import datetime, date, time
import subprocess
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

def testextract(path="somefile",coreID="3"):
    try:
        docstore=config['Models']['collectionbasepath'] #get base path of the docstore
        cores=s.getcores() #fetch dictionary of installed solr indexes (cores)
        mycore=cores[coreID]
        i.ping(mycore) #checks the connection is alive
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


def failedscans(collection=''):
    if collection:
        d=File.objects.filter(indexedTry=True,collection=collection)
    else:
        d=File.objects.filter(indexedTry=True)
    for f in d:
        print(f.collection, f.filename, f.filepath, f.filesize)
        print ("UpdateMeta: "+str(f.indexUpdateMeta), "Indexed Success: "+str(f.indexedSuccess), "Indexed Try :"+str(f.indexedTry), f.last_modified, f.solrid)
       
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
        print('Path:'+file.filepath,'SolrID:'+file.solrid,'Indexed?'+str(file.indexedSuccess),'IndexedTry'+str(file.indexedTry),'Contents:'+file.hash_contents,'Path:'+file.hash_filename)
        
def collection2solrcore(collection):
    id=str(collection.core.id)
    mycore=s.getcores()[id]
    return mycore
    
def clearindexTry(collection,ext=''):
    if ext:
        listfiles=File.objects.filter(collection=collection,fileext=ext)
    else:
        listfiles=File.objects.filter(collection=collection)
    for file in listfiles:
       file.indexedTry=False
       file.save()
