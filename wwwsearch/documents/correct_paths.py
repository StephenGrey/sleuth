# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from __future__ import print_function
from __future__ import absolute_import
import os, logging
log = logging.getLogger('ownsearch.correctpaths')
from . import solrcursor,updateSolr
from configs import config
from ownsearch import solrJson
from .models import Collection,File,Index
from . import file_utils
from .updateSolr import path_changes

DOCSTORE=file_utils.DOCSTORE

def check_solrpaths(mycore,collection,docstore=DOCSTORE):
    #print((mycore,collection))            
    #get the basefilepath
    #docstore=config['Models']['collectionbasepath'] #get base path of the docstore
    #now compare file list with solrindex
    _result=True
    if True:
        filelist=File.objects.filter(collection=collection)
        #main loop - go through files in the collection
        for _file in filelist:
            #hash=_file.hash_contents #get the stored hash of the file contents
            #print (file.filepath,relpath,file.id,hash)
            if not check_path(_file,mycore,docstore=docstore):
                _result=False
    return _result
                
def check_path(_file,mycore,docstore=DOCSTORE):
    solrdocs=solrJson.getmeta(_file.solrid,mycore)
    _success=True
    if not solrdocs:
        print('solrdoc {} does not exists'.format(_file.solrid))
        _success=False
    for solrdoc in solrdocs:        
        docpaths_in_solr=solrdoc.data.get('docpath')
        docpath_in_database=_file.filepath
        
        assert type(docpaths_in_solr) == list       
        if docpath_in_database in docpaths_in_solr:
            #found full path
            log.debug(f'Path in database: {docpath_in_database} Paths in solr:{docpaths_in_solr}')
            print('Found full path to correct: {}'.format(docpath_in_database))
            
            #remove the fullpath
            docpaths_in_solr.remove(docpath_in_database)
            
            #relpath=file_utils.make_relpath(docpath_in_database)
            paths_are_missing,paths,p_hashes=path_changes(docpath_in_database,docpaths_in_solr,docstore=docstore)
                        
            if paths_are_missing:
                log.debug(f'Updating paths to: {paths}') 
                changes=[] 
                changes.append(('docpath','docpath',paths))
                changes.append((mycore.parenthashfield,mycore.parenthashfield,p_hashes))
            
            #make changes to the solr index
                json2post=updateSolr.makejson(solrdoc.id,changes,mycore)
                log.debug('{}'.format(json2post)) 
                response,updatestatus=updateSolr.post_jsonupdate(json2post,mycore)
                log.debug('Response: {response}, UpdateStatus: {updatestatus}')
                if updateSolr.checkupdate(solrdoc.id,changes,mycore):
                    log.debug('solr successfully updated')
                else:
                    log.debug('solr changes not successful')
                    _success=False
            else:
                log.debug('No paths to update!')
        return _success

