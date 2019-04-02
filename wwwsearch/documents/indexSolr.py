# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from __future__ import print_function
#from bs4 import BeautifulSoup as BS
from django.conf import settings
import requests, os, logging, json, urllib, re
import ownsearch.hashScan as dup
import hashlib  #routines for calculating hash
from .models import Collection,File,Index
log = logging.getLogger('ownsearch.indexsolr')
from configs import config
from ownsearch.solrJson import SolrConnectionError
from ownsearch.solrJson import SolrCoreNotFound
from documents.updateSolr import scandocs,delete,updatetags,check_hash_in_solrdata,check_file_in_solrdata,remove_filepath_or_delete_solrrecord,makejson,update as update_meta,get_source,get_collection_source,check_paths,clear_date
from ownsearch import solrJson as s
from fnmatch import fnmatch
from . import solrICIJ,file_utils,changes,time_utils
from .file_utils import make_relpath
try:
    from urllib.parse import quote #python3
except ImportError:
    from urllib import quote #python2
import time
from .redis_cache import redis_connection as r

#from watcher import watch_dispatch2 as watch_dispatch


try:
    IGNORELIST=config['Solr']['ignore_list'].split(',')
    DOCSTORE=config['Models']['collectionbasepath'] #get base path of the docstore
    TIMEOUT=int(config['Solr']['solrtimeout'])
    MAXSIZE_MB=int(config['Solr']['maxsize'])
    
except Exception as e:
    log.warning('Some missing configuration options; using defaults')
    IGNORELIST=[]
    TIMEOUT=120
    MAXSIZE_MB=5 #MB

MAXSIZE=MAXSIZE_MB*(1024**2)

"""
EXTRACT CONTENTS OF A FILE FROM LOCAL MEDIA INTO SOLR INDEX

main method is extract(path,contentsHash,mycore,test=False)
"""

class BadParameters(Exception):
    pass

class ExtractInterruption(Exception):
    pass

class PostFailure(Exception):
    pass
    
class DuplicateRecords(Exception):
    pass


class ExtractFolder():
    def __init__(self,corename,path='',collection='',collectionID='',job=None,ocr=False,docstore=DOCSTORE):
        
        self.job=job
        self.ocr=ocr
        self.docstore=docstore
        try:
            self._index=Index.objects.get(corename=corename)
            self.mycore=s.SolrCore(corename)
        except Exception as e:
            log.error(e)
            raise BadParameters("Bad specs for Collection")
        
        if collection:
             if not isinstance(collection,Collection):
                 raise BadParameters("Bad specs for Collection")
             else:
                 self.collection=collection
        elif collectionID:
            try:
                self.collection=Collection.objects.get(id=collectionID)
                assert isinstance(self.collection,Collection)
            except Exception as e:
                log.error(e)
                raise BadParameters("Bad specs for Collection")
        elif path:
            try:
                self.collection=Collection.objects.filter(path=path,core_id=self._index.id)[0]
                assert isinstance(self.collection,Collection)
            except Exception as e:
                log.error(e)
                raise BadParameters("Bad specs for Collection")
        else:
            raise BadParameters("No Collection defined")
        
        try:
            self._path=self.collection.path
            assert os.path.exists(self._path)
        except Exception as e:
            raise BadParameters("Collection filepath does not exist")
        
        self.process()
        

    def process(self):
        #scan the collection
        log.info(f"Scanning collection {self.collection}")
        scanner=scandocs(self.collection,job=self.job)
        
        #extract the files to the index
        ext=solrICIJ.ICIJExtractor(self._path,self.mycore,ocr=self.ocr)
        log.info(f'Extracted folder success: {ext.result}')
        
        #now fix meta
        Collection_Post_Processor(self.collection,self.mycore,docstore=self.docstore,_test=False,job=self.job)

        

