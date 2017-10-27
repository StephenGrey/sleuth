# -*- coding: utf-8 -*-
from __future__ import unicode_literals, print_function
from ownsearch import solrSoup as s
from usersettings import userconfig as config
import subprocess

#EXTRACT A FILE TO SOLR INDEX (defined in mycore (instance of solrSoup.SolrCore))
#returns solrSoup.MissingConfigData error if path missing to extract.jar
def ICIJextract(path,hashcontents,mycore):
    try:
        mycore.ping() #checks the connection is alive
        result=tryextract(path,mycore)
        return result #return True on success
    except IOError as e:
        print ('File cannot be opened')
    except s.SolrConnectionError as e:
        print ('Connection error')
    return False  #if error return False

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
    result=subprocess.Popen(args, stderr=subprocess.PIPE, stdout=subprocess.PIPE,shell=False)
    output,success=parse_out(result)
#    print(output) #DEBUG : LOG IT instead
    for mtype,message in output:
        if mtype=='SEVERE':  #PRINT OUT ONLY SEVERE MESSAGES
            print (mtype+message)
    if success == True:
        print ('Successful extract')
        #commit the results
        print ('Committing ..')
        args=["java","-jar",extractpath,"commit","-s"]
        args.append(solrurl) #tests - add deliberate error
#        print (args)
        result=subprocess.Popen(args, stderr=subprocess.PIPE, stdout=subprocess.PIPE,shell=False)
#        print (result, vars(result)) #
        commitout,ignore=parse_out(result)
        if commitout==[]:
            print ('No errors from commit')
            return True 
    return False
    
def parse_out(result):
    #calling a java app produces no stdout -- but for debug, output it if any
    if result.stdout:
       sout=result.stdout.read()
       if sout != '':
           print('STDOUT from Java process: ',result.stdout.read())
    output=[]
    message=''
    ltype=''
    postsolr = False
    while True:
        line = result.stderr.readline()
        linestrip=line.rstrip()
        #print (linestrip)
        if line != '':
            if line[:5]=='INFO:':
                #dump previous message
                if message:
                    output.append((ltype,message))
                message=line[5:]
                if message[:23]==' Document added to Solr':
                    postsolr = True
                ltype='INFO'
            elif line[:8]=='WARNING:':
                #dump previous message
                if message:
                    output.append((ltype,message))                
                ltype='WARNING'
                message=line[8:]
            elif line[:7]=='SEVERE:':
                #dump previous message
                if message:
                    output.append((ltype,message))                
                ltype='SEVERE'
                message=line[7:]
            else: #NOT A HEADER
                message+=line
#            print ("test:", line.rstrip())
        else:
            break
#    print (vars(result))
#    print (output)
    return output, postsolr