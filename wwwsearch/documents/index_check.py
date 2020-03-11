# -*- coding: utf-8 -*-
import logging,os, configs,time
from . import solrcursor
from .indexSolr import UpdateMeta,ChildProcessor
from .file_utils import get_contents_hash
from .models import File,Collection
from .updateSolr import get_source, updatetags
from ownsearch import solrJson as solr

log = logging.getLogger('ownsearch.index_check')
try:
    BASEDIR=configs.config['Models']['collectionbasepath'] #get base path of the docstore
except:
    log.error('No BaseDirectory defined')

#checking for what files in existing solrindex
def index_check(collection,thiscore):
    log.info(f'Checking index {thiscore} with collection: {collection}')
    log.debug(f'BASEDIR: {BASEDIR}')
    
    filelist=File.objects.filter(collection=collection)
    counter,skipped,failed=main_checks(collection,filelist,thiscore)
    meta_loop(collection,thiscore,filelist=filelist)
    return counter,skipped,failed


def main_checks(collection,filelist,thiscore):
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
    #main loop - go through files in the collection
        for file in filelist:
            relpath=os.path.relpath(file.filepath,start=BASEDIR) #extract the relative path from the docstore
            hash=file.hash_contents #get the stored hash of the file contents
            file.indexFails=0 #reset the indexing tries
            counter+=1
            if counter%500==0:
                log.info(f'checking file number {counter}')

	#INDEX CHECK: METHOD ONE : IF RELATIVE PATHS STORED MATCH
            if relpath in indexpaths:  #if the path in database in the solr index
                solrdata=indexpaths[relpath][0] #take the first of list of docs with this path
                #print ('PATH :'+file.filepath+' found in Solr index', 'Solr \'id\': '+solrdata['id'])
                file.indexMetaOnly=solrdata.data.get('sb_meta_only')
                #log.debug(f'Meta-only flagged for {file.filename}:{file.indexMetaOnly}')
                if not file.indexMetaOnly:
                    file.indexedSuccess=True
                    file.indexMetaOnly=False #turn a possible None into a False
                else:
                    file.indexedSuccess=False
                file.solrid=solrdata.id
                file.save()
                
                continue
        #INDEX CHECK: METHOD TWO: CHECK IF FILE STORED IN SOLR INDEX UNDER CONTENTS HASH
            elif not file.is_folder:
                try:
                    
                    #is there a stored hash, if not get one
                    if not hash:
                        hash=hexfile(file.filepath)
                        file.hash_contents=hash
                        file.save()
                    log.debug(f'searching by hash {hash} for {file.filepath}')
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
                    
                    #meta_check(thiscore,file,solrdata)
                    
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
        
def meta_loop(collection,thiscore,filelist=None):
    if not filelist:
        filelist=File.objects.filter(collection=collection)
    #now check meta
    counter=0
    log.info('now checking meta')
    start = time.time()
    for _file in filelist:
         
         if _file.solrid and not _file.is_folder:
             #log.debug('found index for doc - now checking meta'
           
             solrresult= solr.getmeta(_file.solrid,thiscore)
             if solrresult:
                 solrdata=solrresult[0]
                 if solrdata:
                     meta_check(thiscore,_file,solrdata)
                     counter+=1
                     if counter%1000==0:
                         log.info('committing changes - indexed file{counter}')
                         thiscore.commit()
    
    thiscore.commit()
    duration=time.time()-start
    log.info(f'Completed meta check of collection {collection } in solr index {thiscore} in {duration}')
    return

def meta_check(thiscore,file,solrdata):
    #check the meta
    #log.debug('found index for doc - now checking meta')
    meta_updater=UpdateMeta(thiscore,file,solrdata,docstore=BASEDIR,existing=True,check=False)
    
    if not file.is_folder:
        c=ChildProcessor(file.filepath,thiscore,hash_contents=file.hash_contents,sourcetext=get_source(file),docstore=BASEDIR,check=False)
        c.process_children()


def time_check(thiscore,collection):
    _items=File.objects.filter(collection=collection)[100:1000]
    _count=len(_items)
    _updatecount=0
    print(f'Found {_count} items')
    start = time.time()
    
    lookup_time=0
    update_time=0
    hash_time=0
    for _file in _items:
        
        ministart=time.time()
        if _file.is_folder:
            _hash=_file.hash_filename
            log.info(f'Folder {_file.filename} ')
        else:
            _hash=_file.hash_contents
            if not _hash:
                _hash=get_contents_hash(_file.filepath)
                _file.hash_contents=_hash
                _file.save()

            #log.info(f'{_file.filename} with hash {_hash}')            
        item_time=time.time()-ministart
        hash_time+=item_time
        
        #check for stored doc
        ministart=time.time()
        solrresult= solr.getmeta(_hash,thiscore)
        item_time=time.time()-ministart
        lookup_time+=item_time        
        #log.info(solrresult[0].__dict__)
        if solrresult:
            _updatecount+=1
            ministart=time.time()
            up=UpdateMeta(thiscore,_file,solrresult[0],docstore=BASEDIR,existing=True,check=False)
            item_time=time.time()-ministart
            update_time+=item_time

    thiscore.commit()

    end=time.time()
    duration=end - start
    print(f'Items {_count}')
    print(f'Lasted {duration} seconds, or {duration/_count:.3f} per item')
    print(f'Hash time {hash_time/_count:.3f} per item')
    print(f'Update time {update_time/_updatecount:.3f} per item')
    print(f'Lookup time {update_time/_count:.3f} per item')