class Extractor():
    """extract a collection of docs into solr"""
    def __init__(self,collection,mycore,forceretry=False,useICIJ=False,ocr=True,docstore=DOCSTORE,job=None):
        
        if not isinstance(mycore,s.SolrCore) or not isinstance(collection,Collection):
            raise BadParameters("Bad parameters for extraction")
        self.collection=collection
        self.mycore=mycore
        self.forceretry=forceretry
        self.useICIJ=useICIJ
        self.ocr=ocr
        self.docstore=docstore
        self.job=job
        self.counter,self.skipped,self.failed=0,0,0
        self.skippedlist,self.failedlist=[],[]
        self.filelist=File.objects.filter(collection=collection)
        self.target_count=len(self.filelist)
        self.update_extract_results()
        self.update_working_file('')
        try:
            self.extract()
        finally:
            self.update_extract_results()
            self.update_working_file('')
    
    
    def extract_file(self,file):
        
        if self.skip_file(file):
            pass
            #log.debug('Skipping {}'.format(file))
        else:
            log.info('Attempting index of {}'.format(file.filepath))
            self.update_working_file(file.filepath)

            #if was previously indexed, store old solr ID and then delete if new index successful
            oldsolrid=file.solrid
            #get source
            sourcetext=get_source(file)
                            
            
            if file.is_folder:
                log.debug('detected folder path')
                result=self.extract_folder(file)
                
            else:
                #getfile hash if not already done
                if not file.hash_contents:
                    file.hash_contents=file_utils.get_contents_hash(file.filepath)
                    file.save()
                
                
                #check by hash of contents if doc exists already in solr index
                existing_doc=check_file_in_solrdata(file,self.mycore) #searches by hashcontents, not solrid
                if existing_doc:
                    #FIX META ONLY
                    result=self.update_existing_meta(file,existing_doc)

                else:
                #now try the extract
                    file.indexedTry=True  #set flag to say we've tried
                    file.save()
                    if self.useICIJ:
                        log.info('using ICIJ extract method..')
                        ext = solrICIJ.ICIJExtractor(file.filepath,self.mycore,ocr=self.ocr)
                        result=ext.result
                        file.error_message=ext.error_message
                        if result is True:
                            try:
                                new_id=s.hashlookup(file.hash_contents,self.mycore).results[0].id #id of the first result returned
                                file.solrid=new_id
                                file.save()
                                log.info(f'(ICIJ extract) New solr ID: {new_id}')
                            except:
                                log.warning('Extracted doc not found in index')
                                file.error_message='Indexed, but not found in index'
                                result=False
                        if result is True:
                        #post extract process -- add meta data field to solr doc, e.g. source field
                            try:
                                sourcetext=file.collection.source.sourceDisplayName
                            except:
                                sourcetext=''

                            try:
                                ext=ICIJ_Post_Processor(file.filepath,self.mycore,hash_contents=file.solrid, sourcetext=sourcetext,docstore=self.docstore,test=False)
                            except Exception as e:
                                log.error(f'Cannot add meta data to solrdoc: {new_id}, error: {e}')
                            
                    else:
                        try:
                            extractor=ExtractFile(file.filepath,self.mycore,hash_contents=file.hash_contents,sourcetext=sourcetext,docstore=self.docstore,test=False,ocr=self.ocr)
                            result=extractor.result
                            if result:
                                extractor.post_process()
                                result=extractor.post_result
                            else:
                                file.error_message=extractor.error_message
                        except (s.SolrCoreNotFound,s.SolrConnectionError,requests.exceptions.RequestException) as e:
                            raise ExtractInterruption(self.interrupt_message())
         
            if result is True:
                self.counter+=1
                #print ('PATH :'+file.filepath+' indexed successfully')
                    
                if not self.useICIJ and not file.is_folder:
                    file.solrid=file.hash_contents  #extract uses hashcontents for an id , so add it
                
                file.indexedSuccess=True
                file.error_message=''
                #now delete previous solr doc of moved file(if any): THIS IS ONLY NECESSARY IF ID CHANGES  
                log.info('Old ID: '+oldsolrid+' New ID: '+file.solrid)
                
                if oldsolrid and oldsolrid!=file.solrid:
                    log.info('now delete or update old solr doc'+str(oldsolrid))
                    relpath=make_relpath(file.filepath,docstore=self.docstore)
                    remove_filepath_or_delete_solrrecord(oldsolrid,relpath,self.mycore)
            else:
                log.info(f'Indexing fail: PATH \'{file.filepath}\]\' with ERROR:{file.error_message}')
                self.failed+=1
                self.failedlist.append((file.filepath,file.error_message))
            file.save()
        if self.job and r:
            self.update_extract_results()
                
                
    def extract(self):
        #main loop
        for _file in self.filelist:
            try:
                self.extract_file(_file)
            except Exception as e:
                log.info(f'PATH : {_file.filepath} indexing failed, with exception {e}')
                _file.indexedTry=True  #set flag to say we've tried
                _file.save()
                raise e

    def update_existing_meta(self,file,existing_doc):
        """update meta of existing solr doc"""
        result=True
        file.solrid=existing_doc.id
        log.debug('Existing docpath: {}'.format(existing_doc.data.get('docpath')))
        log.debug('Existing parent path hashes: {}'.format(existing_doc.data.get(self.mycore.parenthashfield)))
        log.debug(f'Existing source: {existing_doc.data.get(self.mycore.sourcefield)}')
        
        
        
        #add a source if no source
        solr_source=existing_doc.data.get(self.mycore.sourcefield)
        if not solr_source:
            file_source=get_source(file)
            if file_source:
                log.debug(f'Adding missing source {file_source}')
                result=updatetags(file.solrid,self.mycore,value=file_source,field_to_update='sourcefield',newfield=False,test=False)
                if not result:
                    log.error('Failed to add source field')
        
        if file.content_date: #only modify date if date from path changes
            date_from_path=time_utils.timestringGMT(file.content_date)
            log.debug(f'Existing date: {existing_doc.date}')
            log.debug(f'Date from path {date_from_path}')
            if existing_doc.date != date_from_path:
                log.debug('Date from path altered; update in index')
                if not clear_date(file.solrid,self.mycore):
                    log.error('Failed to clear previous date')
                result=updatetags(file.solrid,self.mycore,value=date_from_path,field_to_update='datesourcefield',newfield=False,test=False)
                if not result:
                    log.error('Failed in updating date from path')
            else:
                log.debug('Date from path unchanged')

        #check paths
        paths_are_missing,paths,parent_hashes=check_paths(existing_doc,file,self.mycore,docstore=self.docstore)
        if paths_are_missing:
            log.debug('Updating doc \"{}\" to append the old and new filepath {} to make {}'.format(file.solrid,file.filepath,paths))
            result=updatetags(file.solrid,self.mycore,field_to_update='docpath',value=paths)
            if result:
                result=updatetags(file.solrid,self.mycore,field_to_update=self.mycore.parenthashfield,value=parent_hashes)
        
        if existing_doc.docname != file.filename:
            log.debug(f'Existing filename {existing_doc.docname} to replace with {file.filename}')
            result=updatetags(file.solrid,self.mycore,field_to_update=self.mycore.docnamesourcefield,value=file.filename)
        
        file.save()
        
