# -*- coding: utf-8 -*-
from __future__ import unicode_literals, print_function
#go through 

def dedup(collection,core):
    if True:        
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
            
            
            
            
