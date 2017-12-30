# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from bs4 import BeautifulSoup as BS
import requests, requests.exceptions, logging, collections
from usersettings import userconfig as config
from ownsearch import solrJson
log = logging.getLogger('ownsearch.solrcursor')
#print(config)
#core=config['Cores']['1'] #the name of the index to use within the Solr backend
#url=config['Solr']['url']+core+'/select?q=' #Solr:url is the network address of Solr backend
#hlarguments=config[core]['highlightingargs']
class MissingCursorMark(Exception):
    pass

try:
    dfltsearchterm=config['Test']['testsearchterm']
except:
    dfltsearchterm=''
#cursorargs=config[core]['cursorargs']
#docpath=config[core]['docpath']
#arguments='&fl=id,date,content'

def getcore(corename):
    return solrJson.SolrCore(corename)

def cursor(mycore,keyfield='docpath',searchterm='*',highlights=False): #iterates through entire solr index in blocks of e.g. 100
    #if highlights is True, returns more complete data including highlights
    #print('start scan')
#    keyfield=getattr(mycore,key,'id') #get solr field to use as key, default to id
    cursormark='*' #start a cursor scan with * and next cursor to begin with is returned
    nextcursor=''
    counted=0
    longdict={} #dictionary of index data, keyed on relative filepath
    while True:
        if highlights:
            args=mycore.cursorargs+'&hl.fl='+mycore.rawtext+'&hl=on&sort=id+asc&rows=100&cursorMark='+cursormark        
        else:
            args=mycore.cursorargs+'&sort=id+asc&rows=100&cursorMark='+cursormark
        #print args
        try:
            jres=solrJson.getJSolrResponse(searchterm,args,mycore)
            print(jres)
#            blocklist,resultsnumber,counter=listresults(res,mycore)
            solrresult=solrJson.SolrResult(jres,mycore) #processresult
            
            if highlights:
                solrresult.addhighlights() #add the highlights to the results
            blocklist=solrresult.results
            counter=solrresult.counter
            resultsnumber=solrresult.numberfound
            counted+=counter
            #print (resultsnumber,counter)
            #extract next cursor from the result
            if 'nextCursorMark' in jres:
                nextcursor=jres['nextCursorMark']
            else:
                log.error('Missing next cursor mark')
                raise MissingCursorMark
            if True:
                for document in blocklist:
                    if keyfield in document.__dict__ :  #.data:
                        keystring=document.__dict__[keyfield]
                        
                        if isinstance(keystring,basestring):
                        #making a list of docs for each key, appending each new doc:
                            longdict.setdefault(keystring,[]).append(document)
                        else: #if it multivalued make dup for each key
                            for keyitem in keystring:
                                longdict.setdefault(keyitem,[]).append(document)
                    else:
                        #print('Solrcursor: no '+key+' in Solr document with ID: '+str(document['id']))
                        pass
        except Exception as e:
            log.error(str(e))
            break
        
        #ESCAPE ROUTE ; only in event of errors from solr server
        #print (counted,resultsnumber)
        if counted>resultsnumber: #added escape to prevent endless loop
            log.error('Breaking on long list')
            break
        #BREAK WHEN NEXT CURSOR IS SAME AS PREVIOUS NEXT CURSOR, which signals end of results 
        if cursormark==nextcursor:
            break
        else:
            cursormark=nextcursor
    return longdict

#def getSolrResponse(searchterm,arguments,mycore):
#    searchurl=mycore.url+'/select?q='+searchterm+arguments
#    ses = requests.Session()
#    # the session instance holds the cookie. So use it to get/post later
#    res=ses.get(searchurl)
#    soup=BS(res.content,"html.parser")
#    return soup
    
#def listresults(soup,mycore):
#    solrresult=solrJson.SolrResult(soup,mycore)
#    solrresult.addhighlights()
#    results=solrresult.results
#    counter=solrresult.counter
#    numberfound=solrresult.numberfound
#    
#    results=[]
#    counter=0
#    result=soup.response.result
#    if result.has_attr('numfound'):
#        numberfound=int(result['numfound'])
#    else:
#        print('No results found in listresults')
#        return {},0
#
#    #loop through each doc in resultset
#    for doc in result:
#        #print('DOC',doc)
#        #get standardised result
#        parsedoc=solrJson.Solrdoc(doc,mycore)
##        
#        results.append(parsedoc.data)
#        counter+=1
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

#RETURN ENTIRE SET OF RESULTS FOR A GIVEN SEARCH TERM, SORTED BY A FIELD (sorttype)
def cursorSearch(q,keyfield,mycore,highlights=False):
    #check variables are valid
    assert isinstance(mycore,solrJson.SolrCore)
    mycore.ping()
    assert isinstance(keyfield,basestring)
    assert isinstance(q,basestring)
    
    unsortedcursor=cursor(mycore,keyfield=keyfield,searchterm=q,highlights=highlights)
    #sorting by keyfield
#    log.debug(unsortedcursor)
    sortedcursor=collections.OrderedDict(sorted(unsortedcursor.items(),key=lambda key: key[0].lower()))
    #log.debug(str(unsortedcursor))
    return sortedcursor
    
    