#        changes.append((self.mycore.docnamesourcefield,'docname',self.filename))
#        #extract a relative path from the docstore root
#        
        
        
        
        return result
       
    def skip_file(self,file):
        if file.indexedSuccess:
            pass
            file.error_message='Already indexed'
            #skip this file: it's already indexed
        elif file.indexedTry and not self.forceretry:
            #skip this file, tried before and not forcing retry
            file.error_message='Previous failure'
            log.info(f'Skipped {file.error_message} path: {file.filename}')
        elif ignorefile(file.filepath):
            #skip this file because it is on ignore list
            file.error_message='On ignore list'
            log.info(f'Skipped {file.error_message} path: {file.filename}')
        elif file.filesize>MAXSIZE:
            #skip the extract, it's too big
            file.error_message=f'Too large {file.filesize}b'
            log.info(f'Skipped {file.error_message} path: {file.filename}')
        elif file.filesize<3:
            #skip , it's empty
            file.error_message=f'Skipped. Empty file: {file.filesize}bytes'
            log.info(f'Skipped {file.error_message} path: {file.filename}')
        else:
            #don't skip
            return False
        self.skipped+=1
        
        relpath=os.path.relpath(file.filepath,self.collection.path)
        self.skippedlist.append((relpath, file.error_message))
        return True

    def interrupt_message(self):
        return '{} files extracted, {} files skipped and {} files failed.'.format(self.counter,self.skipped,self.failed)
        
    def extract_folder(self,file):
        
        solrid=file.hash_filename
        log.info('Adding (meta-only) folder name to index')
           #extract a relative path from the docstore root
        relpath=make_relpath(file.filepath,docstore=self.docstore)
        #args+='&literal.{}={}&literal.{}={}'.format(filepathfield,relpath,pathhashfield,file_utils.pathHash(path))
        result=updatetags(solrid,self.mycore,field_to_update='docpath',value=[relpath])
        if result:
            file.solrid=solrid
            #add hash of parent relative path
            if self.mycore.parenthashfield:
                parenthash=file_utils.parent_hash(relpath)
                #args+='&literal.{}={}'.format(parenthashfield,parenthash)
                log.debug("Parenthash: {} Relpath: {}".format(parenthash,relpath))
                result=updatetags(solrid,self.mycore,field_to_update=self.mycore.parenthashfield,value=parenthash)
            else:
                log.debug('no parenthashfield')
                result=False    
            
            if result:
                result=updatetags(solrid,self.mycore,field_to_update=self.mycore.docnamesourcefield,value='Folder: {}'.format(file.filename))
        return result
    #REDIS UPDATES
    
    def update_working_file(self,_filename):
        if self.job:
            r.hset(self.job,'working_file',_filename)
            
    
    def update_extract_results(self):
        if self.job:
            processed=self.counter+self.skipped+self.failed
            try:
                progress=f'{((processed/self.target_count)*100):.0f}'
            except ZeroDivisionError:
                progress=f'100'
            progress_str=f"{processed} of {self.target_count} files" #0- replace 0 for decimal places
            #log.debug(f'Progress: {progress_str}')
            #log.debug(self.failedlist)
            failed_json=json.dumps(self.failedlist)
            #log.debug(failed_json)
            r.hmset(self.job,{'progress':progress,'progress_str':progress_str,'target_count':self.target_count,'counter':self.counter,'skipped':self.skipped,'failed':self.failed,
            	'path':self.collection.path,
            	'failed_list': failed_json, 
            	'skipped_list':json.dumps(self.skippedlist)
            		})

