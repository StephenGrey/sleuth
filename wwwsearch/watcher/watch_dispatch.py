# -*- coding: utf-8 -*-
import sys,datetime,time, logging, redis, sys,traceback,os

from tools import wwwsearch_connect #Connect to Django project
from django.conf import settings
from documents import file_utils,changes,updateSolr,indexSolr,redis_cache
from documents.models import File,Collection
logging.config.dictConfig(settings.LOGGING)
log = logging.getLogger('ownsearch.watch_dispatch')
#if (log.hasHandlers()):
#    print('has handler')

r=redis_cache.redis_connection
#redis.Redis(charset="utf-8", decode_responses=True)
log.info('initialising watcher')

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


class HeartBeat:
    def tick(self):
        r.set('SB_heartbeat','tick')
    def tock(self):
        r.set('SB_heartbeat','tock')

    @property
    def alive(self):
        if r.get('SB_heartbeat') == 'tock':
            return False
        self.tock()
        return True



class Index_Dispatch:
    def __init__(self,event_type,sourcepath,destpath):
        self.event_type=event_type
        self.sourcepath=sourcepath
        self.ignore=True if indexSolr.ignorefile(self.sourcepath) else False
        self.destpath=destpath
        self.check_base()
        self.process()
    def process(self):
        log.info(f'EVENT: {self.event_type}  PATH: {self.sourcepath}  (DESTPATH: {self.destpath})') if not self.ignore else None
        if self.event_type=='created':
            self.create()
            self._index()
        elif self.event_type=='modified':
            self.modify()
        elif self.event_type=='delete':
            self.delete()
        elif self.event_type=='moved':
            self.moved()
            self._index()
        
        #log.debug(f'Modification queues: {MODIFIED_FILES}, TIMES: {MODIFIED_TIMES}')
        
    def create(self):
        if indexSolr.ignorefile(self.sourcepath):
            #log.debug(f'Create file ignored - filename on ignore list')
            return
        elif self.source_in_database:
            #exists already
            self.modify() #just check it's all ok
            return
            
        _collections=file_utils.find_live_collections(self.sourcepath)
        if not _collections:
            log.debug('Not in any collection - no modification of database')
            return
            
        for _collection in _collections:
            _newfile=changes.newfile(self.sourcepath,_collection)
            if _newfile:
                self.source_in_database.append(_newfile)
                log.debug(f'Created new record in Collection: \'{_collection}\' in Index: \'{_collection.core}\'')    
    
    def modify(self):
        if os.path.isdir(self.sourcepath):
            log.debug(f'Ignore directory modified')
            pass
        elif indexSolr.ignorefile(self.sourcepath):
            #log.debug(f'Modification ignored - filename on ignore list')
            pass
        elif self.source_in_database:
            #MODIFIED_TIMES[self.sourcepath]=time.time()
            for _file in self.source_in_database:
                #putting modified file in q
                #MODIFIED_FILES.setdefault(self.sourcepath,set()).add(_file.id)
                r.sadd('MODIFIED_FILES',_file.id)
                r.set(f'MODIFIED_TIME.{_file.id}',time.time())
                log.debug(f'Added: \'{_file}\' with id \'{_file.id}\' to modification queue')
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
        if indexSolr.ignorefile(self.sourcepath):
            #log.debug(f'Modification ignored - filename on ignore list')
            pass
        elif self.source_in_database:
            for _file in self.source_in_database:
                deletefiles=[_file.filepath]
                collection=_file.collection
                updateSolr.removedeleted(deletefiles,collection) #docstore= use default in user settings
        else:
            log.debug(f'File not in database - nothing to delete')
            
            
    def check_base(self):
        _database_files=file_utils.find_live_files(self.sourcepath)
        #log.debug(f'Existing files found: {_database_files}')
        
        if len(_database_files)>0:
            self.source_in_database=_database_files
        else:
            self.source_in_database=[]
        
        if self.destpath:
            _database_files=file_utils.find_live_files(self.destpath)
            if len(_database_files)>1:
                self.dest_in_database=_database_files
            else:
                self.dest_in_database=None            
    
    
    def _index(self):
        for _file in self.source_in_database:
            if not _file.indexedSuccess:
                log.debug(f'{_file} in database not indexed: try to index')
                index_file(_file)
            elif _file.indexUpdateMeta:
                log.debug(f'Now should update solr meta for {_file}')
                updateSolr.metaupdate_rawfile(_file)

