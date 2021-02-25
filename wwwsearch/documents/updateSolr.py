# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from __future__ import print_function
from __future__ import absolute_import
import requests, os, logging, re
import json, collections
import ownsearch.solrJson as s
import documents.solrcursor as sc
from datetime import datetime, date, time
from .models import File,Collection
from . import changes, time_utils
from ownsearch.hashScan import HexFolderTable as hex
from ownsearch.hashScan import hashfile256 as hexfile
from .file_utils import pathHash,parent_hash,parent_hashes,make_relpath,relpath_exists
from ownsearch.hashScan import FileSpecTable as filetable
from django.utils import timezone
import pytz #support localising the timezone
log = logging.getLogger('ownsearch.updateSolr')
from configs import config

DOCSTORE=config['Models']['collectionbasepath'] #get base path of the docstore

class SolrdocNotFound(Exception):
    pass

class DuplicateRecords(Exception):
    pass


class Updater:
    """template to modify solr index"""
    def __init__(self,mycore,searchterm='*',maxcount=100000):
        self.mycore=mycore
        self.searchterm=searchterm
        self.update_errors=False
        self.args=''
        self.maxcount=maxcount
    
    def modify(self,result):
        pass
        
    def process(self):
        """iterate through the index, modifying as required"""
        counter=0
        res=False
        maxcount=self.maxcount
        try:
            while True:
                res = sc.cursor_next(self.mycore,self.searchterm,highlights=False,lastresult=res,rows=5)
                if res == False:
                    break
                #ESCAPE ROUTES ;
                if not res.results:
                    break

                for doc in res.results:
                    #get all relevant fields
                    #print(doc.__dict__)
                    counter+=1
                    if counter>maxcount:
                        break
                    
                    searchterm=self.mycore.unique_id+r':"'+doc.id+r'"'
                    
                    jres=s.getJSolrResponse(searchterm,self.args,core=self.mycore)
                    results=s.SolrResult(jres,self.mycore).results
                    #print(results)
                    if results:
                        result=results[0]
                        self.modify(result)
                    else:
                        log.debug('Skipping missing record {}'.format(doc.id))
                if counter>maxcount:
                    break
        except s.SolrConnectionError:
            log.debug('Solr connection error: failed after {} records'.format(counter))        

class RemoveNoContent(Updater):
    """remove entries with no content"""
    def modify(self,result):
        #log.debug(result.docname)
        if result:
            if not result.folder:
                try:
                    if not result.data.get('rawtext') and not result.data.get('extract_level'):
                        #log.debug('empty file')
                        #log.debug(result.id)
                        #log.debug(result.data.get('docpath'))
                        assert not result.data.get('content_type')
                        
                        delete(result.id,self.mycore)
                except Exception as e:
                    log.error(e)
                    log.debug(result.__dict__)
        else:
            if not result.data.get('extract_level'):
                log.debug(result.__dict__)
            log.debug(result.data.get('extract_level'))
        

class PurgeField(Updater):
    """remove all contents of a single field"""
    def __init__(self,mycore,field):
        self.field=field
        searchterm=f'*&fq={field}:[* TO *]'
        super(PurgeField,self).__init__(mycore,searchterm=searchterm)
        
    def modify(self,result):
        currentvalue=result.data.get(self.field)
        #print(f'SolrID: {result.id}  Current value: {currentvalue}')
        data=make_remove_json(self.mycore,result.id,self.field,currentvalue)
        #print(data)
        post_jsondoc(data,self.mycore)

