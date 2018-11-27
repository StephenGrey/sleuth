# -*- coding: utf-8 -*-
import sys,datetime,time, logging, redis

from SearchBox.tools import wwwsearch_connect #Connect to Django project
from django.conf import settings
from documents import file_utils,changes,updateSolr,indexSolr
from documents.models import File,Collection
logging.config.dictConfig(settings.LOGGING)
log = logging.getLogger('ownsearch.watch_dispatch')
#if (log.hasHandlers()):
#    print('has handler')


r=redis.Redis(charset="utf-8", decode_responses=True)


"""

watcher thread:  - watching file system
report file events to wait q

wait thread: acts on threads
#delay before action - reindex after a few mins 
q of fileevents


worker thread: take action on fileevents


"""
MODIFIED_FILES={}
MODIFIED_TIMES={}

class Index_Dispatch:
    def __init__(self,event_type,sourcepath,destpath):
        self.event_type=event_type
        self.sourcepath=sourcepath
        self.destpath=destpath
        self.check_base()
        self.process()
        
    def process(self):
        log.info(f'EVENT: {self.event_type}  PATH: {self.sourcepath}  (DESTPATH: {self.destpath})')
        if self.event_type=='created':
            self.create()
        elif self.event_type=='modified':
            self.modify()
        elif self.event_type=='delete':
            self.delete()
        elif self.event_type=='moved':
            self.moved()
        self._index()
        log.debug(f'Modification queues: {MODIFIED_FILES}, TIMES: {MODIFIED_TIMES}')
        
    def create(self):
        if self.source_in_database:
            #exists already
            self.modify() #just check it's all ok
            return
            
        _collections=file_utils.find_collections(self.sourcepath)
        if not _collections:
            log.debug('Not in any collection - no modification of database')
            return
            
        for _collection in _collections:
            _newfile=changes.newfile(self.sourcepath,_collection)
            if _newfile:
                self.source_in_database.append(_newfile)
                log.debug(f'Created new record in Collection: \'{_collection}\' in Index: \'{_collection.core}\'')    
    
    def modify(self):
        if self.source_in_database:
            #MODIFIED_TIMES[self.sourcepath]=time.time()
            for _file in self.source_in_database:
                #putting modified file in q
                #MODIFIED_FILES.setdefault(self.sourcepath,set()).add(_file.id)
                r.sadd('MODIFIED_FILES',_file.id)
                r.set(f'MODIFIED_TIME.{_file.id}',time.time())
                print(f'Added: \'{_file}\' with id {_file.id}to modification queue')
#                if changes.changefile(_file):
#                    print(f'Modified: \'{_file}\' in Index: \'{_file.collection.core}\'')
        else:
            self.create()



    def moved(self):
        if self.dest_in_database and self.source_in_database:
            self.delete() #delete the origin - the destination will be picked up with move event
        elif self.dest_in_database and not self.source_in_database:
            pass #ignore as overwrite - will be picked up as modified event
        elif self.source_in_database and not self.dest_in_database:
            for _file in self.source_in_database:
                changes.movefile(_file,self.destpath)
        else:
            self.sourcepath=self.destpath #send new location to source path to create file record
            self.create() #create if within a collection
    
    def delete(self):
        """delete both from database and solr index, if indexed"""
        if self.source_in_database:
            for _file in self.source_in_database:
                deletefiles=[_file.filepath]
                collection=_file.collection
                updateSolr.removedeleted(deletefiles,collection) #docstore= use default in user settings
        else:
            log.debug(f'File not in database - nothing to delete')
            
            
    def check_base(self):
        _database_files=File.objects.filter(filepath=self.sourcepath)
        log.debug(f'Existing files found: {_database_files}')
        if len(_database_files)>0:
            self.source_in_database=_database_files
        else:
            self.source_in_database=[]
        
        if self.destpath:
            _database_files=File.objects.filter(filepath=self.destpath)
            if len(_database_files)>1:
                self.dest_in_database=_database_files
            else:
                self.dest_in_database=None            
    
    
    def _index(self):
        for _file in self.source_in_database:
            if not _file.indexedSuccess:
                log.debug(f'Now should index {_file} in solr')
                index_file(_file)
            elif _file.indexUpdateMeta:
                log.debug(f'Now should update solr meta for {_file}')
                updateSolr.metaupdate_rawfile(_file)

