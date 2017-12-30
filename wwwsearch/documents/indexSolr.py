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
def extract_test(test=True):
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
    mycore.ping()
    
    result=extract(path,hash,mycore,test=test)
    return result

def extract(path,contentsHash,mycore,test=False):
    assert isinstance(mycore,s.SolrCore)
    #print(path)
    docstore=config['Models']['collectionbasepath'] #get base path of the docstore
#    extracturl=mycore.url+'/update/extract?'
    extractargs='commit=true&wt=json'
    try:
        filenamefield=mycore.docnamefield
        hashcontentsfield=mycore.hashcontentsfield
        filepathfield=mycore.docpath
    except Exception as e:
        print ('Exception: ',str(e))
        print('core missing default fields')
        return False
    #establish connnection to solr index
    if True:
        mycore.ping()
#    except SolrConnectionError as e:
#        print('No connection')
#        return False
    if os.path.exists(path)==False: #check file exists
        print ('path '+path+' does not exist')
        return False
    if test==True:
        args=extractargs+'&extractOnly=true' #does not index on test
        print ('extract args: '+args,'path: ',path,'mycore: ',mycore)
    else:
        relpath=os.path.relpath(path,start=docstore) #extract a relative path from the docstore
        args=extractargs+'&literal.id='+pathHash(path)+'&literal.'+filenamefield+'='+os.path.basename(path)
        args+='&literal.'+filepathfield+'='+relpath+'&literal.'+hashcontentsfield+'='+contentsHash
        #>>>>go index, use MD5 of path as unique ID
        #and calculate filename to put in index
        print ('extract args: '+args,'path: ',path,'mycore: ',mycore)
    statusOK=postSolr(args,path,mycore) #POST TO THE INDEX
    if statusOK is not True:
        print ('Error in extract() posting file with args: ',args,' and path: ',path)
        log.debug('Extract test FAILED')
        return False
    else:
        log.debug('Extract test SUCCEEDED')
        return True
    
    
##turn request json response from solr api into a dictionary
#def parseresponse(jres):
#    if soup.response:
#        result={}
#        if soup.response.find_all('lst'):
#            lists={}
#            success=False
#            #parse lists in resposne
#            for lst in soup.response.find_all('lst'):
#                 tags={}
#                 for item in lst:
#                     value=''
#                     if item.name=='int':
#                         value=int(item.text)
#                     if item.name=='str':
#                         value=item.text
#                     if item.has_attr('name'):
#                         tags[item['name']]=value
#                     else:
#                         print('tag has no name attribute')
#                 lists[lst['name']]=tags
#            result['lists']=lists
#            #check for errors 
#            if 'responseHeader' in lists:
#                 header=lists['responseHeader']
#                 status=header['status']
#                 if status==0:
#                     success=True
#                     return result,success,'success'
#                 else:
#                     success=False
#            if 'error' in lists:
#                errorlist=lists['error']
#                errormessage=errorlist['msg']
#                errorcode=errorlist['code']
#                message=errormessage+'  CODE:'+str(errorcode)
#            else:
#                message='Error message not parsed'
#            #NB THERE IS A METADATA LIST THAT COULD ALSO BE PARSED AND LOGGGED
#            return result,success,message
#        return result,False,'no lists found'
#    return {},False,'no response found'

#
#def getSolrResponse(args,mycore):
#    searchurl=extracturl+args
#    #USE IF COOKIES OR LOGIN REQUIRED ses = requests.Session()
#    # the session instance holds the cookie. So use it to get/post later
#    #res=ses.get(searchurl)
#    res=requests.get(searchurl)
#    soup=BS(res.content,"html.parser")
#    return soup

#DEBUG NOTE: requests won't successfully post if unicode filenames in the header; so converted below
#should consider using basefilename not file path below
def postSolr(args,path,mycore):
    extracturl=mycore.url+'/update/extract?'
    url=extracturl+args
    print('POSTURL',url)
    try:
        simplefilename=path.encode('ascii','ignore')
    except:
        simplefilename='Unicode filename DECODE error'
    try: 
        with open(path,'rb') as f:
            file = {'myfile': (simplefilename,f)}
            res=requests.post(url, files=file)
        resstatus=res.status_code
        log.debug('RESULT STATUS: '+str(resstatus))
        solrstatus=json.loads(res._content)['responseHeader']['status']
        log.debug('SOLR STATUS: '+str(solrstatus))
        if resstatus==404:
            raise s.Solr404('404 error - URL not found')        
        if solrstatus==0 and resstatus==200:
            return True 
        else:
            raise PostFailure('Errors in posting file for extraction')
    except requests.exceptions.RequestException as e:
        log.debug('Exception in postSolr: {}{}'.format(str(e),e))
        return False
    except PostFailure as e:
        log.error(str(e))
        log.error('Post result {}'.format(res.content))
        return False
    except ValueError as e:
        log.error(str(e))
        log.debug('Post result {}'.format(res.content))
        return False

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
    
