# -*- coding: utf-8 -*-
from bs4 import BeautifulSoup as BS
import requests, requests.exceptions
from usersettings import userconfig as config
from ownsearch import solrSoup

#print(config)
#core=config['Cores']['1'] #the name of the index to use within the Solr backend
#url=config['Solr']['url']+core+'/select?q=' #Solr:url is the network address of Solr backend
#hlarguments=config[core]['highlightingargs']
dfltsearchterm=config['Test']['testsearchterm']
#cursorargs=config[core]['cursorargs']
#docpath=config[core]['docpath']
#arguments='&fl=id,date,content'

def getcore(corename):
    return solrSoup.SolrCore(corename)

def cursor(mycore): #iterates through entire solr index in blocks of e.g. 100
    #print('start scan')
    cursormark='*' #start a cursor scan with * and next cursor to begin with is returned
    nextcursor=''
    longdict={} #dictionary of index data, keyed on full filepath
    while True:
        args=mycore.cursorargs+'&cursorMark='+cursormark
        #print args
        res=getSolrResponse('*',args,mycore)
        blocklist,resultsnumber=listresults(res,mycore)
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
    
def listresults(soup,mycore):
    
    results={}
    result=soup.response.result
    if result.has_attr('numfound'):
        numberfound=int(result['numfound'])
    else:
        print('No results found in listresults')
        return {},0

    #loop through each doc in resultset
    for doc in result:
        #print('DOC',doc)
        document={}
        #get all the attributes
        document['id']=doc.str.text
        for arr in doc:
            if 'name' in arr.attrs:
                document[arr.attrs['name']]=arr.text
        #indexing these attributes, keyed to filepath from field defined in mycore.docpath
        #print(document)
        if mycore.docpath in document:
            path=document[mycore.docpath] #the docpath field defined in configs 'cursorargs'
            #print(path)
            results[path]=document
            #document['docname']=os.path.basename(id)
        else:
            print('Solrcursor: no filepath defined in this Solr document: ',document)
    return results,numberfound
