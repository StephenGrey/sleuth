# -*- coding: utf-8 -*-
import logging,os, configs
from . import solrcursor
from .indexSolr import UpdateMeta,ChildProcessor
from .models import File,Collection
from .updateSolr import get_source
from ownsearch import solrJson as solr
log = logging.getLogger('ownsearch.index_check')
try:
    BASEDIR=configs.config['Models']['collectionbasepath'] #get base path of the docstore
except:
    log.error('No BaseDirectory defined')

#checking for what files in existing solrindex
def index_check(collection,thiscore):

    log.debug(f'BASEDIR: {BASEDIR}')
    #first get solrindex ids and key fields
    try:#make a dictionary of filepaths from solr index
        indexpaths=solrcursor.cursor(thiscore)
        #log.debug(f'Indexpaths: {indexpaths}')
    except Exception as e:
        log.warning('Failed to retrieve solr index')
        log.warning(str(e))
        return 0,0,0
    #now compare file list with solrindex
    if True:
        counter=0
        skipped=0
        failed=0
        #print(collection)
        filelist=File.objects.filter(collection=collection)

        #main loop - go through files in the collection
        for file in filelist:
            relpath=os.path.relpath(file.filepath,start=BASEDIR) #extract the relative path from the docstore
            hash=file.hash_contents #get the stored hash of the file contents
            #print (file.filepath,relpath,file.id,hash)
            file.indexFails=0 #reset the indexing tries

	#INDEX CHECK: METHOD ONE : IF RELATIVE PATHS STORED MATCH
            if relpath in indexpaths:  #if the path in database in the solr index
                solrdata=indexpaths[relpath][0] #take the first of list of docs with this path
                #print ('PATH :'+file.filepath+' found in Solr index', 'Solr \'id\': '+solrdata['id'])
                
                log.debug('found index for doc - now checking meta')
                meta_check(thiscore,file,solrdata)
                                
                file.indexMetaOnly=solrdata.data.get('sb_meta_only')
                #log.debug(f'Meta-only flagged for {file.filename}:{file.indexMetaOnly}')
                if not file.indexMetaOnly:
                    file.indexedSuccess=True
                    file.indexMetaOnly=False #turn a possible None into a False
                    
                else:
                    file.indexedSuccess=False
                file.solrid=solrdata.id
                file.save()
                counter+=1
                continue
        #INDEX CHECK: METHOD TWO: CHECK IF FILE STORED IN SOLR INDEX UNDER CONTENTS HASH
            elif not file.is_folder:
                try:
                    log.debug(f'searching by hash for {file.filepath}')
                    #is there a stored hash, if not get one
                    if not hash:
                        hash=hexfile(file.filepath)
                        file.hash_contents=hash
                        file.save()
                    #now lookup hash in solr index
                    #log.debug('looking up hash : '+hash)
                    solrresult=solr.hashlookup(hash,thiscore).results
                    #log.debug(solrresult)
                    
                except Exception as e:
                    log.error(e)
                    solrresult=''
                
                if len(solrresult)>0:
                    #if some files, take the first one
                    solrdata=solrresult[0]
                    log.debug('Data found in solr: {}'.format(vars(solrdata)))
                    
                    meta_check(thiscore,file,solrdata)
                    
                    file.indexedSuccess=True
                    file.solrid=solrdata.id
                    file.save()
                    counter+=1
                    log.debug(f'PATH : {file.filepath} indexed successfully (HASHMATCH) Solr \'id\': {solrdata.id}')
                    
                    continue
                    
            #NO MATCHES< RETURN FAILURE

            log.info(f'\"{file.filepath}\" not found in Solr index')
            file.indexedSuccess=False
            file.indexedTry=False #reset indexing try flag
            file.indexMetaOnly=False #reset flag for index only
            file.solrid='' #wipe any stored solr id; DEBUG: this wipes also oldsolr ids scheduled for delete
            file.save()
            skipped+=1
                
                    
        return counter,skipped,failed


def meta_check(thiscore,file,solrdata):
    #check the meta
    log.debug('found index for doc - now checking meta')
    meta_updater=UpdateMeta(thiscore,file,solrdata,docstore=BASEDIR,existing=True)
    
    c=ChildProcessor(file.filepath,thiscore,hash_contents=file.hash_contents,sourcetext=get_source(file),docstore=BASEDIR)
    c.process_children()
    