class UpdateField(Updater):
    """ modify fields in solr index"""
    def __init__(self,mycore,newvalue='test value',newfield=False,searchterm='*',field_datasource='docpath',field_to_update='sb_parentpath_hash',test_run=True,maxcount=100000):
        #set up
        super(UpdateField,self).__init__(mycore,searchterm=searchterm)
        self.newvalue=newvalue
        self.newfield=newfield
        self.field_to_update=field_to_update
        self.field_datasource=field_datasource
        self.field_datasource_decoded=self.mycore.__dict__.get(self.field_datasource,self.field_datasource) #decode the standard field, or use the name'as is'.
        self.args='&fl={},{},database_originalID, sb_filename'.format(self.mycore.unique_id,self.field_datasource_decoded)
        self.test_run=test_run
        self.maxcount=maxcount


    def update_value(self,value):
        """update field with same value in all docs"""
        return self.newvalue

    def modify(self,result):
        try:
            datasource_value=result.data.get(self.field_datasource)
            if self.test_run:
                log.debug('Data source value: {}'.format(datasource_value))
            update_value=self.update_value(datasource_value)
            if not self.test_run and update_value:
                #print('..updating .. ')
                result=updatetags(result.id,self.mycore,value=update_value,field_to_update=self.field_to_update,newfield=self.newfield)
                if result == False:
                    log.error('Update failed for solrID: {}'.format(result.id))
            else:
                if update_value:
                    log.debug('Updating test')
                    log.debug('Update value: {}'.format(update_value))

                    result=updatetags(result.id,self.mycore,value=update_value,field_to_update=self.field_to_update,newfield=self.newfield,test=True)
                    if result == False:
                        log.error('Update failed for solrID: {}'.format(result.id))
                else:
                    log.info('ignoring null update value')
                
        except Exception as e:
            #print(self.__dict__)
            self.update_errors=True
            log.debug(e)
            if self.test_run:
                print('Error in solrupdate modifiy: {}'.format(e))
                    

class AddParentHash(UpdateField):
    def __init__(self, *args, **kwargs):
        super(AddParentHash, self).__init__(*args, **kwargs)

        self.searchterm="-{}:[* TO *]".format(self.mycore.parenthashfield)
        log.debug(f"Searchterm: {self.searchterm}")
        #run update
        self.process()

    
    def update_value(self,datasource_value):
        return parent_hashes(datasource_value)
                        
class CopyField(UpdateField):
    def update_value(self,value):
        """update field with same value in all docs"""
        return value

"""
examples:

updateSolr.CopyField(mycore,field_datasource='message_from_name',field_to_update='message_from',test_run=False,searchterm="content_type:\"application/vnd.ms-outlook\"").process(maxcount=1000000)

CopyField(mycore,field_datasource='message_to_display_name',field_to_update='message_to',test_run=False,searchterm="content_type:\"application/vnd.ms-outlook\" -message_to:*",maxcount=10000).process()

"""

class SequenceByDate(Updater):
    """go through index, put result of search into date order, using 'before' 'next' fields"""
    #user filter queries e.g. searchterm="*&fq=sb_source:\"some source\"" to reorder a subset of the index
    def __init__(self,mycore,searchterm='*',test_run=True,regex=''):
        #set up
        super(SequenceByDate,self).__init__(mycore,searchterm=searchterm)
        if self.mycore.sequencefield=='' or self.mycore.nextfield=='' or self.mycore.beforefield=='':
            log.warning('No before and after fields to sequence')
            return
        self.regex=regex
        self.test_run=test_run
        #print(self.mycore)
        self.getindex(keyfield='date')
        #print(self.indexpaths)
        self.sortindex()
        #print(self.indexsequence)
        self.changes()
    
    def getindex(self,keyfield):
        try:
            self.indexpaths=sc.cursor(self.mycore,keyfield=keyfield,searchterm=self.searchterm)            
        except Exception as e:
            log.warning('Failed to retrieve solr index')
            log.warning(str(e))
            self.indexpaths=False  
    
    def sortindex(self):
        indexsequence=[]
        sequence_number=0
        try:
            keys=sorted(self.indexpaths.keys())
            #print(keys)
            for key in keys:
                for doc in self.indexpaths[key]:
                    sequence_number+=1
                    seq_string='{num:06d}'.format(num=sequence_number)
                    indexsequence.append((seq_string,doc))
            self.indexsequence=indexsequence   
        except Exception as e:
            log.debug(e)
            
    def changes(self):
        for n, item in enumerate(self.indexsequence):
            seq_string,doc=item
            before_seq_string,before_doc=self.indexsequence[n-1]
            after_seq_string,after_doc=self.indexsequence[(n+1)%len(self.indexsequence)]

            changes=[('beforefield','sequencefield',seq_string),('beforefield','beforefield',before_doc.id),('nextfield','nextfield',after_doc.id)]
            #print(doc.docname,changes)

            if changes:
                #make changes to the solr index
                json2post=makejson(doc.id,changes,self.mycore)
                #log.debug('{}'.format(json2post)) 
                if self.test_run==False:
                    response,updatestatus=post_jsonupdate(json2post,self.mycore)
                    #print((response,updatestatus))
                    if checkupdate(doc.id,changes,self.mycore):
                        log.info('solr successfully updated')
                        
                    else:
                        log.error('solr changes not successful')
                        
            else:
                log.info('Nothing to update!')
