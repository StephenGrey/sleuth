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

DOCSTORE=file_utils.DOCSTORE

def check_solrpaths(mycore,collection):
    #print((mycore,collection))            
    #get the basefilepath
    #docstore=config['Models']['collectionbasepath'] #get base path of the docstore
    #now compare file list with solrindex
    if True:
        filelist=File.objects.filter(collection=collection)
        #main loop - go through files in the collection
        for file in filelist:
            relpath=os.path.relpath(file.filepath,start=DOCSTORE) #extract the relative path from the docstore
            hash=file.hash_contents #get the stored hash of the file contents
            #print (file.filepath,relpath,file.id,hash)
            check_path(file,mycore)
                
def check_path(file,mycore):
    solrdocs=solrJson.getmeta(file.solrid,mycore)
    if not solrdocs:
        print('solrdoc {} does not exists'.format(file.solrid))
    for solrdoc in solrdocs:        
        docpathes_in_solr=solrdoc.data.get('docpath')
        docpath_in_database=file.filepath
        
        assert type(docpathes_in_solr) == list       
        if docpath_in_database in docpathes_in_solr:
            #found full path
            log.debug(f'Path in database: {docpath_in_database} Paths in solr:{docpathes_in_solr}')
            print('Found full path to correct: {}'.format(docpath_in_database))
            
            #remove the fullpath
            
            #add relative path
            
#        if docpath!=relpath:
#            changes=[('docpath',relpath)]
#        else:
#            changes=None
#        if changes:
#            #make changes to the solr index
#            json2post=updateSolr.makejson(solrdoc.id,changes,mycore)
#            log.debug('{}'.format(json2post)) 
#            #response,updatestatus=updateSolr.post_jsonupdate(json2post,mycore)
#            print((response,updatestatus))
#            if updateSolr.checkupdate(solrdoc.id,changes,mycore):
#                print('solr successfully updated')
#            else:
#                print('solr changes not successful')
        else:
            pass
            #print('Nothing to update!')


