# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from bs4 import BeautifulSoup as BS
import requests, os, logging
import ownsearch.hashScan as dup
import hashlib  #routines for calculating hash
from documents.models import Collection,File
log = logging.getLogger('ownsearch')
from usersettings import userconfig as config
from ownsearch.solrSoup import SolrConnectionError
from ownsearch.solrSoup import SolrCoreNotFound
from fnmatch import fnmatch

try:
    ignorelist=config['Solr']['ignore_list'].split(',')
except Exception as e:
    print('Configuration warning: no ignore list found')
    ignorelist=[]
    
"""
EXTRACT CONTENTS OF A FILE FROM LOCAL MEDIA INTO SOLR INDEX

main method is extract(path,contentsHash,mycore,test=False)
"""

class ExtractInterruption(Exception):
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
                print ('PATH :'+path+'indexed successfully')


#SOLR METHODS
def extract(path,contentsHash,mycore,test=False):
    #print(path)
    docstore=config['Models']['collectionbasepath'] #get base path of the docstore
#    extracturl=mycore.url+'/update/extract?'
    extractargs='commit=true'
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
    else:
        relpath=os.path.relpath(path,start=docstore) #extract a relative path from the docstore
        args=extractargs+'&literal.id='+pathHash(path)+'&literal.'+filenamefield+'='+os.path.basename(path)
        args+='&literal.'+filepathfield+'='+relpath+'&literal.'+hashcontentsfield+'='+contentsHash
        #>>>>go index, use MD5 of path as unique ID
        #and calculate filename to put in index
        #print ('extract args: '+args,'path: ',path,'mycore: ',mycore)
    sp,statusOK=postSolr(args,path,mycore) #POST TO THE INDEX
    #print (sp)
    if statusOK is not True:
        print ('Error in extract() posting file with args: ',args,' and path: ',path)
        print ('Response from solr:',sp)
        return False
    response,success,message=parseresponse(sp) #turn the response into a dictionary
    if success is True:
        print(message)
        return True
    else:
        print(message,response)
        return False
    
#turn request xml response from solr api into a dictionary
def parseresponse(soup):
    if soup.response:
        result={}
        if soup.response.find_all('lst'):
            lists={}
            success=False
            #parse lists in resposne
            for lst in soup.response.find_all('lst'):
                 tags={}
                 for item in lst:
                     value=''
                     if item.name=='int':
                         value=int(item.text)
                     if item.name=='str':
                         value=item.text
                     if item.has_attr('name'):
                         tags[item['name']]=value
                     else:
                         print('tag has no name attribute')
                 lists[lst['name']]=tags
            result['lists']=lists
            #check for errors 
            if 'responseHeader' in lists:
                 header=lists['responseHeader']
                 status=header['status']
                 if status==0:
                     success=True
                     return result,success,'success'
                 else:
                     success=False
            if 'error' in lists:
                errorlist=lists['error']
                errormessage=errorlist['msg']
                errorcode=errorlist['code']
                message=errormessage+'  CODE:'+str(errorcode)
            else:
                message='Error message not parsed'
            #NB THERE IS A METADATA LIST THAT COULD ALSO BE PARSED AND LOGGGED
            return result,success,message
        return result,False,'no lists found'
    return {},False,'no response found'


def getSolrResponse(args,mycore):
    searchurl=extracturl+args
    #USE IF COOKIES OR LOGIN REQUIRED ses = requests.Session()
    # the session instance holds the cookie. So use it to get/post later
    #res=ses.get(searchurl)
    res=requests.get(searchurl)
    soup=BS(res.content,"html.parser")
    return soup

#DEBUG NOTE: requests won't successfully post if unicode filenames in the header; so converted below
#should consider using basefilename not file path below
def postSolr(args,path,mycore):
    extracturl=mycore.url+'/update/extract?'
    url=extracturl+args
    #print('POSTURL',url)
    try:
        simplefilename=path.encode('ascii','ignore')
    except:
        simplefilename='Unicode filename DECODE error'
    try: 
        with open(path,'rb') as f:
            file = {'myfile': (simplefilename,f)}
            res=requests.post(url, files=file)
        soup=BS(res.content,"html.parser")
        statusOK = True
        return soup, statusOK

    except requests.exceptions.RequestException as e:
        print ('Exception in postSolr: ',str(e),e)
        statusOK=False
        return '',statusOK

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
    