class UpdateMeta(Extractor):
    def __init__(self,mycore,file,existing_doc,docstore=DOCSTORE):
        if not isinstance(mycore,s.SolrCore):
            raise BadParameters("Bad parameters for extraction")
        self.mycore=mycore
        self.docstore=docstore
        self.update_existing_meta(file,existing_doc)   


class ExtractSingleFile(Extractor):
    """extract a single doc into solr"""
    def __init__(self,_file,forceretry=False,useICIJ=False,ocr=True,docstore=DOCSTORE,job=None):        
        cores=s.getcores() #fetch dictionary of installed solr indexes (cores)
        self.mycore=cores[_file.collection.core.id]
        self.collection=_file.collection
        if not isinstance(self.mycore,s.SolrCore) or not isinstance(self.collection,Collection):
            raise BadParameters("Bad parameters for extraction")
        self.forceretry=forceretry
        self.useICIJ=useICIJ
        self.ocr=ocr
        self.job=None
        self.docstore=docstore
        self.counter,self.skipped,self.failed=0,0,0
        self.skippedlist,self.failedlist=[],[]
        self.filelist=[_file]
        self.extract()


class ChildProcessor():
    def __init__(self,path,mycore,hash_contents='',sourcetext='',docstore=''):
        self.path=path
        self.mycore=mycore
        self.sourcetext=sourcetext
        self.hash_contents = hash_contents if hash_contents else file_utils.get_contents_hash(self.path)
        specs=file_utils.FileSpecs(path,scan_contents=False)###
        self.docstore=docstore

    def process_children(self):
        
        result=True
        solr_result=s.hashlookup(self.hash_contents, self.mycore,children=True)
        for solrdoc in solr_result.results:
        #add source info to the extracted document
            log.debug(solrdoc.__dict__)
            _path=solrdoc.data.get('docpath')[0]
            date_from_path=None
            

            if not solrdoc.docname: #no stored filename
                filename=solrdoc.data[self.mycore.docnamesourcefield2]
                if filename:
                    date_from_path=file_utils.FileSpecs(filename,scan_contents=False).date_from_path
                    result=updatetags(solrdoc.id,self.mycore,value=filename,field_to_update='docnamefield',newfield=False)
                    if result:
                        log.debug(f'added filename \'{filename}\' to child doc')
                    else:
                        log.debug(f'failed to add filename \'{filename}\' to child doc')
                        return False
            if self.sourcetext:
                try:
                    result=updatetags(solrdoc.id,self.mycore,value=self.sourcetext,field_to_update='sourcefield',newfield=False)
                    if result==True:
                        log.info('Added source \"{}\" to child-document \"{}\", id {}'.format(self.sourcetext,solrdoc.docname,solrdoc.id))
                    else:
                        log.error('Failed to add source to child document id: {}'.format(solrdoc.id))
                        return False
                except Exception as e:
                    log.error(e)
                    return False
            
                    
            changes=[]
            #check_the_date
            parsed_date=self.parse_date(solrdoc.id,None,date_from_path)
            changes.append((self.mycore.datesourcefield,'date',parsed_date)) if parsed_date else None
            
            file_size=s.getfield(solrdoc.id,'file_size',self.mycore)
            if file_size:
                size=re.match(r"\d+",file_size)[0]
                log.debug(f'Size parsed: {size}')
                changes.append((self.mycore.docsizesourcefield1,'solrdocsize',size)) if size else None
            
            #extract a relative path from the docstore root
            _relpath=make_relpath(_path,docstore=self.docstore) if _path else None
            log.debug(_relpath)
            if _relpath:
                changes.append((self.mycore.docpath,'docpath',_relpath))
                if self.mycore.parenthashfield:
                    parenthash=file_utils.parent_hash(_relpath)
                    changes.append((self.mycore.parenthashfield,self.mycore.parenthashfield,parenthash))
            if changes:
                log.debug(changes)
                response,updatestatus=update_meta(solrdoc.id,changes,self.mycore)
                if not updatestatus:
                    return False
        return True
    def parse_date(self,solrid,last_modified,date_from_path):
        """evaluate the best display date from alternative sources"""
        #in order of priority: 
        #1. take the date from the filename
        if date_from_path:
            if not clear_date(solrid,self.mycore):
                log.error('Failed to clear previous date')
                return None
            return time_utils.timestringGMT(date_from_path)

        #2. else if no date stored in date sourcefield .. try the other sourcefield
        elif not s.getfield(solrid,self.mycore.datesourcefield,self.mycore):
            #3. or date from cleaned-up second source field
            altdate=time_utils.cleaned_ISOtimestring(s.getfield(solrid,self.mycore.datesourcefield2,self.mycore))
            if altdate:
                return altdate
            #4. or date from file's last-modified stamp
            elif last_modified:
                return time_utils.ISOtimestring(last_modified)
            else:
                return None
        else:
            return None
  


