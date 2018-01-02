# -*- coding: utf-8 -*-
from __future__ import unicode_literals
#from bs4 import BeautifulSoup as BS
from django.conf import settings
import requests, os, logging, json
import ownsearch.hashScan as dup
import hashlib  #routines for calculating hash
#from documents.models import Collection,File
log = logging.getLogger('ownsearch.indexsolr')
from usersettings import userconfig as config
from ownsearch.solrJson import SolrConnectionError
from ownsearch.solrJson import SolrCoreNotFound
from ownsearch import solrJson as s
from fnmatch import fnmatch

try:
    ignorelist=config['Solr']['ignore_list'].split(',')
except Exception as e:
    log.warning('Configuration warning: no ignore list found')
    ignorelist=[]
    
"""
EXTRACT CONTENTS OF A FILE FROM LOCAL MEDIA INTO SOLR INDEX

main method is extract(path,contentsHash,mycore,test=False)
"""

class ExtractInterruption(Exception):
    pass

class PostFailure(Exception):
    pass
    
#FILE METHODS
def pathHash(path):
    m=hashlib.md5()
    m.update(path.encode('utf-8'))  #cope with unicode filepaths; NB to work requred 'from __future__ import unicode_literals'
    return m.hexdigest()

def scanPath(parentFolder):  #recursively check all files in a file folder and get specs 
    if os.path.exists(parentFolder)==True: #check the folder exists
        filedict=dup.HexFolderTable(parentFolder)
        #print ('filedict',filedict)
        for hexfile in filedict:
        #hexfile is a list of duplicate files [[path,filelen,shortName,fileExt,modTime]...,[]]
            path=filedict[hexfile][0][0]
            #print (hexfile,path)
            result=extract(path)
            if result is True:
                log.info ('PATH :'+path+'indexed successfully')


#SOLR METHODS
def extract_test(test=True,timeout=''):
    #get path to test file
    path=settings.BASE_DIR+'/tests/testdocs/TESTFILE_BBCNews1.pdf'
    assert os.path.exists(path)
    print(config['Solr'])
    
    #get hash
    hash=dup.hashfile256(path)
    print(hash)
    
    #get default index
    defaultID=config['Solr']['defaultcoreid']
    cores=s.getcores()
    mycore=cores[defaultID]
    #checks solr index is alive
    log.debug('Testing extract to {}'.format(mycore.name))
    mycore.ping()
    
    result=extract(path,hash,mycore,test=test,timeout=timeout)
    return result

#extract a path to solr index (mycore), storing hash of contents (avoiding timewasting recompute, optional testrun, timeout); throws exception if no connection to solr index, otherwise failures return False
def extract(path,contentsHash,mycore,test=False,timeout=''):
    try:
        assert isinstance(mycore,s.SolrCore)
        assert os.path.exists(path) #check file exists
    except AssertionError:
        log.debug ('Extract: bad parameters: {},{}'.format(path,mycore))
        return False
    #establish connnection to solr index
    mycore.ping() #       throws a SolrConnectionError if solr is down; throw error to higher level.
    try: 
        docstore=config['Models']['collectionbasepath'] #get base path of the docstore
        #load default timeout unless specified
        if timeout=='':
            timeout=float(config['Solr']['solrtimeout'])
    except KeyError:
        log.error ('Missing data in solr config')
        return False
    try:
        filenamefield=mycore.docnamefield
        hashcontentsfield=mycore.hashcontentsfield
        filepathfield=mycore.docpath
    except AttributeError as e:
        log.error('Exception: {}'.format(e))
        log.error('Solr index is missing default fields')
        return False
#    extracturl=mycore.url+'/update/extract?'
    extractargs='commit=true&wt=json'
    if test==True:
        args=extractargs+'&extractOnly=true' #does not index on test
        print ('Testing extract args: '+args,'path: ',path,'mycore: ',mycore)
    else:
        #>>>>go index, use MD5 of path as unique ID
        #and calculate filename to put in index
        relpath=os.path.relpath(path,start=docstore) #extract a relative path from the docstore root
        args=extractargs+'&literal.id='+pathHash(path)+'&literal.'+filenamefield+'='+os.path.basename(path)
        args+='&literal.'+filepathfield+'='+relpath+'&literal.'+hashcontentsfield+'='+contentsHash
        log.debug('extract args: {}, path: {}, solr core: {}'.format(args,path,mycore))
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
    try:
        res=s.resPostfile(url,path,timeout=timeout) #timeout=
        solrstatus=json.loads(res._content)['responseHeader']['status']
        print(res.elapsed.total_seconds())
        solrelapsed=res.elapsed.total_seconds()
    except s.SolrTimeOut as e:
        log.error('Solr post timeout ')
        return False,0
    except s.Solr404 as e:
        log.error('Error in posting 404 error - URL not workking: {}'.format(e))
        return False,0
    except s.PostFailure as e:
        log.error('Fost Failure : {}'.format(e))
        return False,0
    log.debug('SOLR STATUS: {}  ELAPSED TIME: {:.2f} secs'.format(solrstatus,solrelapsed))
    if solrstatus==0:
        return True,solrelapsed 
    else:
        return False,0

#check if filepath fits an ignore pattern (no check to see if file exists)
def ignorefile(path):
    head,filename=os.path.split(path)
    if any(fnmatch(filename, pattern) for pattern in ignorelist):
        print 'Ignore', filename
        return True
    else:
        return False

def ignorepath(parentFolder):
    ignorefiles=[]
    assert os.path.exists(parentFolder)
    for dirName, subdirs, fileList in os.walk(parentFolder): #go through every subfolder in a folder
        #print('Scanning %s...' % dirName)
        for filename in fileList: #now through every file in the folder/subfolder
            if any(fnmatch(filename, pattern) for pattern in ignorelist):
                print 'Ignore', filename, os.path.abspath(filename)
                ignorefiles.append((filename, os.path.abspath(filename)))
                continue
    return ignorefiles


if __name__ == '__main__':   #
    scanpath('')
    
