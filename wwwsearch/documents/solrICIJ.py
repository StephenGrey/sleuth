# -*- coding: utf-8 -*-
from __future__ import unicode_literals, print_function
from builtins import str
from ownsearch import solrJson as s
from documents import updateSolr as u
from documents import file_utils
from configs import config
import subprocess, logging, os
log = logging.getLogger('ownsearch.solrICIJ')

MEM_MIN_ARG="-Xms512m"
MEM_MAX_ARG="-Xmx2048m"

class AuthenticationError(Exception):
    pass

class NotFound(Exception):
    pass

#EXTRACT A FILE TO SOLR INDEX (defined in mycore (instance of solrSoup.SolrCore))
#returns solrSoup.MissingConfigData error if path missing to extract.jar
def ICIJextract(path,mycore,ocr=True):
    try:
        mycore.ping() #checks the connection is alive
        if os.path.exists(path) == False:
            raise IOError
        result=tryextract(path,mycore,ocr=ocr)
        return result #return True on success
    except IOError as e:
        log.error('File cannot be opened')
    except s.SolrConnectionError as e:
        log.error('Connection error')
    return False  #if error return False

def tryextract(path,mycore,ocr=True):
    try:
        extractpath=config['Extract']['extractpath'] #get location of Extract java JAR
    except KeyError as e:
        raise s.MissingConfigData
    
    
    
    solrurl=mycore.url
    target=path
    #extract via ICIJ extract
    args=["java","-jar", MEM_MIN_ARG,MEM_MAX_ARG, extractpath, "spew","-o", "solr", "-s"]
    args.append(solrurl)

    if not ocr:
       args.extend(["--ocr","no"])

    _user,_pass=authenticate()
    if _user and _pass:
        args.extend(["-U",_user,"-P",_pass])

    args.append(target)
    log.debug('Extract args: {}'.format(args))
    result=subprocess.Popen(args, stderr=subprocess.PIPE, stdout=subprocess.PIPE,shell=False)
    output,success=parse_out(result)
#    print(output) #DEBUG : LOG IT instead
    for mtype,message in output:
        if mtype=='SEVERE':  #PRINT OUT ONLY SEVERE MESSAGES
            log.debug(f'Message type:{mtype},Message:{message}')
            if "Expected mime type application/octet-stream but got text/html" in message:
                log.debug('Unexpected response')
                if "<title>Error 401 require authentication</title>" in message:
                    log.debug('Authentication error')
                    raise AuthenticationError
    if success == True:
        log.info('Successful extract')
        #commit the results
        log.debug ('Committing ..')
        args=["java","-jar",extractpath,"commit","-s"]
        args.append(solrurl) #tests - add deliberate error

        if _user and _pass:
            args.extend(["-U",_user,"-P",_pass])
        
        try:
            result=subprocess.Popen(args, stderr=subprocess.PIPE, stdout=subprocess.PIPE,shell=False)
#        print (result, vars(result)) #
            commitout,ignore=parse_out(result)
            log.debug('No errors from commit')
            return True 
        except AuthenticationError:
            log.debug('Authentication error')
        except NotFound:
            log.debug('Error 404 : Not Found')
        except Exception as e:
            log.debug(e)
    return False
    
def parse_out(result):
    #calling a java app produces no stdout -- but for debug, output it if any
    #log.debug(result.__dict__)
    if result.stdout:
       sout=bytes(result.stdout.read()).decode()
       if sout != '':
           print('STDOUT from Java process: {}'.format(sout))
    output=[]
    message=''
    ltype=''
    postsolr = False
    while True:
        line = bytes(result.stderr.readline()).decode()
        log.debug(f'{line}')
        if line != '':
            linestrip=line.rstrip()
            #print (linestrip)
            if 'Error 401' in message:
                    raise AuthenticationError
            elif 'Error 404' in message:
                raise NotFound
            if line[:5]=='INFO:':
                
                #dump previous message
                if message:
                    output.append((ltype,message))
                message=line[5:]
                #log.info(f'\"{message}\"')
                if 'Document added to Solr' in message:
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

#def add_source(solrid,sourcetext,hashcontents, core):
#    """ADD ADDITIONAL META NOT ADDED AUTOMATICALLY BY THE EXTRACT METHOD"""
#    #add source info to the extracted document
#    result=u.updatetags(solrid,core,value=sourcetext,field_to_update='sourcefield',newfield=False)
#    if result == False:
#        print('Update failed for solrID: {}'.format(solrid))
#        return False
#    
#
#    #now add source to any children
#    result=childprocess(hashcontents,sourcetext,core)
#    return result
#    
    
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
    
    
def authenticate():
    try:
        return s.SOLR_USER, s.SOLR_PASSWORD
    except:
        return Null, Null
        
        