def index_file(_file):
    file_utils.update_file(_file) #update filesize and last-modified in database
    extractor=indexSolr.ExtractSingleFile(_file)
    #print(extractor.__dict__)
    """options: forceretry=False,useICIJ=False,ocr=True,docstore=DOCSTORE """
    if extractor.failed==0:
        return True
    else:
        log.debug('Extraction failed')
        return False

def index_file2(_file):
    pass


def make_scan_and_index_job(collection_id,_test=0,force_retry=False,use_icij=False,ocr=True):
    job_id=f'CollectionScanAndExtract.{collection_id}'
    makejob=r.sadd('SEARCHBOX_JOBS',job_id)
    if not makejob:
        log.info('task exists already')
        return job_id
    else:
        job=f'SB_TASK.{job_id}'
        if use_icij:
            r.hset(job,'task','scan_extract_collection_force_retry_icij') if force_retry else r.hset(job,'task','scan_extract_collection_icij')
        else:
            r.hset(job,'task','scan_extract_collection_force_retry') if force_retry else r.hset(job,'task','scan_extract_collection')
        r.hset(job,'collection_id',collection_id)
        r.hset(job,'status','queued')
        r.hset(job,'ocr',1) if ocr else r.hset(job,'ocr',0)
        r.hset(job,'test',_test)
        r.hset(job,'job',job)
        return job_id


def make_index_job(collection_id,_test=0,force_retry=False,use_icij=False,ocr=True):
    job_id=f'CollectionExtract.{collection_id}'
    makejob=r.sadd('SEARCHBOX_JOBS',job_id)
    if not makejob:
        log.info('task exists already')
        return job_id
    else:
        job=f'SB_TASK.{job_id}'
        if use_icij:
            r.hset(job,'task','extract_collection_force_retry_icij') if force_retry else r.hset(job,'task','extract_collection_icij')
        else:
            r.hset(job,'task','extract_collection_force_retry') if force_retry else r.hset(job,'task','extract_collection')
        r.hset(job,'collection_id',collection_id)
        r.hset(job,'status','queued')
        r.hset(job,'ocr',1) if ocr else r.hset(job,'ocr',0)
        r.hset(job,'test',_test)
        r.hset(job,'job',job)
        r.hmset(job,{'show_taskbar':1,'progress':0,'progress_str':"",'target_count':"",'counter':"",'skipped':"",'failed':"",'failed_list':""})
        return job_id

def make_scan_job(collection_id,_test=0):
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
        r.hset(job,'job',job)
        r.hmset(job,{'show_taskbar':1,'progress':0,'progress_str':"",'target_count':"",'moved':"",'new':"",'deleted':"",'unchanged':""})
        return job_id

def make_dupscan_job(folder,label,_test=0):
    job_id=f"DupScan.{label}"
    makejob=r.sadd('SEARCHBOX_JOBS',job_id)
    if not makejob:
        log.info('task exists already ... resetting')
        
        
        #return job_id
    if True:
        job=f'SB_TASK.{job_id}'
        r.hset(job,'task','dupscan')
        r.hset(job,'label',label)
        r.hset(job,'folder',folder)
        r.hset(job,'status','queued')
        r.hset(job,'test',_test)
        r.hset(job,'job',job)
        r.hmset(job,{'show_taskbar':1,'progress':0,'progress_str':"",'total_folders':"",'total_scanned':"",'new':"",'deleted':"",'unchanged':""})
        return job_id
        
def get_extract_results(job):
    return r.hgetall(job)
    
def task_check():
    job_ids=r.smembers('SEARCHBOX_JOBS')
    for job_id in job_ids:
        task_dispatch(job_id)

