# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from builtins import str #backwards to py 2.X
from bs4 import BeautifulSoup as BS
import logging, collections
from configs import config
from ownsearch import solrJson
log = logging.getLogger('ownsearch.solrcursor')


class MissingCursorMark(Exception):
    pass

try:
    dfltsearchterm=config['Test'].get('testsearchterm','')
except:
    dfltsearchterm='company'

##MAIN FUNCTIONS
def cursor_by_name(corename='coreexample'):
    """return iteration of entire index, called by indexname"""
    mycore=solrJson.SolrCore(corename)
    res=cursor(mycore)
    return res


def cursor(mycore,keyfield='docpath',searchterm='*',highlights=False,rows=100): 
    """unsorted iteration through entire solr index"""
    #if highlights is True, returns more complete data including highlights
    #use standard names for keyfields
    
    longdict={} #dictionary of index data, keyed on relative filepath
    res=False

    while True:
        try:
            res = cursor_next(mycore,searchterm=searchterm,highlights=highlights,lastresult=res,rows=rows)
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
                    log.debug('Solrcursor: no \'{}\' in Solr document with ID: '.format(keyfield,document.id))
                    continue
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


def cursor_sorted(q,keyfield,mycore,highlights=False):
    """iteration of entire Solr index, sorted by a keyfield"""
    #returns an ordered dictionary
    
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

def cursor_next(mycore,searchterm='*',highlights=False,lastresult=False,rows=100):
    """KEEP RETURNING CURSOR RESULTS IN BLOCKS UNTIL NO MORE"""
    if lastresult:
        cursormark=lastresult.nextcursormark
        if lastresult.nextcursormark=='ENDED':
            return False
    else:
        cursormark='*'
    res=cursor_result(mycore,cursormark,searchterm,highlights=highlights,rows=rows)
    if res.nextcursormark==cursormark:
        res.nextcursormark='ENDED'
    return res


def cursor_result(mycore,cursormark,searchterm,highlights=False,rows=100):
    if highlights:
        args=mycore.cursorargs+'&hl.fl='+mycore.rawtext+'&hl=on&sort='+mycore.unique_id+'+asc&rows='+str(rows)+'&cursorMark='+cursormark        
    else:
        args=mycore.cursorargs+'&sort='+mycore.unique_id+'+asc&rows='+str(rows)+'&cursorMark='+cursormark

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