def index_file(_file):
    extractor=indexSolr.ExtractSingleFile(_file)
    print(extractor.__dict__)
    """options: forceretry=False,useICIJ=False,ocr=True,docstore=DOCSTORE """
    if extractor.failed==0:
        return True
    else:
        print('Extraction failed')
        return False

def index_file2(_file):
    pass


def make_index_job(collection_id,_test=False,force_retry=False):
    job_id=f'CollectionExtract.{collection_id}'
    makejob=r.sadd('SEARCHBOX_JOBS',job_id)
    if not makejob:
        log.info('task exists already')
        return job_id
    else:
        job=f'SB_TASK.{job_id}'
        r.hset(job,'task','extract_collection_force_retry') if force_retry else r.hset(job,'task','extract_collection')
        r.hset(job,'collection_id',collection_id)
        r.hset(job,'status','queued')
        r.hset(job,'test',_test)
        r.hmset(job,{'show_taskbar':True,'progress':0,'progress_str':"",'target_count':"",'counter':"",'skipped':"",'failed':"",'failed_list':""})
        return job_id

def make_scan_job(collection_id,_test=False):
    job_id=f'CollectionScan.{collection_id}'
    makejob=r.sadd('SEARCHBOX_JOBS',job_id)
    if not makejob:
        log.info('task exists already')
        return False
    else:
        job=f'SB_TASK.{job_id}'
        r.hset(job,'task','scan_collection')
        r.hset(job,'collection_id',collection_id)
        r.hset(job,'status','queued')
        r.hset(job,'test',_test)
        r.hmset(job,{'show_taskbar':True,'progress':0,'progress_str':"",'target_count':"",'moved':"",'new':"",'deleted':"",'unchanged':""})
        return job_id


def get_extract_results(job):
    return r.hgetall(job)
    
def task_check():
    job_ids=r.smembers('SEARCHBOX_JOBS')
    for job_id in job_ids:
        job=f'SB_TASK.{job_id}'
        if r.exists(job):
            log.debug(f'Processing {job}')
            task=r.hget(job,'task')
            if task=='extract_collection' or task=='extract_collection_force_retry':
                collection_id=r.hget(job,'collection_id')
                r.hset(job,'status','started')
                _test=True if r.hget(job,'test')=='True' else False
                log.info('This is a test') if _test else None
                log.info(f'indexing collection {collection_id}')
                try:
                    index_collection_id(job,collection_id,_test) if task=='extract_collection' else index_collection_id(job,collection_id,_test,forceretry=True)
                except updateSolr.s.SolrConnectionError as e:
                    log.error(f'Solr Connection Error: {e}')
                    r.hset(job,'status','error')
                    r.hset(job,'message','Solr connection error')
#                except Exception as e:
#                    log.error(f'Error: {e}')
#                    r.hset(job,'status','error')
#                    r.hset(job,'message','Unknown error')
                results=r.hgetall(job)
                log.info(results)
                r.srem('SEARCHBOX_JOBS',job_id)
                r.sadd('SEARCHBOX_JOBS_DONE',job_id)
            elif task=='scan_collection':
                collection_id=r.hget(job,'collection_id')
                log.info(f'scanning collection {collection_id}')
                scan_collection_id(job,collection_id)
                r.srem('SEARCHBOX_JOBS',job_id)
                r.sadd('SEARCHBOX_JOBS_DONE',job_id)
            else:
                log.info(f'no task defined .. killing job')
                r.delete(job)
                r.srem('SEARCHBOX_JOBS',job_id)


