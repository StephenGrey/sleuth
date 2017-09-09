# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import hashlib,requests
from django.test import TestCase
import indexSolr as i

from models import File,Collection
thiscollection=Collection.objects.all()[0]
files=File.objects.filter(collection=thiscollection)

for file in files:
    print (file.id,file.filepath)
    print(file.filepath.encode('ascii','ignore'))
#    h=i.pathHash(file.filepath)
    m=hashlib.md5()
    m.update(file.filepath.encode('utf-8'))  #cope with unicode filepaths
    hex = m.hexdigest()
    print (hex)

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

def post(path):
    url='http://localhost:8983/solr/docscan1/update/extract?commit=true'
    simplefilename=path.encode('ascii','ignore')
    with open(path,'rb') as f:
            file = {'myfile': (simplefilename,f)}
            res=requests.post(url, files=file)
    return res


#files = {'file': ('report.xls', open('report.xls', 'rb'), 'application/vnd.ms-excel', {'Expires': '0'})}

