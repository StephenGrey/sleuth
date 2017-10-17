# -*- coding: utf-8 -*-
from __future__ import unicode_literals, print_function
from ownsearch import solrSoup as s
from usersettings import userconfig as config
import subprocess

#EXTRACT A FILE TO SOLR INDEX (defined in mycore (instance of solrSoup.SolrCore))
#returns solrSoup.MissingConfigData error if path missing to extract.jar
def ICIJextract(path,hashcontents,mycore):
    print('trying test extract')
    try:
        mycore.ping() #checks the connection is alive
        result=tryextract(path,mycore)
        return result
    except IOError as e:
        print ('File cannot be opened')
    except s.SolrConnectionError as e:
        print ('Connection error')
    return False  #for now make every result false to force retry

def tryextract(path,mycore):
    try:
        extractpath=config['Extract']['extractpath'] #get location of Extract java JAR
    except KeyError as e:
        raise s.MissingConfigData
    solrurl=mycore.url
    target=path
    #extract via ICIJ extract
    args=["java","-jar", extractpath, "spew","-o", "solr", "-s"]
    args.append(solrurl)
    args.append(target)
    result=subprocess.call(args)
    print (result)
    if result==0:
        print ('Successful extract')
        #commit the results
        print ('Committing ..')
        args=["java","-jar",extractpath,"commit","-s"]
        args.append(solrurl)
        result=subprocess.call(args)
        if result==0:
            return True
    return False
    