# -*- coding: utf-8 -*-
from __future__ import unicode_literals, print_function
from documents import solrcursor
from ownsearch import solrSoup

#get cursor of index, collecting hash data
#optionally delete the newest version
#or- by default - check name of file and path; delete the newest if these also duplicate.

def dedup(core):
    docpath=getattr(core,'docpath')
    docnamefield=getattr(core,'docnamefield')
    if True:
        key='hashcontentsfield'
        coredict=solrcursor.cursor(core,key=key)
        for key in coredict:
            if len(coredict[key])>1:
                #check for duplicate paths
                pathdict={}
                for dup in coredict[key]:
                    #print(dup[docpath])
                    pathdict.setdefault(dup[docpath],[]).append(dup['id'])
                #print (pathdict)
                for path in pathdict:
                    if len(pathdict[path])>1:
                        print('\nHASH:'+key)
                        print(path,pathdict[path])
    return coredict

def duppaths(core,key,key2=''):
    dups=[]
    docpath=getattr(core,key)
    if key2:
        key2field=getattr(core,key2)    
    #get dictionary to entire solr index, keyed to main'key' e.g folder
    solrdict=solrcursor.cursor(core,key=key)
    #print (solrdict)

    for indexkey in solrdict: #e.g loop through each folder
        #CHECK ONE: #DUPLICATE ENTRY FOR KEY e.g folder
        if len(solrdict[indexkey])>1:
            #DUPLICATE ENTRY FOR KEY
            #print('\nPATH:'+indexkey)
            
            if key2:
                #check for duplicate under second key e.g filename
                sortagain={}
                for solrdoc in solrdict[indexkey]: #e.g for docs in folder
                    if key2field in solrdoc: #if the second key is present in solr doc
                        
                        #making a dictionary of second key and list of solr records(denoted by id)
                        sortagain.setdefault(solrdoc[key2field],[]).append(solrdoc['id'])
                #print('resorted',sortagain)
                for otherkey in sortagain:
                    if len(sortagain[otherkey])>1: #more than one entry for 2ndkey e.g filename
                        duplist=[]
                        for id in sortagain[otherkey]:
                            #print('Duplicate:',indexkey,filename,id)
                            duplist.append(id)
                        dups.append((indexkey,otherkey,duplist))
            else:
                duplist=[]
                for solrdoc in solrdict[indexkey]: #e.g for docs in folder
                    duplist.append(solrdoc['id'])
                dups.append((indexkey,'',duplist))
            
            
    print(dups)
    return dups
    

def test(coreid):
    core=solrSoup.SolrCore(coreid)
    print('Checking for dups in ',core.name)
    key='docnamefield'#'docpath'
#    key2='docnamefield'
    dups=duppaths(core,key)
    return dups

"""
        #main loop - go through files in the collection
        for file in filelist:
            relpath=os.path.relpath(file.filepath,start=docstore) #extract the relative path from the docstore
        
            hash=file.hash_contents #get the stored hash of the file contents
            if not hash:
                hash=hexfile(file.filepath)
                file.hash_contents=hash
                file.save()
        
            #now lookup hash in solr index
            solrresult=solr.hashlookup(hash,thiscore)
            #print(solrresult)
            if len(solrresult)>0:
                #if some files, take the first one
                solrdata=solrresult[0]
                #print('solrdata:',solrdata)
                file.indexedSuccess=True
                file.solrid=solrdata['id']
                file.save()
                counter+=1
                #print ('PATH :'+file.filepath+' indexed successfully (HASHMATCH)', 'Solr \'id\': '+solrdata['id'])
            #NO MATCHES< RETURN FAILURE
            
"""         
            
