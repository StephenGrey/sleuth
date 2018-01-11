# -*- coding: utf-8 -*-
from __future__ import unicode_literals, print_function
from ownsearch import solrJson as s
from documents import updateSolr as u
from usersettings import userconfig as config
import subprocess, logging, os
log = logging.getLogger('ownsearch.solrICIJ')

#EXTRACT A FILE TO SOLR INDEX (defined in mycore (instance of solrSoup.SolrCore))
#returns solrSoup.MissingConfigData error if path missing to extract.jar
def ICIJextract(path,mycore):
    try:
        mycore.ping() #checks the connection is alive
        if os.path.exists(path) == False:
            raise IOError
        result=tryextract(path,mycore)
        return result #return True on success
    except IOError as e:
        log.error('File cannot be opened')
    except s.SolrConnectionError as e:
        log.error('Connection error')
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
            print (mtype,message)
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
                log.info(message)
                if message[:23]==' Document added to Solr':
                    postsolr = True
                ltype='INFO'
            elif line[:8]=='WARNING:':
                #dump previous message
                if message:
                    output.append((ltype,message))                
                ltype='WARNING'
                message=line[8:]
                log.warning(message)
            elif line[:7]=='SEVERE:':
                #dump previous message
                if message:
                    output.append((ltype,message))                
                ltype='SEVERE'
                message=line[7:]
                log.error(message)
            else: #NOT A HEADER
                message+=line
#            print ("test:", line.rstrip())
        else:
            break
#    print (vars(result))
#    print (output)
    return output, postsolr

#ADD ADDITIONAL META NOT ADDED AUTOMATICALLY BY THE EXTRACT PROGRAM
def postprocess(solrid,sourcetext,hashcontents, core):
    #add source info to the extracted document
    result=u.updatetags(solrid,core,value=sourcetext,standardfield='sourcefield',newfield=False)
    if result == False:
        print('Update failed for solrID: {}'.format(solrid))
        return False
    #now add source to any children
    result=childprocess(hashcontents,sourcetext,core)
    return result
    
    
def childprocess(hashcontents,sourcetext,core):
    #also add source to child documents created
    solr_result=s.hashlookup(hashcontents, core,children=True)
    for solrdoc in solr_result.results:
        #add source info to the extracted document
        try:
            result=u.updatetags(solrdoc.id,core,value=sourcetext,standardfield='sourcefield',newfield=False)
            if result==True:
                log.info('Added source \"{}\" to child-document \"{}\", id {}'.format(sourcetext,solrdoc.docname,solrdoc.id))
            else:
                log.error('Failed to add source to child document id: {}'.format(solrdoc.id))
                return False
        except Exception as e:
            print(e)
            return False
    return True
