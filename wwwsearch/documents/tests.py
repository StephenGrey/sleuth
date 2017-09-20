# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import hashlib,requests
from django.test import TestCase
import indexSolr as i
from models import File,Collection
from ownsearch.hashScan import HexFolderTable as hex
from ownsearch.hashScan import hashfile256 as hexfile
import ownsearch.solrSoup as s
import solrcursor as curs

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

def hexexists(hex):
    url=u'http://localhost:8983/solr/docscan3/select?fl=id,tika_metadata_resourcename&q=extract_id:'+hex
    res=requests.get(url)
    return res

def post(path):
    url='http://localhost:8983/solr/docscan1/update/extract?commit=true'
    simplefilename=path.encode('ascii','ignore')
    with open(path,'rb') as f:
            file = {'myfile': (simplefilename,f)}
            res=requests.post(url, files=file)
    return res