#    

#            #EXAMPLE FILTER = TEST IF ANY DATA IN FIELD - DATABASE_ORIGINALID _ AND UPDATE OTHERS


def scandocs(collection,delete_on=True,docstore=DOCSTORE,job=None):
    """SCAN A COLLECTION AND MAKE UPDATES TO BOTH LOCAL FILE META DATABASE AND SOLR INDEX"""
    
    scanner=changes.Scanner(collection,job=job)  #get dictionary of changes to file collection (compare disk folder to meta database)
    
    if scanner.total:
        try:
            #make any changes to local file database
            scanner.update_database()        
        except Exception as e:
            log.error('Failed to make updates to file database')
            log.error(f'Error: {e}')
            scanner.scan_error=True
            return scanner
    
        #remove deleted files from the index
        #(only remove from database when successfully removed from solrindex, so if solr is down won't lose sync)
        if delete_on and scanner.deleted_files:
            try:
                removedeleted(scanner.deleted_files,collection,docstore=docstore)
            except Exception as e:
                log.debug('Failed to remove deleted files from solr index. Error: {}'.format(e)) 
    
        #alters meta in the the solr index (via an atomic update)
        metaupdate(collection) 
    else:
        log.debug('no files found')
    return scanner
    

def check_hash_in_solrdata(contents_hash,mycore):    
    try:
        existing_docs=s.hashlookup(contents_hash,mycore).results
        if not existing_docs:
            log.debug('hash \"{}\" not found in index'.format(contents_hash))
            return None
        if len(existing_docs)>1:
            raise DuplicateRecords("Document found more than once in index")
        return existing_docs[0]
    except s.SolrConnectionError:
        raise s.SolrConnectionError
    except DuplicateRecords as e:
        log.warning(e)
        return existing_docs[0]
    except Exception as e:
        log.debug(e)
        log.info('hash \"{}\" not found in index'.format(contents_hash))
        return None
        
def check_file_in_solrdata(file_in_database,mycore):
    return check_hash_in_solrdata(file_in_database.hash_contents,mycore)

def removedeleted(deletefiles,collection,docstore=DOCSTORE):
    cores=s.getcores() #fetch dictionary of installed solr indexes (cores)
    mycore=cores[collection.core.id]
    log.debug('Delete from core: {}'.format(mycore))
    filelist=File.objects.filter(collection=collection)
    for path in deletefiles:
        files=filelist.filter(filepath=path)
        for file in files:
            if file.solrid:
                relpath=os.path.relpath(file.filepath,start=docstore)
                log.debug('File to delete {} from solr id: {}'.format(relpath,file.solrid))        
                try:
                    result=remove_filepath_or_delete_solrrecord(file.solrid,relpath,mycore)
                    if result:
                        pass
                    else:
                        #try a fullpath
                        result=remove_filepath_or_delete_solrrecord(file.solrid,file.filepath,mycore)
                        if result:
                            pass
                        else:
                            log.debug('Failed to delete from solr index; deleting database entry anyway'.format(path))
                except SolrdocNotFound:
                    log.debug('Both solr doc & disk path not found - remove database entry')
            file.delete()
            log.debug(f'Deleted \'{path}\' from collection: \'{collection}\' in index: \'{file.collection.core}\'')
        
    return

def remove_filepath_or_delete_solrrecord(oldsolrid,filepath,mycore):
    return remove_filepath(oldsolrid,filepath,mycore,deletedoc=True)
    

