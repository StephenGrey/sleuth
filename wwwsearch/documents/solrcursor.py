# -*- coding: utf-8 -*-
from bs4 import BeautifulSoup as BS
import requests, requests.exceptions
from usersettings import userconfig as config
from ownsearch import solrSoup

#print(config)
#core=config['Cores']['1'] #the name of the index to use within the Solr backend
#url=config['Solr']['url']+core+'/select?q=' #Solr:url is the network address of Solr backend
#hlarguments=config[core]['highlightingargs']
try:
    dfltsearchterm=config['Test']['testsearchterm']
except:
    dfltsearchterm=''
#cursorargs=config[core]['cursorargs']
#docpath=config[core]['docpath']
#arguments='&fl=id,date,content'

def getcore(corename):
    return solrSoup.SolrCore(corename)

def cursor(mycore,key='docpath'): #iterates through entire solr index in blocks of e.g. 100
    #print('start scan')
    keyfield=getattr(mycore,key,'id') #get solr field to use as key, default to id
    cursormark='*' #start a cursor scan with * and next cursor to begin with is returned
    nextcursor=''
    counted=0
    longdict={} #dictionary of index data, keyed on relative filepath
    while True:
        args=mycore.cursorargs+'&cursorMark='+cursormark
        #print args
        res=getSolrResponse('*',args,mycore)
        blocklist,resultsnumber,counter=listresults(res,mycore,key)
        #print (resultsnumber,counter)
        more=res.response.result.next_sibling
        counted+=counter
        #extract next cursor from the result
        if more['name']=='nextCursorMark':
            nextcursor=more.text
        else:
            print ('Missing next cursor mark')

        if True:
            for document in blocklist:
                if keyfield in document:
                    keystring=document[keyfield]
#                    print(keystring) 
                    #making a list of docs for each key, appending each new doc:
                    longdict.setdefault(keystring,[]).append(document)
                 #document['docname']=os.path.basename(id)
                else:
                    #print('Solrcursor: no '+key+' in Solr document with ID: '+str(document['id']))
                    pass

        #ESCAPE ROUTE ; only in event of errors from solr server
        #print (counted,resultsnumber)
        if counted>resultsnumber: #added escape to prevent endless loop
            print('Breaking on long list')
            break
        #BREAK WHEN NEXT CURSOR IS SAME AS PREVIOUS NEXT CURSOR, which signals end of results 
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
    
def listresults(soup,mycore,key):
    results=[]
    counter=0
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
        results.append(document)
        counter+=1
    return results,numberfound,counter
                

#
#        if key=='filepath':
#        #indexing these attributes, keyed to filepath from field defined in mycore.docpath
#            #print(document)
#            if mycore.docpath in document:
#                path=document[mycore.docpath] #the docpath field defined in configs 'cursorargs'
#                #print(path)
#                results[path]=document
#                #document['docname']=os.path.basename(id)
#            else:
#                print('Solrcursor: no filepath in Solr document with ID: '+str(document['id']))
#        else:
#        #key to hash of contents
#            if mycore.hashcontentsfield in document:
#                hash=document[mycore.docpath] #the docpath field defined in configs 'cursorargs'
#                #print(path)
#                results[hash]=document
#                
#            else:
#                print('Solrcursor: no hash contents in Solr document with ID :'+str(document)['id']))
#    return results,numberfound