class ExtractFile(ChildProcessor):
    def __init__(self,path,mycore,hash_contents='',sourcetext='',docstore='',test=False,ocr=True):
        self.path=path
        self.ocr=ocr
        specs=file_utils.FileSpecs(path,scan_contents=False)###
        self.filename=specs.name
        self.size=specs.length
        self.date_from_path,self.last_modified=changes.parse_date(specs)
        self.mycore=mycore
        self.test=test
        self.sourcetext=sourcetext
        self.docstore=docstore
        self.hash_contents = hash_contents if hash_contents else file_utils.get_contents_hash(path)
        self.solrid=self.hash_contents
        self.result,self.error_message=extract(self.path,self.hash_contents,self.mycore,timeout=TIMEOUT,docstore=docstore,test=self.test,sourcetext=self.sourcetext,ocr=self.ocr)
        log.debug(self.result)
        
        
    def post_process(self):
        changes=[]
        changes.append((self.mycore.docnamesourcefield,'docname',self.filename))
        #extract a relative path from the docstore root
        relpath=make_relpath(self.path,docstore=self.docstore)
        changes.append((self.mycore.docpath,'docpath',relpath))
        

        
        parsed_date=self.parse_date(self.solrid,self.last_modified,self.date_from_path)
        log.debug(f'parsed date: {parsed_date}')
        changes.append((self.mycore.datesourcefield,'date',parsed_date)) if parsed_date else None
        
        
        #pick up alternate filesize, else use docsize
        parsed_filesize=self.parse_filesize()
        changes.append((self.mycore.docsizesourcefield1,'solrdocsize',parsed_filesize)) if parsed_filesize else None

        
        #if sourcefield is defined and sourcetext is not empty string, add that to the arguments
        #make the sourcetext args safe, for example inserting %20 for spaces 
        if self.mycore.sourcefield and self.sourcetext:
            changes.append((self.mycore.sourcefield,self.mycore.sourcefield,self.sourcetext))

        #add hash of parent relative path
        if self.mycore.parenthashfield:
            parenthash=file_utils.parent_hash(relpath)
            changes.append((self.mycore.parenthashfield,self.mycore.parenthashfield,parenthash))

        log.debug(f'CHANGES: {changes}')
        
        response,updatestatus=update_meta(self.solrid,changes,self.mycore)
        log.debug(response)
        
        self.post_result=updatestatus
        #log.debug(jsondata)
        self.process_children()
    
    def parse_filesize(self):
        #filesize picked up automatically into 'stream_size' field in standard extract handler
        return None
        

    
  



