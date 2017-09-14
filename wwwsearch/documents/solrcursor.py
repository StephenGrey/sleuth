# -*- coding: utf-8 -*-
from bs4 import BeautifulSoup as BS
import requests, requests.exceptions
from usersettings import userconfig as config

#print(config)
core=config['Cores']['1'] #the name of the index to use within the Solr backend
#url=config['Solr']['url']+core+'/select?q=' #Solr:url is the network address of Solr backend
hlarguments=config[core]['highlightingargs']
dfltsearchterm=config['Test']['testsearchterm']
#cursorargs=config[core]['cursorargs']
docpath=config[core]['docpath']
#arguments='&fl=id,date,content'


def cursor(mycore): #iterates through entire solr index in blocks of e.g. 100
    print('start scan')
    cursormark='*' #start a cursor scan with * and next cursor to begin with is returned
    nextcursor=''
    longdict={} #dictionary of index data, keyed on full filepath
    while True:
        args=mycore.cursorargs+'&cursorMark='+cursormark
        #print args
        res=getSolrResponse('*',args,mycore)
        #print res
        blocklist,resultsnumber=listresults(res)
        #print (blocklist,resultsnumber)
        more=res.response.result.next_sibling 
        if more['name']=='nextCursorMark':
            nextcursor=more.text
        else:
            print ('Missing next cursor mark')
        longdict.update(blocklist)
        if len(longdict)>resultsnumber: #added escape to prevent endless loop
            print('Breaking on long list')
            break
        if cursormark==nextcursor:
            break
        else:
            cursormark=nextcursor
    return longdict

def getSolrResponse(searchterm,arguments,mycore):
    searchurl=mycore.url+'/select?q='+searchterm+arguments
    ses = requests.Session()
    # the session instance holds the cookie. So use it to get/post later
    res=ses.get(searchurl)
    soup=BS(res.content,"html.parser")
    return soup
    
def listresults(soup):
#    counter=0
    try:
        numberfound=int(soup.response.result['numfound'])
        result=soup.response.result
        results={}
        for doc in result:
            document={}
#            counter+=1
            document['id']=doc.str.text
            for arr in doc:
                document[arr.attrs['name']]=arr.text
            fid=document['id'] #this is the main file ID used by Solr
            #indexing this output by file path to docpath
            path=document[docpath] #the docpath field defined in configs must be in cursorargs
            #print(path)
            #INDEX BY THE PATH STORED IN SOLR INDEX 
            results[path]=document
            #document['docname']=os.path.basename(id)
    except Exception as e: 
        print(e)
        results={}
        numberfound=0
    return results,numberfound