def task_dispatch(job_id):
    job=f'SB_TASK.{job_id}'
    try:
        if r.exists(job):
            log.debug(f'Processing {job}')
            task=r.hget(job,'task')
            log.debug(f'Task found {task}')
            if task[:18]=='extract_collection':
                #expecting: 'extract_collection' or 'extract_collection_force_retry' or 'extract_collection_icij' or 'extract_collection_force_retry_icij'
                try:
                    index_job(job_id,job,task)
                except:
                    pass
            elif task=='scan_collection':
                scan_job(job_id,job,task)
            elif task=='scan_extract_collection' or task=='scan_extract_collection_force_retry' or task=='scan_extract_collection_icij' or task=='scan_extract_collection_force_retry_icij':
                #DEBUG
                scan_extract_job(job_id,job,task)                    
            elif task=='dupscan':
                dupscan_job(job_id,job,task)
            else:
                log.info(f'no task defined .. killing job')
                r.delete(job)
                r.srem('SEARCHBOX_JOBS',job_id)
            return True
        else:
            log.info(f'Job \"{job_id}\" does not exist in queue')
            r.srem('SEARCHBOX_JOBS',job_id)
            return False
    except:
        log.info('Exception in searchbox task: removing job')
        r.srem('SEARCHBOX_JOBS',job_id)
        raise

def scan_extract_job(job_id,job,task):
    sub_job_id=r.hget(job,'sub_job_id')
    sub_job='SB_TASK.'+sub_job_id if sub_job_id else None
    status=r.hget(job,'status')
    ocr=0 if r.hget(job,'ocr')==0 else 1
    collection_id=r.hget(job,'collection_id')
    force_retry = True if 'force_retry' in task else False
    use_icij = True if 'icij' in task else False
    log.debug(f'ocr: {ocr}, force_retry: {force_retry}, icij {use_icij}, sub_id: {sub_job}')
    if status=='queued':
        log.info('making scan job')
        sub_job_id=make_scan_job(collection_id,_test=0)
        r.hset(job,'status','scanning')
        if sub_job_id:
            r.hset(job,'sub_job_id',sub_job_id)
    elif status=='scan_complete':
        pass
    elif status =='scanning' and not sub_job:
         log.info('no active sub-job put back in queue')
         r.hset(job,'status','queued')
    elif status=='scanning':
        sub_status=r.hget(sub_job,'status')
        if sub_status =='completed':
            log.debug('now index')   
            sub_job_id=make_index_job(collection_id,_test=0,force_retry=False,use_icij=False,ocr=1)
            r.hset(job,'status','indexing')
            r.hset(job,'sub_job_id',sub_job_id)
        else:
            log.debug('still scanning')
    elif status=='indexing':
        sub_status=r.hget(sub_job,'status')
        if sub_status =='completed':
            r.hset(job,'status','completed')
            r.srem('SEARCHBOX_JOBS',job_id)
            r.sadd('SEARCHBOX_JOBS_DONE',job_id)
            log.debug('scan and index complete')
        elif sub_status =='error':
            r.hset(job,'status','completed')
            r.srem('SEARCHBOX_JOBS',job_id)
            r.sadd('SEARCHBOX_JOBS_DONE',job_id)
            log.debug('scan and index shutdown on error')
        else:
            log.debug('still indexing')
    else: 
        pass   


def scan_job(job_id,job,task):
    collection_id=r.hget(job,'collection_id')
    log.info(f'scanning collection {collection_id}')
    scan_collection_id(job,collection_id)
    r.srem('SEARCHBOX_JOBS',job_id)
    r.sadd('SEARCHBOX_JOBS_DONE',job_id)
    
def dupscan_job(job_id,job,task):
    folder=r.hget(job,'folder')
    label=r.hget(job,'label')
    r.hset(job,'status','scanning')
    log.info(f'scanning folder {folder}')
    dupscan_process(job,folder,label)
    log.debug(f'completed scanning {job_id}')
    r.srem('SEARCHBOX_JOBS',job_id)
    r.sadd('SEARCHBOX_JOBS_DONE',job_id)

def dupscan_process(job,folder,label):
    _index=dupscan_folder(job,folder,label=label)
    r.hset(job,'status','completed')
    if _index:
        r.hmset(job,{
        'total':_index.total,
        'new':_index.newfiles,
        'deleted':_index.deleted_files_count,
        'moved':"",
        'unchanged':"",
        'changed':_index.changed_files_count
        })