def remove_filepath(oldsolrid,filepath,mycore,deletedoc=False):
    olddoc=check_hash_in_solrdata(oldsolrid,mycore)
    if not olddoc:
        log.debug('Doc not found with ID: {} '.format(oldsolrid))
        raise SolrdocNotFound

    paths=olddoc.data.get('docpath')
    log.debug('Paths found in existing doc: {}'.format(paths))
    log.debug('Deleting \'{}\' from filepaths in solrdoc \'{}\''.format(filepath,oldsolrid))

    if not isinstance(paths,list):
        paths=[paths]    

    if filepath not in paths:
        log.debug('{} not found in solrdoc existing filepaths'.format(filepath))
        
        return False
        
    if not deletedoc or (deletedoc and len(paths)>1):
        log.info('Deleting {} from filepaths in solrdoc {}'.format(filepath,oldsolrid))
        paths.remove(filepath)
        result=updatetags(oldsolrid,mycore,field_to_update='docpath',value=paths)
        
        if result:
            parenthashes=olddoc.data.get(mycore.parenthashfield,None)
            if not isinstance(parenthashes,list):
                parenthashes=[parenthashes]
            log.debug('Existing parentpath hashes: {}'.format(parenthashes))           
            log.debug(parenthashes)
            if parenthashes=='None':
                print('None string')
                
            if parenthashes and parenthashes !=[None]:
                result=remove_hash(parenthashes,filepath,mycore,oldsolrid)
            return result

    elif deletedoc:
        response,status=delete(oldsolrid,mycore)
        if status:
            log.info('Deleted solr doc with ID:'+oldsolrid)
            return True            
    return False

def remove_hash(hashes,filepath,mycore,solrid):
    hashes.remove(parent_hash(filepath))
    result=updatetags(solrid,mycore,field_to_update=mycore.parenthashfield,value=hashes)
    return result

def delete(solrid,mycore):
    """delete a file from solr index"""
    data=deletejson(solrid,mycore)
    #log.debug('Json to post: {}'.format(data))
    response,status=post_jsonupdate(data,mycore)
    #log.debug('Response: {}'.format(response))
    return response,status
    
def deletejson(solrid,mycore):
    """build json to delete a solr doc"""
    a=collections.OrderedDict()  #keeps the JSON file in a nice order
    a['delete']={"id":solrid}  #id refers to the unique field, whatever the field name actually is
    data=json.dumps(a)
    return data

"""
It looks like this:
 "delete": { "id":"ID" },
"""

def delete_all(mycore):
    """delete all docs in solr index"""
    data=delete_all_json()
    response,status=post_jsonupdate(data,mycore)
    return response,status    

def delete_all_json():
    """ build json to delete all docs"""
    a=collections.OrderedDict()  #keeps the JSON file in a nice order
    a['delete']={'query':"*:*"}
    a['commit']={}
    data=json.dumps(a)
    return data
"""
{
    "delete": {
        "query": "*:*"
    },
    "commit": {}
}
"""
"""
HANDLE CHANGES
Methods to handle a list of defined changes: [[(sourcefield, resultfield, value),...]
	fields can be standardised field names (e.g. 'datesourcefield','date',) or actual field names ('tika_last_modified')
	the "resultfield" is an attribute of the SolrDoc object 
 
"""
def update(id,changes,mycore,_test=False,check=True):  #solrid, list of changes [(sourcefield, resultfield, value),(f1,f2,value)..],core
    """update solr index with list of atomic changes"""
    data=makejson(id,changes,mycore)
    response,poststatus=post_jsonupdate(data,mycore,test=_test,check=check)
    log.debug('Response: {} PostStatus: {}'.format(response,poststatus))
    if not _test and check:
        updatestatus=checkupdate(id,changes,mycore)
        if updatestatus:
            log.debug('solr successfully updated')
        else:
            log.debug('solr changes not successful')    
        return response,updatestatus
    else:
        return response,True

def makejson(solrid,changes,mycore):   #the changes use standard fields (e.g. 'datesourcefield'); so parse into actual solr fields
    """make json instructions to make atomic changes to solr core"""
    a=collections.OrderedDict()  #keeps the JSON file in a nice order
    a[mycore.unique_id]=solrid 
    for sourcefield,resultfield,value in changes:
        solrfield=mycore.__dict__.get(sourcefield,sourcefield) #if defined in core, replace with standard field, or leave unchanged
        if solrfield !='':
            a[solrfield]={"set":value}
    data=json.dumps([a])
    return data

def make_atomic_json(solrid,changes,id_field):
	"""make json instructiosn for atomic changes with fields already calculated"""
	a=collections.OrderedDict()  #keeps the JSON file in a nice order
	a[id_field]=solrid 
	for field,value in changes.items():
		a[field]={"set":value}
	data=json.dumps([a])
	return data
	 

