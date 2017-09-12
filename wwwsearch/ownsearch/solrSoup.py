# -*- coding: utf-8 -*-
#using 'id' as the uniquefield
from __future__ import unicode_literals
from bs4 import BeautifulSoup as BS
import requests, requests.exceptions
import os, logging
import re
from documents.models import File,Collection
from usersettings import userconfig as config
log = logging.getLogger('ownsearch')

#print(config)
core=config['Cores']['coredefault'] #the name of the index to use within the Solr backend
url=config['Solr']['url']+core+'/select?q=' #Solr:url is the network address of Solr backend
hlarguments=config[core]['highlightingargs']
dfltsearchterm=config['Test']['testsearchterm']
docpath=config[core]['docpath']
docnamefield=config[core]['docname']

#arguments='&fl=id,date,content'
contentarguments=config[core]['contentarguments']

def getdefault():
    soup=getSolrResponse(dfltsearchterm,hlarguments+'0')
    res,numbers=getlist(soup,0)
    return res,soup

def getSortAttrib(sorttype):
    if sorttype == 'documentID':
        sortattrib = config[core]['docsort']
    elif sorttype == 'last_modified':
        sortattrib = config[core]['datesort']
    else: #this is the default - sort by relevance
        sortattrib = ''
    return sortattrib

def solrSearch(q,sorttype,startnumber):
    args=hlarguments+str(startnumber)+getSortAttrib(sorttype)
    #print('args',args)
    try:
        soup=getSolrResponse(q,args)
        #print(soup.prettify())    
        reslist,numbers=getlist(soup,startnumber)
    except requests.exceptions.RequestException as e:
        reslist=[]
        numbers=-2
        print 'Connection error to Solr'
    return reslist,numbers

def getSolrResponse(searchterm,arguments):
    searchurl=url+searchterm+arguments
    #print (searchurl)
    ses = requests.Session()
    # the session instance holds the cookie. So use it to get/post later
    res=ses.get(searchurl)
    soup=BS(res.content,"html.parser")
    #print(soup.prettify())
    return soup


def getlist(soup,counter): #this parses the list of results, starting at 'counter'
    try:
        numberfound=int(soup.response.result['numfound'])
        result=soup.response.result
        results=[]
        for doc in result:
            document={}
            counter+=1
            document['id']=doc.str.text
            #now go through all fields returned by the solr search
            for arr in doc:
                document[arr.attrs['name']]=arr.text
            #give the docname a standard name  -- the field must be in the content args or this will return an error
            document['docname']=document[docnamefield]
            #print('extracted docname',document['docname'])
            fid=document['id'] #this is the main file ID used by Solr
            #document['docname']=os.path.basename(document[docpath])
            #print('extracted docname is:',document['docname'])

            #look up this in our model database, to see if additional data on this doc >>>SHOULD BE MOVED
            try: 
                f=File.objects.get(hash_filename=fid)
                #DEBUG print('FILE',f)
                document['path']=f.filepath
                document['filesize']=f.filesize
            except Exception as e:
                #print('Cannot look up file in database',e)
                document['path']=''
                document['filesize']=0
            document['resultnumber']=counter
            results.append(document)
    except Exception as e: 
        print(e)
        results=[]
        numberfound=0
    #DEBUG print ('results', results)
    if results:
        highlights=gethighlights(soup)
        if highlights:
              highlightedresults=[]
              for result in results:
                   try:
                       result['highlight']=highlights[result['id']]
                       highlightedresults.append(result)
                   except KeyError:
                       result['highlight']=''
                       highlightedresults.append(result)
              results=highlightedresults
    return results,numberfound

#print(results)
def gethighlights(soup):
    highlights={}
    highlights_all=soup.response.result.next_sibling
#    print ('highlightsall',highlights_all)
    try:
        highlights_all['name']=='highlighting'
    except:
        #no highlights
        return {}
    for item in highlights_all:
            #print (item)
        id=item['name']
        if item.arr:
#remove line returns
            highlight=item.arr.text.replace('\n','') 
#split by em tags to enable highlighting
            highlight=[highlight.split('<em>')[0]]+highlight.split('<em>')[1].split('</em>')
        else:
            highlight=''
        highlights[id]=highlight
    return highlights

# highlightall=results.highlighting[id]['content'][0].replace('$
# highlight=[highlightall.split('<em>')[0]]+highlightall.split($
#                                #       print(u"CONTEXT: ...{0}...".format(highlight))   
# resultlist.append([id,docname,lmod,ddate,wcount,author,highlight])

def getcontents(docid):
    searchterm=r'id:"'+docid+r'"'
    #print (searchterm,contentarguments)
    args=contentarguments
    sp=getSolrResponse(searchterm,args)
    res,numbers=getlist(sp,0)
    return res

def hashlookup(hex):
    searchterm='extract_id:'+hex
    #print (searchterm,contentarguments)
    args=hlarguments+'0'
    #print (args)
    sp=getSolrResponse(searchterm,args)
    res,numbers=getlist(sp,0)
    return res    



#res=getlist(sp)
#highlights=gethighlights(sp)

#contents = getcontents(eg)
#result=contents[0]
#print (results['contents'])