class ICIJ_Post_Processor(ExtractFile):
    def __init__(self,path,mycore,hash_contents='',sourcetext='',docstore='',test=False):
        self.path=path
        specs=file_utils.FileSpecs(path,scan_contents=False)###
        self.filename=specs.name
        self.docstore=docstore
        self.sourcetext=sourcetext
        self.date_from_path,self.last_modified=changes.parse_date(specs)
        self.mycore=mycore
        self.test=test
        self.hash_contents = hash_contents if hash_contents else file_utils.get_contents_hash(path)
        self.solrid=self.hash_contents
        self.post_process()

    def parse_filesize(self):
        file_size=s.getfield(self.solrid,self.mycore.docsizesourcefield2,self.mycore)
        return file_size if file_size else self.length
        

class Collection_Post_Processor(Extractor):
    def __init__(self,collection,mycore,docstore=DOCSTORE,_test=False,job=None):
        """check meta in solr index for collection"""
        #forceretry=False,useICIJ=False,ocr=True,docstore=DOCSTORE,job=None):        
        if not isinstance(mycore,s.SolrCore) or not isinstance(collection,Collection):
            raise BadParameters("Bad parameters for extraction")
        self.collection=collection
        self.mycore=mycore
        self.docstore=docstore
        self.job=job
        self._test=_test
        self.sourcetext=get_collection_source(self.collection)
#        self.counter,self.skipped,self.failed=0,0,0
#        self.skippedlist,self.failedlist=[],[]
        self.filelist=File.objects.filter(collection=collection)
        try:
            self.loop()
        finally:
            pass
    
    def loop(self):
        for _file in self.filelist:
            _file.indexedTry=True
            if _file.is_folder:
                #add folder to the index:
                log.debug('Adding folder to index')
                _file.indexedSuccess=True if self.extract_folder(_file) else False
                _file.save()
            else:
                if self.skip_file(_file):
                    existing_doc=check_file_in_solrdata(_file,self.mycore) #searches by hashcontents, not solrid
                    if existing_doc:
                        log.info(f'deleting file {_file} on skip list')
                        delete(existing_doc.id,self.mycore)
                else:
                    existing_doc=check_file_in_solrdata(_file,self.mycore) #searches by hashcontents, not solrid
                    if existing_doc:
                    #FIX META ONLY
                        result=self.update_existing_meta(_file,existing_doc)
                        c=ChildProcessor(_file.filepath,self.mycore,hash_contents=_file.hash_contents,sourcetext=self.sourcetext,docstore=self.docstore)
                        c.process_children()
                        _file.solrid=_file.hash_contents
                        _file.indexedSuccess=True
                        _file.save()
                    else:
                        log.debug(f'File not found in solr index: {_file}')
                        _file.indexedSuccess=False
                        _file.save()

    def skip_file(self,_file):
        if ignorefile(_file.filepath):
            #skip this file because it is on ignore list
            return True
        else:
            return False
    
#SOLR METHODS

def extract_test(test=True,timeout=TIMEOUT,mycore='',docstore='',ocr=True,path=''):
    #get path to test file
    if not path:
        path=settings.BASE_DIR+'/tests/testdocs/testfile/TESTFILE_BBCNews1.pdf'
    assert os.path.exists(path)
    
    #get hash
    hash=dup.hashfile256(path)
    #print(hash)
    
    if not mycore:
        #get default index
        mycore=s.SolrCore('tests_only')
        
    #checks solr index is alive
    log.debug('Testing extract to {}'.format(mycore.name))
    mycore.ping()
    
    result,error_message=extract(path,hash,mycore,test=test,timeout=TIMEOUT,docstore=docstore,ocr=ocr)
    return result

