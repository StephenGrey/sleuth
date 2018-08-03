# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from __future__ import print_function
#from bs4 import BeautifulSoup as BS
from django.conf import settings
import requests, os, logging, json, urllib
import ownsearch.hashScan as dup
import hashlib  #routines for calculating hash
from .models import Collection,File,Index
log = logging.getLogger('ownsearch.indexsolr')
from usersettings import userconfig as config
from ownsearch.solrJson import SolrConnectionError
from ownsearch.solrJson import SolrCoreNotFound
from documents.updateSolr import delete,updatetags,check_hash_in_solrdata,check_file_in_solrdata,remove_filepath_or_delete_solrrecord
from ownsearch import solrJson as s
from fnmatch import fnmatch
from . import solrICIJ,file_utils

try:
    from urllib.parse import quote #python3
except ImportError:
    from urllib import quote #python2


try:
    IGNORELIST=config['Solr']['ignore_list'].split(',')
    DOCSTORE=config['Models']['collectionbasepath'] #get base path of the docstore
    TIMEOUT=float(config['Solr']['solrtimeout'])
    
except Exception as e:
    log.warning('Configuration warning: no ignore list found')
    IGNORELIST=[]
    
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

class Extractor():
    """extract a collection of docs into solr"""
    def __init__(self,collection,mycore,forceretry=False,useICIJ=False,ocr=True,docstore=''):
        
        if not isinstance(mycore,s.SolrCore) or not isinstance(collection,Collection):
            raise BadParameters("Bad parameters for extraction")
        self.collection=collection
        self.mycore=mycore
        self.forceretry=forceretry
        self.useICIJ=useICIJ
        self.ocr=ocr
        self.docstore=docstore
        self.counter,self.skipped,self.failed=0,0,0
        self.skippedlist,self.failedlist=[],[]

        self.filelist=File.objects.filter(collection=collection)
        
        self.extract()
    
    
    def extract(self):
        #main loop
        for file in self.filelist:
            #log.debug(file.__dict__)
            if self.skip_file(file):
                log.debug('Skipping {}'.format(file))
            else:
                log.info('Attempting index of {}'.format(file.filepath))
                
                #if was previously indexed, store old solr ID and then delete if new index successful
                oldsolrid=file.solrid
                #get source
                try:
                    sourcetext=file.collection.source.sourceDisplayName
                except:
                    sourcetext=''
                    log.debug('No source defined for file: {}'.format(file.filename))
                
                
                if file.is_folder:
                    log.debug('Skipping extract of folder')
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
                        if self.useICIJ:
                            log.info('using ICIJ extract method..')
                            result = solrICIJ.ICIJextract(file.filepath,self.mycore,ocr=self.ocr)
                            if result is True:
                                try:
                                    new_id=s.hashlookup(file.hash_contents,self.mycore).results[0].id #id of the first result returned
                                    file.solrid=new_id
                                    file.save()
                                    log.info('(ICIJ extract) New solr ID: '+new_id)
                                except:
                                    log.warning('Extracted doc not found in index')
                                    result=False
                            if result is True:
                            #post extract process -- add meta data field to solr doc, e.g. source field
                                try:
                                    sourcetext=file.collection.source.sourceDisplayName
                                except:
                                    sourcetext=''
                                if sourcetext:
                                    try:
                                        result=solrICIJ.postprocess(new_id,sourcetext,file.hash_contents,self.mycore)
                                        if result==True:
                                            log.debug('Added source: \"{}\" to docid: {}'.format(sourcetext,new_id))
                                    except Exception as e:
                                        log.error('Cannot add meta data to solrdoc: {}, error: {}'.format(new_id,e))
                        else:
                            try:
                                result=extract(file.filepath,file.hash_contents,self.mycore,sourcetext=sourcetext,docstore=self.docstore)
                            except (s.SolrCoreNotFound,s.SolrConnectionError,requests.exceptions.RequestException) as e:
                                raise ExtractInterruption(self.interrupt_message())
             
                if result is True:
                    self.counter+=1
                    #print ('PATH :'+file.filepath+' indexed successfully')
                        
                    if not self.useICIJ:
                        file.solrid=file.hash_contents  #extract uses hashcontents for an id , so add it
                    
                    file.indexedSuccess=True
                    
                    #now delete previous solr doc of moved file(if any): THIS IS ONLY NECESSARY IF ID CHANGES  
                    log.info('Old ID: '+oldsolrid+' New ID: '+file.solrid)
                    
                    if oldsolrid and oldsolrid!=file.solrid:
                        log.info('now delete or update old solr doc'+str(oldsolrid))
                        relpath=make_relpath(file.filepath,docstore=self.docstore)
                        remove_filepath_or_delete_solrrecord(oldsolrid,relpath,self.mycore)
                    file.save()
                else:
                    log.info('PATH : '+file.filepath+' indexing failed')
                    self.failed+=1
                    file.indexedTry=True  #set flag to say we've tried
                    log.debug('Saving updated file info in database')
                    file.save()
                    self.failedlist.append(file.filepath)

    def update_existing_meta(self,file,existing_doc):
        """update meta of existing solr doc"""
        file.solrid=existing_doc.id
        log.debug('Existing docpath: {}'.format(existing_doc.data.get('docpath')))
        log.debug('Existing parent path hashes: {}'.format(existing_doc.data.get(self.mycore.parenthashfield)))
        
        #no need to extract
        paths=existing_doc.data.get('docpath')        
        relpath=make_relpath(file.filepath,docstore=self.docstore)
        
        if paths:
            if relpath not in paths:
                paths.append(relpath)
                log.debug('Updating doc \"{}\" to append the old and new filepath {} to make {}'.format(file.solrid,file.filepath,paths))
                result=updatetags(file.solrid,self.mycore,field_to_update='docpath',value=paths)
                
                if result:
                    parent_hashes=file_utils.parent_hashes(paths)
                    result=updatetags(file.solrid,self.mycore,field_to_update=self.mycore.parenthashfield,value=parent_hashes)
                
                
            else:
                log.debug('Path to file already stored in solr index')
                result=True
        else:
            log.error('Filepath not found in existing doc')
            result=False
        file.save()
        return result
       
    def skip_file(self,file):
        if file.indexedSuccess:
            pass
            #skip this file: it's already indexed
        elif file.indexedTry==True and self.forceretry==False:
            #skip this file, tried before and not forcing retry
            log.info('Skipped on previous index failure; no retry: {}'.format(file.filepath))
        elif ignorefile(file.filepath) is True:
            #skip this file because it is on ignore list
            log.info('Ignoring: {}'.format(file.filepath))
        else:
            return False
        self.skipped+=1
        self.skippedlist.append(file.filepath)
        return True

    def interrupt_message(self):
        return '{} files extracted, {} files skipped and {} files failed.'.format(self.counter,self.skipped,self.failed)
        
    def extract_folder(self,file):
        
        file.solrid=file.hash_filename
        
        log.debug('extracting folder')
           #extract a relative path from the docstore root
        relpath=make_relpath(file.filepath,docstore=self.docstore)
        #args+='&literal.{}={}&literal.{}={}'.format(filepathfield,relpath,pathhashfield,file_utils.pathHash(path))
        result=updatetags(file.solrid,self.mycore,field_to_update='docpath',value=[relpath])
        if result:
            #add hash of parent relative path
            if self.mycore.parenthashfield:
                parenthash=file_utils.parent_hash(relpath)
                #args+='&literal.{}={}'.format(parenthashfield,parenthash)
                log.debug("Parenthash: {} Relpath: {}".format(parenthash,relpath))
                result=updatetags(file.solrid,self.mycore,field_to_update=self.mycore.parenthashfield,value=parenthash)
            else:
                log.debug('no parenthashfield')
                result=False    
            
            if result:
                result=updatetags(file.solrid,self.mycore,field_to_update=self.mycore.docnamesourcefield,value='Folder: {}'.format(file.filename))
        
        return result