def clear_date(solrid,mycore):
    docs=s.getmeta(solrid,mycore)
    if docs:
        doc=docs[0]
        if doc.date:
            data=make_remove_json(mycore,solrid,mycore.datesourcefield,doc.date)
            response,poststatus=post_jsonupdate(data,mycore)
            doc=s.getmeta(solrid,mycore)[0]
    #        
    #        if doc.date and mycore.datesourcefield2:
    #            data=make_remove_json(mycore,solrid,mycore.datesourcefield2,doc.date)
    #            response,poststatus=post_jsonupdate(data,mycore)
    #            doc=s.getmeta(solrid,mycore)[0]
    #            if not doc.date:
    #                return True
    #            else:
    #                return False
    #        else:
            if doc.date:
                return False
    return True


def make_remove_json(mycore,solrid,field,value):
    """json to clear a field value"""
    a=collections.OrderedDict()
    a[mycore.unique_id]=solrid 
    a[field]={"remove":value}
    data=json.dumps([a])
    return data


def checkupdate(id,changes,mycore):
    """check success of an update"""
    #print id
    status=True
    res=s.getmeta(id,mycore)
    #print (changes,res[0])
    if len(res)>0: #check there are solr docs returned
        doc=res[0]
        for sourcefield, resultfield,value in changes:
            if sourcefield=='rawtext':
                continue
            #print('Change',sourcefield,resultfield,value)
            solrfield=resultfield            
            newvalue=doc.__dict__.get(solrfield,doc.data.get(solrfield,''))
            if not newvalue:
                solrfield=mycore.__dict__.get(resultfield,resultfield)
                newvalue=doc.__dict__.get(solrfield,doc.data.get(solrfield,''))
#            log.debug(f'Solrdoc.data {doc.data} solrfield: {solrfield} newvalue={newvalue} targetvalue={value}')
##            log.debug(doc.__dict__)
#            log.debug(type(newvalue))
#            log.debug(newvalue)
            
            
            if newvalue != None:
                #print(newvalue,type(newvalue))
                if isinstance(newvalue,int):
                    try:
                        value=int(value)
                    except:
                        pass
                elif isinstance(newvalue, list): #check for a list e.g date(not a string)
                    if newvalue==value: 
                        log.debug('{} successfully updated to {}'.format(resultfield,value))
                    else:
                        newvalue=newvalue[-1] if len(newvalue)>0 else '' #use the last in list
                        if newvalue==value: 
                            log.debug('{} successfully updated to {}'.format(resultfield,value))
                else:
                    if newvalue==value or [newvalue]==value: 
                        log.debug('{} successfully updated to {}'.format(resultfield,value))
                    else:
                        log.debug('{} NOT updated; current value {}'.format(resultfield,value))
                        status=False
            else:
                log.debug('{} not found in solr result'.format(resultfield))
                status=False
    else:
        print(('error finding solr result for id',id))
        status=False
    return status


def post_jsonupdate(data,mycore,timeout=10,test=False,check=True):
    """ I/O with Solr API """
    log.debug(f'Check: {check}')
    if check:
        updateurl=mycore.url+'/update/json?commit=true'
    else:
        updateurl=mycore.url+'/update/json'
    url=updateurl
    log.debug(data)
    headers={'Content-type': 'application/json'}
    try:
        ses=s.SolrSession()
        if not test:
            res=ses.post(url, data=data, headers=headers,timeout=timeout)
            jres=res.json()
            status=jres['responseHeader']['status']
            #log.debug(jres)
        else:
            log.info('TEST ONLY: simulate post to {}, with data {} and headers {}'.format(url,data,headers))
            status=0
            jres={'Test':True}
        if status==0:
            statusOK = True
        else:
            statusOK = False
        return jres, statusOK
    except IndexError as e:
        log.error('Exception: {}'.format(e))
    except s.ConnectionError as e:
        log.error('Connection Error')
    except Exception as e:
        log.error(f'Unknown exception: {e}')
    return '',False
       