def scan_collection_id(job,collection_id,_test=False):
    _collection,_mycore=collection_from_id(collection_id)
    scanner=scan_collection(job,_collection,_test=_test)
    r.hset(job,'status','completed')
    if scanner:
        r.hmset(job,{
        'total':scanner.scanned_files,
        'new':scanner.new_files_count,
        'deleted':scanner.deleted_files_count,
        'moved':scanner.moved_files_count,
        'unchanged':scanner.unchanged_files_count,
        'changed':scanner.changed_files_count
        })

def scan_collection(job,_collection,_test=False):
    scanner=updateSolr.scandocs(_collection,job=job)
    return scanner

def collection_from_id(collection_id):
    _collection=Collection.objects.get(id=int(collection_id))
    _mycore=indexSolr.s.core_from_collection(_collection)
    return _collection,_mycore

def index_collection_id(job,collection_id,_test=False,forceretry=False):
    try:
        _collection,_mycore=collection_from_id(collection_id)
        ext=index_collection(_collection,_mycore,_test=_test,job=job)
        r.hset(job,'status','completed')
        if ext:
            r.hmset(job,{'counter':ext.counter,'skipped':ext.skipped,'failed':ext.failed,'failed_list':ext.failedlist})
        r.srem('COLLECTIONS_TO_INDEX',collection_id)
    except Collection.DoesNotExist:
        log.info(f'Collection id {collection_id} not valid ... deleting')
        r.hset(job,'status','error')
        r.hset(job,'message','collection not valid')
        r.srem('COLLECTIONS_TO_INDEX',collection_id)
                
def index_collection(thiscollection,mycore,_test=False,job=None,forceretry=False):
    assert isinstance(thiscollection,Collection)
    assert isinstance(mycore,indexSolr.s.SolrCore)
    log.info(f'extracting {thiscollection} in {mycore}')
    ext=indexSolr.Extractor(thiscollection,mycore,job=job,forceretry=True) if not _test else None #GO INDEX THE DOCS IN SOLR
    return ext

def modify_check(time_before_check):
    """ check and index modified file after waiting x seconds"""
    for n in r.smembers('MODIFIED_FILES'):
        _fileid=int(n)
        try:
            _file=file_from_id(_fileid)
            _rawmod=r.get(f'MODIFIED_TIME.{_file.id}')
            _modtime=float(_rawmod) if _rawmod else None
            _now=time.time()
            print(f'Checking: File:{_file} Modified: {int(_now-_modtime)} seconds ago')
            if _now-_modtime>time_before_check:
                print('needs update check')
                result=update_file(_file)
                log.info(f'{_file} updated: {result}')
                #remove checked files:
                r.srem('MODIFIED_FILES',_fileid)
                r.delete(f'MODIFIED_TIME.{_file.id}')                
        except File.DoesNotExist:
            print(f'{_fileid} not found .. removing from MODIFIED_FILES')
            r.srem('MODIFIED_FILES',_fileid)

def update_file(_file):
    if file_utils.changed_file(_file):
        print('This file needs updating')
        _file.hash_contents=''
        _file.indexedSuccess=False
        _file.indexedTry=False
        _file.save()
        return index_file(_file)
        

def update_filepath(filepath):
    #print(filepath,MODIFIED_FILES)
    file_ids=MODIFIED_FILES.pop(filepath)
    #print(f'Now modifying {file_ids}')
    files=files_from_id(file_ids)
    result=True
    for _file in files:
        if not update_file(_file):
            result=False
    return result


def file_from_id(_id):
    return File.objects.get(id=_id)
#
def files_from_id(_ids):
    return [File.objects.get(id=_id) for _id in _ids]
#
#if __name__ == "__main__":
#    path = sys.argv[1] if len(sys.argv) > 1 else '.'
    
    
#    event_handler = LoggingEventHandler()



