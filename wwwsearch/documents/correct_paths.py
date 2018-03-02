# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from __future__ import print_function
from __future__ import absolute_import
import os, logging
log = logging.getLogger('ownsearch.correctpaths')
from . import solrcursor,updateSolr
from usersettings import userconfig as config
from ownsearch import solrJson
from .models import Collection,File,Index

def check(mycore,collection):
    print((mycore,collection))
            #main loop - go through files in the collection
            
    #get the basefilepath
    docstore=config['Models']['collectionbasepath'] #get base path of the docstore

#    #first get solrindex ids and key fields
#    try:#make a dictionary of filepaths from solr index
#        indexpaths=solrcursor.cursor(mycore)
#    except Exception as e:
#        log.warning('Failed to retrieve solr index')
#        log.warning(str(e))
#        return False

    #now compare file list with solrindex
    if True:
        counter=0
        skipped=0
        failed=0
        #print(collection)
        filelist=File.objects.filter(collection=collection)

        #main loop - go through files in the collection
        for file in filelist:
            relpath=os.path.relpath(file.filepath,start=docstore) #extract the relative path from the docstore
            hash=file.hash_contents #get the stored hash of the file contents
            #print (file.filepath,relpath,file.id,hash)
            for solrdoc in solrJson.getmeta(file.solrid,mycore):
                docpath=solrdoc.data.get('docpath')
                print (docpath)
                relpath_correct=os.path.relpath(docpath,start=docstore)
                print(relpath)
                
                if docpath!=relpath:
                    changes=[('docpath',relpath)]
                else:
                    changes=None
                if changes:
                    #make changes to the solr index
                    json2post=updateSolr.makejson(solrdoc.id,changes,mycore)
                    log.debug('{}'.format(json2post)) 
                    response,updatestatus=updateSolr.post_jsonupdate(json2post,mycore)
                    print((response,updatestatus))
                    if updateSolr.checkupdate(solrdoc.id,changes,mycore):
                        print('solr successfully updated')
                    else:
                        print('solr changes not successful')
                else:
                    print('Nothing to update!')