class ExtractFile():
    def __init__(self):
        pass

    
#SOLR METHODS

def extract_test(test=True,timeout=TIMEOUT,mycore='',docstore=''):
    #get path to test file
    path=settings.BASE_DIR+'/tests/testdocs/testfile/TESTFILE_BBCNews1.pdf'
    assert os.path.exists(path)
    
    #get hash
    hash=dup.hashfile256(path)
    #print(hash)
    
    if not mycore:
        #get default index
        defaultID=config['Solr']['defaultcoreid']
        cores=s.getcores()
        mycore=cores[defaultID]

    #checks solr index is alive
    log.debug('Testing extract to {}'.format(mycore.name))
    mycore.ping()
    
    result=extract(path,hash,mycore,test=test,timeout=TIMEOUT,docstore=docstore)
    return result

def extract(path,contentsHash,mycore,test=False,timeout=TIMEOUT,sourcetext='',docstore=''):
    """extract a path to solr index (mycore), storing hash of contents, optional testrun, timeout); throws exception if no connection to solr index, otherwise failures return False"""
    
    try:
        assert isinstance(mycore,s.SolrCore)
        assert os.path.exists(path) #check file exists
    except AssertionError:
        log.debug ('Extract: bad parameters: {},{}'.format(path,mycore))
        return False
    #establish connnection to solr index
    mycore.ping() #       throws a SolrConnectionError if solr is down; throw error to higher level.

    if contentsHash =='':
        contentsHash=dup.hashfile256(path)    

    try:
        docnamesourcefield=mycore.docnamesourcefield
        hashcontentsfield=mycore.hashcontentsfield
        filepathfield=mycore.docpath
        sourcefield=mycore.sourcefield
        id_field=mycore.unique_id
        pathhashfield=mycore.pathhashfield
        parenthashfield=mycore.parenthashfield

    except AttributeError as e:
        log.error('Exception: {}'.format(e))
        log.error('Solr index is missing default fields')
        return False
