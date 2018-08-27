# -*- coding: utf-8 -*-
from __future__ import unicode_literals, print_function
from documents import solrcursor,updateSolr
from ownsearch import solrJson
from usersettings import userconfig as config
import os
#get cursor of solr index, indexing that by key which can be any field, usually a filename or contentshash
#optionally delete the newest version of any duplicate solrdoc indexed by that key
#or- by default - check name of file and path; delete the newest if these also duplicate.


def hashdups(core):
    key='hashcontents'
    dups=dupkeys(core,key)
    

    return dups
    
def filepathdups(core,delete=False):
    pathfield='docpath'
    namefield='docname'
    datefield='date'
    dups=dupkeys(core,pathfield,key2field=namefield)
    dupcount,deletecount=0,0
    
    for path,name,duplist in dups:
        #IGNORE DUPS IF NO FILENAME OR PATH STORED  (avoids emails)
        #IGNORE IF FILE PATH DOES NOT EXIST ON LOCAL (avoids false dups on mis-stored paths e.g unicode filenames)
        #FILENAME MUST MATCH BASENAME IN PATH (avoids attachment, subfiles )
        
        if path!='' and name!='' and os.path.exists(path) and os.path.basename(path)==name:
            print('\nDUPLICATE: (key1)',path,'(key2)',name)
    #        print(duplist)
            sortedlist = sorted(duplist, key=lambda k: k[datefield],reverse=True)
    #        print(sortedlist
    
            for dup in duplist:
                if dup == duplist[0]:
                    deletethis=False
                    print ('DUP TO KEEP:')
                else:
                    print ('DUP TO DELETE: ')
                    deletethis=True
                    dupcount+=1
                #print (dup)
                if dup[datefield]!='':
                    #print (dup[datefield])
                    date=solrSoup.timefromSolr(dup.get(datefield))
                    datestring=solrSoup.timestring(date)
                else:
                    datestring=''
                    
                print('ID: \"'+dup['id']+'\"','\nFILENAME:'+dup[namefield],' DATE: '+datestring,' HASH: '+dup['hashcontents'])    
                
                #NOW DELETE THE DUP
                if delete==True and deletethis==True:
                    if updateSolr.delete(dup[core.unique_id],core):
                        print('... deleted from solr index')
                        deletecount+=1

    return dupcount,deletecount

def dupkeys(core,keyfield1,key2field=''):
    dups=[]
#    docpath=getattr(core,key)
#    if key2:
#        key2field=getattr(core,key2)    
    #get dictionary to entire solr index, keyed to main'key' e.g folder
    solrdict=solrcursor.cursor(core,keyfield=keyfield1)
    
    #print (solrdict)
    for indexkey in solrdict: #e.g loop through each folder
        #CHECK ONE: #DUPLICATE ENTRY FOR KEY e.g folder
        if len(solrdict[indexkey])>1:
            #DUPLICATE ENTRY FOR KEY
            #print('\nPATH:'+indexkey)
            if key2field:
                #check for duplicate under second key e.g filename
                sortagain={}
                for solrdoc in solrdict[indexkey]: #e.g for docs in folder
                    key2value=getattr(solrdoc,key2field)
                    if key2value: #if the second key is present in solr doc
                        #making a dictionary of second key and list of solr records(denoted by id)
                        sortagain.setdefault(key2value,[]).append(solrdoc)
                for otherkey in sortagain:
                    if len(sortagain[otherkey])>1: #more than one entry for 2ndkey e.g filename
                        duplist=[]
                        for doc in sortagain[otherkey]:
                            #print('Duplicate:',indexkey,filename,id)
                            duplist.append(doc)
                        dups.append((indexkey,otherkey,duplist))
            else:
                duplist=[]
                for solrdoc in solrdict[indexkey]: #e.g for docs in folder
                    duplist.append(solrdoc)
                dups.append((indexkey,'',duplist))
            
#    print(dups)
    return dups



def listdups(dups,core):
    docnamefield='docname' #getattr(core,'docnamefield')
    datefield='date' #getattr(core,'datefield')
    for key1,key2,duplist in dups:
        print('\nDUPLICATE: (key1)',key1,'(key2)',key2)
#        print(duplist)
        sortedlist = sorted(duplist, key=lambda k: k[datefield],reverse=True)
#        print(sortedlist) 
        for dup in duplist:
            #print (dup)
            if dup[datefield]!='':
                #print (dup[datefield])
                date=solrSoup.timefromSolr(dup.get(datefield))
                datestring=solrSoup.timestring(date)
            else:
                datestring=''
            print('ID: \"'+dup['id']+'\"','\nFILENAME:'+dup[docnamefield],' DATE: '+datestring)
            

    
def test(core='',delete=False):
    if core=='':
        #get a default core for test
        cores=solrSoup.getcores()
        defaultcoreID=config['Solr']['defaultcoreid']
        if defaultcoreID not in cores:
            try:
                defaultcoreID=cores.keys()[0]  #take any old core, if default not found
            except Exception as e:
                defaultcoreID='1' #and if no cores defined , just make it 1
        core=cores[defaultcoreID]
    print('Checking for dups in ',core.name)
#    key='docnamefield'#'docpath'
#    key2='docnamefield'
#    dups=hashdups(core)
#    dups=dupkeys(core,key)
    dupcount,deletecount=filepathdups(core,delete=delete)
#    listdups(dups,core)
    return dupcount,deletecount

"""
      "tika_metadata_last_modified":["2016-03-19T16:40:00Z"],
        "id":"8d27bf79-759d-4209-9077-de71148e7cb6"}]
  }}
  
"""