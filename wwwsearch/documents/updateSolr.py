# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import requests, os, logging
import json, collections
import ownsearch.solrSoup as s
log = logging.getLogger('ownsearch')
from usersettings import userconfig as config

def test():
    cores=s.getcores() #fetch dictionary of installed solr indexes (cores)
    mycore=cores['1']
    print (mycore.name)
    id='6805856b-cf0d-4859-844b-1c3cf775936d'
    changes=[('tika_metadata_content_length',100099)]

    data=makejson(id,changes)
    response,updatestatus=post_jsonupdate(data,mycore)
    checkstatus=checkupdate(id,changes,mycore)
    return updatestatus,checkstatus

def checkupdate(id,changes,mycore):
    #check success
    
    print id
    status=True
    res,numbers=s.solrSearch('id:'+id,'',0,core=mycore)
    for field,value in changes:
        newvalue=res[0][field]
        #print newvalue,value
        if str(newvalue)==str(value):
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