def index_job(job_id,job,task):
    ocr_raw=r.hget(job,'ocr')
    ocr=False if ocr_raw==0 else True
    useICIJ= True if task[-5:]=='_icij' else False
    forceretry=True if 'force_retry' in task else False
    collection_id=r.hget(job,'collection_id')
    r.hset(job,'status','started')
    _test=True if r.hget(job,'test')=='True' else False
    log.info('This is a test') if _test else None
    log.info(f'indexing collection {collection_id}')

    try:
        index_collection_id(job,collection_id,_test,useICIJ=useICIJ,ocr=ocr,forceretry=forceretry)
    except updateSolr.s.SolrConnectionError as e:
        log.error(f'Solr Connection Error: {e}')
        r.hset(job,'status','error')
        r.hset(job,'message','Solr connection error')
        raise
    except updateSolr.s.MissingConfigData as e:
        log.error(f'Missing Config Data: {e}')
        r.hset(job,'status','error')
        r.hset(job,'message','Missing config data')
#    except Exception as e:
#        log.error(f'Error: {e}')
#        r.hset(job,'status','error')
#        r.hset(job,'message','Unknown error')
#        raise
#                results=r.hgetall(job)
#                log.info(results)
    except Exception as e:
        log.error(e)
        r.hset(job,'status','error')
        r.hset(job,'message','Unknown error - see trace')
        exc_type, exc_value, exc_traceback = sys.exc_info()
        traceback.print_exc(limit=2, file=sys.stdout)
        raise
    finally:
        r.srem('SEARCHBOX_JOBS',job_id)
        log.info(f'Removed job {job_id}')
        r.sadd('SEARCHBOX_JOBS_DONE',job_id)
   
    

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

def dupscan_folder(job,folder_path,label=None):
    try:
        _index=file_utils.sql_dupscan(folder_path,label=label,job=job)
        return _index
    except Exception as e:
        log.error(f'Error scanning {e}')
        r.hset(job,{'message':'Scan Error','progress_str':'Scan terminated'})
        
        return None
    

def collection_from_id(collection_id):
    _collection=Collection.objects.get(id=int(collection_id))
    _mycore=indexSolr.s.core_from_collection(_collection)
    return _collection,_mycore

def index_collection_id(job,collection_id,_test=False,forceretry=False,useICIJ=False,ocr=True):
    try:
        _collection,_mycore=collection_from_id(collection_id)
        ext=index_collection(_collection,_mycore,_test=_test,job=job,forceretry=forceretry,useICIJ=useICIJ,ocr=ocr)
        r.hset(job,'status','completed')
        r.hset(job,'working_file','')
        #if ext:
        #    r.hmset(job,{'counter':ext.counter,'skipped':ext.skipped,'failed':ext.failed,'failed_list':ext.failedlist})
        r.srem('COLLECTIONS_TO_INDEX',collection_id)
    except Collection.DoesNotExist:
        log.info(f'Collection id {collection_id} not valid ... deleting')
        r.hset(job,'status','error')
        r.hset(job,'message','collection not valid')
        r.srem('COLLECTIONS_TO_INDEX',collection_id)
                
def index_collection(thiscollection,mycore,_test=False,job=None,forceretry=False,useICIJ=False,ocr=True):
    assert isinstance(thiscollection,Collection)
    assert isinstance(mycore,indexSolr.s.SolrCore)
    log.info(f'extracting {thiscollection} in {mycore}')
    ext=indexSolr.Extractor(thiscollection,mycore,job=job,forceretry=forceretry,useICIJ=useICIJ,ocr=ocr) if not _test else None #GO INDEX THE DOCS IN SOLR
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
            #log.debug(f'Checking: File:{_file} Modified: {int(_now-_modtime)} seconds ago')
            if _now-_modtime>time_before_check:
                log.debug('needs update check')
                result=update_file(_file)
                log.info(f'{_file} updated: {result}')
                #remove checked files:
                r.srem('MODIFIED_FILES',_fileid)
                r.delete(f'MODIFIED_TIME.{_file.id}')                
        except File.DoesNotExist:
            log.info(f'{_fileid} not found .. removing from MODIFIED_FILES')
            r.srem('MODIFIED_FILES',_fileid)

def update_file(_file):
    if file_utils.changed_file(_file):
        log.info(f'This file \"{_file}\"needs updating')
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

HBEAT=HeartBeat()


#if __name__ == "__main__":
#    path = sys.argv[1] if len(sys.argv) > 1 else '.'
    
    
#    event_handler = LoggingEventHandler()