def post_jsondoc(data,mycore):
    """post json to solr index"""
    updateurl=mycore.url+'/update/json/docs?commit=true'
    url=updateurl
    headers={'Content-type': 'application/json'}
    try:
        ses=s.SolrSession()
        res=ses.post(url, data=data, headers=headers)
        jres=res.json()
        status=jres['responseHeader']['status']
        if status==0:
            statusOK = True
        else:
            statusOK = False
        return res.json(), statusOK
    except Exception as e:
        log.debug('Exception:  {}'.format(e))
        statusOK=False
        return '',statusOK

        

def metaupdate(collection,test_run=False):
    """update the metadata in the SOLR index"""
    #print ('testing collection:',collection,'from core',collection.core,'core ID',collection.core.coreDisplayName)
    cores=s.getcores() #fetch dictionary of installed solr indexes (cores)
    mycore=cores[collection.core.id]
    #main code
    
    filelist=File.objects.filter(collection=collection)
        
    for _file in filelist: #loop through files in collection
        #log.debug(f'File: {_file} Updatemetaflag: \'{_file.indexUpdateMeta}\'  ID:\'{_file.solrid}\'')
        if _file.solrid:
            #do action if indexUpdateMeta flag is true; and there is a stored solrID
            if _file.indexUpdateMeta:
                metaupdate_file(_file,mycore,test_run=test_run)
            else:
                #log.debug('file not flagged for meta update')
                pass
        else:
            #log.debug('[metaupdate]file not found in solr index')
            pass

def metaupdate_rawfile(_file,test_run=False):
    cores=s.getcores() #fetch dictionary of installed solr indexes (cores)
    mycore=cores[_file.collection.core.id]
    metaupdate_file(_file,mycore,test_run=test_run)

def metaupdate_file(_file,mycore,test_run=False,_docstore=DOCSTORE):
    if not _file.indexUpdateMeta:
        log.debug('Wrong call to metaupdate: Not flagged for update')
        return
    assert _file.solrid
    log.debug('ID: {}'.format(_file.solrid))
    log.debug('Solr meta data flagged for update')
    results=s.getmeta(_file.solrid,core=mycore)  #get current contents of solr doc, without full contents
    if len(results)>0:
        solrdoc=results[0] #results come as a list so just take the first one
        _changes=parsechanges(solrdoc,_file,mycore,docstore=_docstore) #returns list of tuples [(field,newvalue),]
        if _changes:
            #make changes to the solr index - using standardised fields
            json2post=makejson(solrdoc.id,_changes,mycore)
            log.debug('{}'.format(json2post)) 
            if not test_run:
                response,updatestatus=post_jsonupdate(json2post,mycore)
                if checkupdate(solrdoc.id,_changes,mycore):
                    log.debug('solr successfully updated')
                    _file.indexUpdateMeta=False
                    _file.save()
                else:
                    log.warning('solr changes not successful')
            else:
                log.debug('TEST run: no changes made')
        else:
            log.debug('Nothing to update!')
            if not test_run:
                _file.indexUpdateMeta=False
                _file.save()
        #tidy up
        #remove old paths
        remove_oldpaths(_file,mycore)
    else:
        log.debug('[metaupdate]file not found in solr index')

def remove_oldpaths(_file,mycore):
    existing_oldpaths_raw=_file.oldpaths_to_delete
    oldpaths=json.loads(existing_oldpaths_raw) if existing_oldpaths_raw else ''
    if oldpaths:
        for path in oldpaths:
            if os.path.exists(path):
                #relpath_exists(path,root=DOCSTORE):
                log.warning('Trying to delete a path that exists - ignoring')
            else:
                relpath=make_relpath(path,docstore=DOCSTORE)
                if remove_filepath(_file.solrid,relpath,mycore,deletedoc=False):
                    log.debug(f'Successfully removed filepath {path}')

def check_paths(solr_result,_file,mycore,docstore=DOCSTORE):
    """check if path needs updated, return new paths and parent_hashes"""
    paths=solr_result.data.get('docpath')
    if not paths:
        log.error('No stored filepath found in existing doc')
        return False,None,None
    else:
        return path_changes(_file.filepath,paths,docstore=docstore)

