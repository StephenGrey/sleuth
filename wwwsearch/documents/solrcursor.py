# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from builtins import str #backwards to py 2.X
from bs4 import BeautifulSoup as BS
import requests, requests.exceptions, logging, collections
from usersettings import userconfig as config
from ownsearch import solrJson
log = logging.getLogger('ownsearch.solrcursor')


class MissingCursorMark(Exception):
    pass

try:
    dfltsearchterm=config['Test']['testsearchterm']
except:
    dfltsearchterm=''

#class CursorResult(solrJson.SolrResult):
#    def next(self):
        
        
        



def getcore(corename):
    return solrJson.SolrCore(corename)

def cursor(mycore,keyfield='docpath',searchterm='*',highlights=False): #iterates through entire solr index in blocks of e.g. 100
    #if highlights is True, returns more complete data including highlights
    #print('start scan')
    #use standard naems for keyfields
    
    longdict={} #dictionary of index data, keyed on relative filepath
    res=False

    while True:
        try:
            res = cursornext(mycore,searchterm=searchterm,highlights=highlights,lastresult=res)
            if res == False:
                break
            #ESCAPE ROUTE ;
            if not res.results:
                break
        #PUT RESULTS INTO DICTIONARY KEYED BY KEYFIELD
            for document in res.results:
                #log.debug('{}, {}'.format(keyfield,document.__dict__))
                if keyfield in document.data:  #.data:
                    keystring=document.data[keyfield]
#                        print(keyfield,document.__dict__,keystring)
                elif keyfield in document.__dict__:
                    keystring=document.__dict__[keyfield]
                
                else:
                    #print('Solrcursor: no '+key+' in Solr document with ID: '+str(document['id']))
                    pass
                if isinstance(keystring,str):
                #making a list of docs for each key, appending each new doc:
                    longdict.setdefault(keystring,[]).append(document)
                else: #if it multivalued make dup for each key
                    for keyitem in keystring:
                        longdict.setdefault(keyitem,[]).append(document)                    
        except Exception as e:
            log.error('Solr Cursor exception: {}'.format(e))
            break
    return longdict

#    res=False
#    while True:
#        res = cursornext(mycore,lastresult=res)
#        if res == False:
#            break
#        #ESCAPE ROUTE ;
#        if not res.results:
#            print('END THIS NOW')
#            break
#        #DO SOMETHING WITH THE RESULTS
#
#
#    cursormark='*' #start a cursor scan with * and next cursor to begin with is returned
#    nextcursor=''
#    counted=0
#    longdict={} #dictionary of index data, keyed on relative filepath
#    while True:
#        try:
#            res=cursorResult(mycore,cursormark,searchterm)
#            counted+=res.counter
#
#            #PUT THE RESULTS INTO A DICTIONARY - KEYED BY THE KEYFIELD
#            if True:
#                for document in res.results:
##                    print(keyfield,document.__dict__)
#                    if keyfield in document.data:  #.data:
#                        keystring=document.data[keyfield]
##                        print(keyfield,document.__dict__,keystring)
#                    elif keyfield in document.__dict__:
#                        keystring=document.__dict__[keyfield]
#                    
#                    else:
#                        #print('Solrcursor: no '+key+' in Solr document with ID: '+str(document['id']))
#                        pass
#                    if isinstance(keystring,str):
#                    #making a list of docs for each key, appending each new doc:
#                        longdict.setdefault(keystring,[]).append(document)
#                    else: #if it multivalued make dup for each key
#                        for keyitem in keystring:
#                            longdict.setdefault(keyitem,[]).append(document)                    
#        except Exception as e:
#            log.error('Solr Cursor exception: {}'.format(e))
#            break
#        
#        #ESCAPE ROUTE ; only in event of errors from solr server
#        #print (counted,resultsnumber)
#        if counted>resultsnumber: #added escape to prevent endless loop
#            log.error('Breaking on long list')
#            break
#        #BREAK WHEN NEXT CURSOR IS SAME AS PREVIOUS NEXT CURSOR, which signals end of results 
#        if cursormark==res.nextcursormark:
#            break
#        else:
#            cursormark=res.nextcursormark
#    return longdict



def cursorResult(mycore,cursormark,searchterm,highlights=False):
    if highlights:
        args=mycore.cursorargs+'&hl.fl='+mycore.rawtext+'&hl=on&sort='+mycore.unique_id+'+asc&rows=100&cursorMark='+cursormark        
    else:
        args=mycore.cursorargs+'&sort='+mycore.unique_id+'+asc&rows=100&cursorMark='+cursormark

    jres=solrJson.getJSolrResponse(searchterm,args,mycore)
#    log.debug('Searchterm: {} Args: {} Mycore:{}'.format(searchterm,args,mycore))
#    log.debug('Result: {}'.format(jres))
    solrresult=solrJson.SolrResult(jres,mycore) #processresult
    if highlights:
        solrresult.addhighlights() #add the highlights to the results
    if solrresult.nextcursormark =='':
        log.error('Missing next cursor mark')
        raise MissingCursorMark
    else:
        return solrresult

#KEEP RETURNING CURSOR RESULTS IN BLOCKS UNTIL NO MORE
def cursornext(mycore,searchterm='*',highlights=False,lastresult=False):
    if lastresult:
        cursormark=lastresult.nextcursormark
        if lastresult.nextcursormark=='ENDED':
            return False
    else:
        cursormark='*'
    res=cursorResult(mycore,cursormark,searchterm,highlights=highlights)
    if res.nextcursormark==cursormark:
        res.nextcursormark='ENDED'
    return res

def cursorloop(mycore,searchterm='*',highlights=False):
    res=False
    while True:
        res = cursornext(mycore,searchterm='*',highlights=False,lastresult=res)
        if res == False:
            break
        #ESCAPE ROUTE ;
        if not res.results:
            break
        #DO SOMETHING WITH THE RESULTS

#RETURN ENTIRE SET OF RESULTS FOR A GIVEN SEARCH TERM, SORTED BY A FIELD (sorttype)
def cursorSearch(q,keyfield,mycore,highlights=False):
    #check variables are valid
    assert isinstance(mycore,solrJson.SolrCore)
    mycore.ping()
    assert isinstance(keyfield,str)
    assert isinstance(q,str)
    
    unsortedcursor=cursor(mycore,keyfield=keyfield,searchterm=q,highlights=highlights)
    #sorting by keyfield
#    log.debug(unsortedcursor)
    sortedcursor=collections.OrderedDict(sorted(unsortedcursor.items(),key=lambda key: key[0].lower()))
    #log.debug(str(unsortedcursor))
    return sortedcursor
    
    