def extract(path,contentsHash,mycore,test=False,timeout=TIMEOUT,sourcetext='',docstore='',ocr=True):
    """extract a path to solr index (mycore), storing hash of contents, optional testrun, timeout); throws exception if no connection to solr index, otherwise failures return False"""
    
    message=''
    try:
        assert isinstance(mycore,s.SolrCore)
        assert os.path.exists(path) #check file exists
    except AssertionError:
        log.debug ('Extract: bad parameters: {},{}'.format(path,mycore))
        return False
    #establish connnection to solr index
    mycore.ping() #       throws a SolrConnectionError if solr is down; throw error to higher level.

    if contentsHash =='':
        contentsHash=file_utils.get_contents_hash(path)    

    try:
        docnamesourcefield=mycore.docnamesourcefield
        hashcontentsfield=mycore.hashcontentsfield
        filepathfield=mycore.docpath

        id_field=mycore.unique_id
        pathhashfield=mycore.pathhashfield
        parenthashfield=mycore.parenthashfield

    except AttributeError as e:
        log.error('Exception: {}'.format(e))
        log.error('Solr index is missing default fields')
        return False
#    extracturl=mycore.url+'/update/extract?'
    extractargs='commit=true&wt=json'
    args='{}&literal.{}={}'.format(extractargs,id_field,contentsHash)
    
    #extract a relative path from the docstore root
    relpath=make_relpath(path,docstore=docstore)

    args+='&literal.{}={}'.format(pathhashfield,file_utils.pathHash(path))

    #if a different field for hashcontents other than the unique ID (key) then store also in that field
    if id_field != hashcontentsfield:
        args+='&literal.{}={}'.format(hashcontentsfield,contentsHash)


    log.debug('extract args: {}, path: {}, solr core: {}'.format(args,path,mycore))
        
    if test==True:
        args +='&extractOnly=true' #does not index on test
        log.debug('Testing extract args: {}, path: {}, mycore {}'.format(args,path,mycore))
        
    try:
        result,elapsed=postSolr(args,path,mycore,timeout=timeout,ocr=ocr) #POST TO THE INDEX (returns True on success)
        if result:
            log.info(f'Indexing succeeded in {elapsed:.2f} seconds with OCR={ocr}')
            return True,None
        else:
            log.warning('Error in indexing file using args: {} and path: {}'.format(args,path))
            log.warning('Indexing FAILED')
            message='Unknown failure'
    except s.SolrTimeOut as e:
        message='Solr post timeout'
        log.warning(message)
    except s.Solr404 as e:
        message='404 Error: solr URL not working: {}'.format(e)
        log.error(message)
    except s.PostFailure as e:
        message='Failed to post file: {}'.format(e)
        log.warning(message)
    return False,message


def postSolr(args,path,mycore,timeout=1,ocr=True):
    if ocr:
        extracturl=mycore.url+'/update/extract?'
    else:
        extracturl=mycore.url+'/update/extract_no_ocr?'
    
    url=extracturl+args
    log.debug('POSTURL: {}  TIMEOUT: {}'.format(url,timeout))
    log.debug('Types posturl: {} path: {}'.format(type(url),type(timeout)))
    if True:
        res=s.resPostfile(url,path,timeout=timeout) #timeout=
#        log.debug('Returned json: {} type: {}'.format(res._content,type(res._content)))
        log.debug('Response header:{}'.format(res.json()['responseHeader']))
#        log.debug(res.__dict__)
        
        solrstatus=res.json()['responseHeader']['status']
        #log.debug(res.elapsed.total_seconds())
        solrelapsed=res.elapsed.total_seconds()
    log.debug('SOLR STATUS: {}  ELAPSED TIME: {:.2f} secs'.format(solrstatus,solrelapsed))
    if solrstatus==0:
        return True,solrelapsed 
    else:
        return False,0


"""UTILITIES:"""

def ignorefile(path):
    """check if filepath fits an ignore pattern (no check to see if file exists)"""
    head,filename=os.path.split(path)
    if any(fnmatch(filename, pattern) for pattern in IGNORELIST):
        return True
    else:
        return False

def ignorepath(parentFolder):
    ignorefiles=[]
    assert os.path.exists(parentFolder)
    for dirName, subdirs, fileList in os.walk(parentFolder): #go through every subfolder in a folder
        #print('Scanning %s...' % dirName)
        for filename in fileList: #now through every file in the folder/subfolder
            if any(fnmatch(filename, pattern) for pattern in IGNORELIST):
                log.debug('Ignoring \'{}\',\'{}\''.format(filename, os.path.abspath(filename)))
                ignorefiles.append((filename, os.path.abspath(filename)))
                continue
    return ignorefiles

#
#if __name__ == '__main__':   #
#    scanpath('')
#    