def path_changes(filepath,existing_paths,docstore=DOCSTORE):
    #log.debug(f'{existing_paths}, {filepath}')
    relpath=make_relpath(filepath,docstore=docstore)       
    if '' in existing_paths and relpath in existing_paths:
        existing_paths.remove('')
        p_hashes=parent_hashes(existing_paths)
        return True,existing_paths,p_hashes
    elif relpath in existing_paths:
        #log.debug('Correct relative filepath already stored in doc')
        return False,existing_paths,None
    if filepath in existing_paths:#replace full path with relative path
        existing_paths.remove(filepath)
    if '' in existing_paths:
        existing_paths.remove('')
    existing_paths.append(relpath)
    p_hashes=parent_hashes(existing_paths)
    
    return True,existing_paths,p_hashes


def parsechanges(solrresult,_file,mycore,docstore=DOCSTORE): 
    """take a Solr Result object,compare with _file database, 
   return change list [(standardisedsourcefield,resultfield,newvalue),..]"""
    #print(solrresult)
    solrdocsize=solrresult.data['solrdocsize']
    try:
        solrdocsize=solrdocsize[0]
    except:
        pass
    olddocsize=int(solrdocsize) if solrdocsize else 0
    olddocpath=solrresult.data['docpath']
    olddate=solrresult.date
    oldsource=solrresult.data.get(mycore.sourcefield)
    log.debug(f'solrresult: {solrresult.__dict__}')
    
    
    
    
    if olddate:
        try:
            oldlastmodified=time_utils.parseISO(olddate)#convert raw time text from solr into time object
        except time_utils.iso8601.ParseError as e:
            log.debug('date stored in solr cannot be parsed')
            oldlastmodified=''
        except Exception as e:
            log.debug('Error with date stored in solr {}, {}'.format(olddate, e))
            oldlastmodified=''
    else:
        oldlastmodified='' 
    olddocname=solrresult.docname
#    print olddocsize,olddocpath,olddocname, oldlastmodified

    #compare solr data with new metadata & make list of changes to make in solr
    changes=[] 

    paths_are_missing,paths,p_hashes=check_paths(solrresult,_file,mycore,docstore=docstore)
    if paths_are_missing:
        log.debug(f'Updating paths to: {paths}') 
        changes.append(('docpath','docpath',paths))
        changes.append((mycore.parenthashfield,mycore.parenthashfield,p_hashes))

    if not oldsource:
        newsource=get_source(_file)
        if newsource:
            changes.append((mycore.sourcefield,mycore.sourcefield,newsource))

    if olddocsize != _file.filesize:
        log.info('need to update filesize from old {} to new {}'.format(olddocsize,_file.filesize))
        changes.append((mycore.docsizesourcefield1,'solrdocsize',_file.filesize))
        
    newlastmodified=time_utils.timestringGMT(_file.content_date) if _file.content_date else time_utils.timestringGMT(_file.last_modified)
    
   
#    _file.last_modified.strftime("%Y-%m-%dT%H:%M:%SZ")
    if olddate !=newlastmodified:
        log.info('need to update last_modified from \"{}\"  to \"{}\"'.format(oldlastmodified, newlastmodified))
        changes.append(('datesourcefield','date',newlastmodified))
        if clear_date(_file.solrid,mycore):
            log.debug('cleared previous stored date')
        else:
            log.debug('failed to clear previous stored date')
    newfilename=f'Folder: {_file.filename}' if _file.is_folder else _file.filename

    if olddocname != newfilename:
        log.info('need to update filename from {} to {}'.format(olddocname,newfilename))
        changes.append(('docnamesourcefield','docname',newfilename))
    

    return changes

#TESTING
def listmeta(id=2):
    collection=Collection.objects.get(id=id)
    filelist=File.objects.filter(collection=collection)
    for file in filelist:
        if not file.indexedSuccess:
            print(file.filename, 'ID:'+file.solrid,'PATHHASH'+file.hash_filename)
            print('Needs to be Indexed')
        if file.indexUpdateMeta:
            print(file.filename, 'ID:'+file.solrid,'PATHHASH'+file.hash_filename)
            print('Solr meta data needs update')

#POST EXTRACTION PROCESSING