#    extracturl=mycore.url+'/update/extract?'
    extractargs='commit=true&wt=json'
    args='{}&literal.{}={}&literal.{}={}'.format(extractargs,id_field,contentsHash,docnamesourcefield,os.path.basename(path))
    
    #extract a relative path from the docstore root
    relpath=make_relpath(path,docstore=docstore)
    args+='&literal.{}={}&literal.{}={}'.format(filepathfield,relpath,pathhashfield,file_utils.pathHash(path))

    #add hash of parent relative path
    if parenthashfield:
        parenthash=file_utils.parent_hash(relpath)
        args+='&literal.{}={}'.format(parenthashfield,parenthash)

    #if a different field for hashcontents other than the unique ID (key) then store also in that field
    if id_field != hashcontentsfield:
        args+='&literal.{}={}'.format(hashcontentsfield,contentsHash)
    #if sourcefield is define and sourcetext is not empty string, add that to the arguments
    #make the sourcetext args safe, for example inserting %20 for spaces 
    if sourcefield and sourcetext:
        args+='&literal.{}={}'.format(sourcefield,quote(sourcetext))
    
    log.debug('extract args: {}, path: {}, solr core: {}'.format(args,path,mycore))
        
    if test==True:
        args +='&extractOnly=true' #does not index on test
        log.debug('Testing extract args: {}, path: {}, mycore {}'.format(args,path,mycore))
        
    result,elapsed=postSolr(args,path,mycore,timeout=timeout) #POST TO THE INDEX (returns True on success)
    if result:
        log.info('Extract SUCCEEDED in {:.2f} seconds'.format(elapsed))
        return True
    else:
        log.info('Error in extract() posting file with args: {} and path: {}'.format(args,path))
        log.info('Extract FAILED')
        return False


def postSolr(args,path,mycore,timeout=1):
    extracturl=mycore.url+'/update/extract?'
    url=extracturl+args
    log.debug('POSTURL: {}  TIMEOUT: {}'.format(url,timeout))
    #log.debug('Types posturl: {} path: {}'.format(type(url),type(timeout)))
    try:
        res=s.resPostfile(url,path,timeout=timeout) #timeout=
        #log.debug('Returned json: {} type: {}'.format(res._content,type(res._content)))
        log.debug('Response header:{}'.format(res.json()['responseHeader']))
        
        solrstatus=res.json()['responseHeader']['status']
        #log.debug(res.elapsed.total_seconds())
        solrelapsed=res.elapsed.total_seconds()
    except s.SolrTimeOut as e:
        log.error('Solr post timeout ')
        return False,0
    except s.Solr404 as e:
        log.error('Error in posting 404 error - URL not workking: {}'.format(e))
        return False,0
    except s.PostFailure as e:
        log.error('Post Failure : {}'.format(e))
        return False,0
    log.debug('SOLR STATUS: {}  ELAPSED TIME: {:.2f} secs'.format(solrstatus,solrelapsed))
    if solrstatus==0:
        return True,solrelapsed 
    else:
        return False,0


"""UTILITIES:"""

def make_relpath(path,docstore=''):
    if not docstore:
        docstore=DOCSTORE
    return os.path.relpath(path,start=docstore)

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
