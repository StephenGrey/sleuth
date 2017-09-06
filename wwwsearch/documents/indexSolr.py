# -*- coding: utf-8 -*-
from bs4 import BeautifulSoup as BS
import requests, os, logging
import ownsearch.hashScan as dup
import hashlib  #routines for calculating hash
from documents.models import Collection,File
log = logging.getLogger('ownsearch')
from usersettings import userconfig as config

#from settings
solrcore=config['Cores']['coredefault'] #the name of the index to use within the Solr backend
solrurl=config['Solr']['url'] #Solr:url is the network address of Solr backend
docstore=config['Models']['collectionbasepath'] #get base path of the docstore

extractargs='commit=true'
extracturl=solrurl+solrcore+'/update/extract?'

#hlarguments=config[core]['highlightingargs']
#dfltsearchterm=config['Test']['testsearchterm']
#docpath=config[core]['docpath']
#docnamefield=config[core]['docname']
#arguments='&fl=id,date,content'
#contentarguments=config[core]['contentarguments']


"""

"""

def pathHash(path):
    m=hashlib.md5()
    m.update(path.encode('utf-8'))  #encoding avoids unicode error for unicode paths
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

def extract(path,test=False):
    if os.path.exists(path)==False: #check file exists
        print ('path '+path+' does not exist')
        return False
    if test==True:
        args=extractargs+'&extractOnly=true' #does not index on test
    else:
        relpath=os.path.relpath(path,start=docstore) #extract a relative path from the docstore
        args=extractargs+'&literal.id='+pathHash(path)+'&literal.filename='+os.path.basename(path)+'&literal.filepath='+relpath
        #>>>>go index, use MD5 of path as unique ID
        #and calculate filename to put in index
        #print ('extract args: '+args)
    sp,statusOK=postSolr(args,path) #POST TO THE INDEX
    #print sp
    if statusOK is not True:
         print ('Error in posting file with args: ',args,' and path: ',path)
         return False
    if sp.response:
        if sp.response.lst.int['name'] == 'status' and sp.response.lst.int.text == '0':
            print ('success')
            return True
    print ('Error: response is: ',sp)
    return False
    

def getSolrResponse(args):
    searchurl=extracturl+args
    #USE IF COOKIES OR LOGIN REQUIRED ses = requests.Session()
    # the session instance holds the cookie. So use it to get/post later
    #res=ses.get(searchurl)
    res=requests.get(searchurl)
    soup=BS(res.content,"html.parser")
    return soup

def postSolr(args,path):
    url=extracturl+args
    try: 
        with open(path,'rb') as f:
            file = {'myfile': f}
            res=requests.post(url, files=file)
        soup=BS(res.content,"html.parser")
        statusOK = True
        return soup, statusOK
    except Exception as e:
        print ('Exception: ',str(e))
        statusOK=False
        return '',statusOK

if __name__ == '__main__':   #
    scanpath('')
    
    

"""


"""