def updatetags(solrid,mycore,value=['test','anothertest'],field_to_update='usertags1field',newfield=False,test=False,check=True):
    """ADD ADDITIONAL METADATA TO SOLR RECORDS """
    #check the parameters
    field=mycore.__dict__.get(field_to_update,field_to_update) #decode the standard field, or use the name'as is'.
    if newfield==False and test==False:
        try:
            assert s.fieldexists(field,mycore) #check the field exists in the index
        except AssertionError as e:
            log.info('Field \"{}\" does not exist in index'.format(field))
            return False

    #make the json
    doc=collections.OrderedDict()  #keeps the JSON file in a nice order
    doc[mycore.unique_id]=solrid
    doc[field]={"set":value}
    jsondoc=json.dumps([doc])
    log.debug(f'Json to post to index \"{mycore}\": {jsondoc}')

    #post the update
    result,status=post_jsonupdate(jsondoc,mycore,timeout=10,test=test,check=check)
    
    #check the result
    log.debug('Solr doc update: result: {}, status: {}'.format(result,status))
    
    return status


def metareplace(mycore,resultfield,find_ex,replace_ex,searchterm='*',sourcefield='',test=False):
    """Update a field with regular expression find and replace"""   
    #example: u.metareplace(mc,'docpath','^','foldername/',searchterm='* -foldername',sourcefield='',test=False) 
    #sourcefield is a field whose value may be copied to the resultfield 
    if sourcefield=='':
        sourcefield=resultfield
    try:#make a dictionary of docs from solr index
        indexpaths=sc.cursor(mycore,resultfield,searchterm=searchterm)
    except Exception as e:
        log.warning('Failed to retrieve solr index')
        log.warning(str(e))
        return False
    for key in indexpaths:
        for doc in indexpaths[key]:
            fieldvalue=getattr(doc,resultfield,doc.data.get(resultfield,''))
            newvalue=re.sub(find_ex,replace_ex,fieldvalue)
            log.debug('Oldvalue: {} Newvalue: {}'.format(fieldvalue,newvalue))
            if newvalue!=fieldvalue:
                changes=[(sourcefield,resultfield,newvalue)]
                #make changes to the solr index
                if test==False:
                    res,status=update(doc.id,changes,mycore)
                    print(status)
    return

    
def sequence(mycore,regex='^XXX(\d+)_Part(\d+)(_*)OCR'):
    """parse filename with regex to put solrdocs in order with a regular expression, update 'before' and 'after' field """
    print(mycore)
    try:#make a dictionary of filepaths from solr index
        indexpaths=sc.cursor(mycore,keyfield='docname',searchterm='*')
    except Exception as e:
        log.warning('Failed to retrieve solr index')
        log.warning(str(e))
        return False
    indexsequence={}
    for docname in indexpaths:
        print (docname)
        seq_number=docname
        #main loop - go through files in the collection
        try:
            match=re.search(regex,docname)
            seq_number=(int(match.group(1))*1000)+int(match.group(2))
            seq_string='{num:06d}'.format(num=seq_number)
            indexsequence[seq_number]=(seq_string,indexpaths[docname][0]) #take only first record
        except Exception as e:
            print((docname,e))
            pass
        print((seq_number,seq_string,docname))
    keys=sorted(indexsequence.keys())
    print((indexsequence,keys))
    for n, sortedkey in enumerate(keys):
        #print((n,sortedkey))
        seq_string,doc=indexsequence[sortedkey]
        before=keys[n-1]
        before_str='{num:06d}'.format(num=before)
        before_seq_string,before_doc=indexsequence[before]
        after=keys[(n+1)%len(keys)]
        after_str='{num:06d}'.format(num=after)
        after_seq_string,after_doc=indexsequence[after]        
        changes=[('sequencefield',seq_string),('beforefield',before_doc.id),('nextfield',after_doc.id)]

        if changes:
            #make changes to the solr index
            json2post=makejson(doc.id,changes,mycore)
            log.debug('{}'.format(json2post)) 
            response,updatestatus=post_jsonupdate(json2post,mycore)
            #print((response,updatestatus))
            if checkupdate(doc.id,changes,mycore):
                log.debug('solr successfully updated')
            else:
                log.error('solr changes not successful')
        else:
            log.debug('No thing to update!')
    
def get_source(file):
    try:
        sourcetext=file.collection.source.sourceDisplayName
    except:
        sourcetext=''
        log.debug('No source defined for file: {}'.format(file.filename))
    return sourcetext

def get_collection_source(collection):
    try:
        sourcetext=collection.source.sourceDisplayName
    except:
        sourcetext=''
        log.debug('No source defined for collection: {}'.format(collection))
    return sourcetext
