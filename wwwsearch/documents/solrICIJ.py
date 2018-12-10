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

class ICIJExtractor():
    def __init__(self,path,mycore,ocr=True):
        self.path=path
        self.mycore=mycore
        self.ocr=ocr
        self.error_message=''
        
        try:
            self.mycore.ping() #checks the connection is alive
            if os.path.exists(self.path) == False:
                raise IOError
            self.tryextract()
            return #return True on success
        except IOError as e:
            log.error('File cannot be opened')
            self.error_message='Error opening file'
        except s.SolrConnectionError as e:
            log.error('Connection error')
            self.error_message='Connection error'
        self.result= False  #if error return False

    def tryextract(self):
        try:
            extractpath=config['Extract']['extractpath'] #get location of Extract java JAR
        except KeyError as e:
            raise s.MissingConfigData
        
        solrurl=self.mycore.url
        target=self.path
        #extract via ICIJ extract
        args=["java","-jar", MEM_MIN_ARG,MEM_MAX_ARG, extractpath, "spew","-o", "solr", "-s"]
        args.append(solrurl)
        
        args.extend(["--metadataPrefix","\"\""])
#        #try adding postfix to dates to fix error w old TIF files
#        args.extend(["--metadataISODatePostfix","\"Z\""])
#        
        if not self.ocr:
           args.extend(["--ocr","no"])
    
        _user,_pass=authenticate()
        if _user and _pass:
            args.extend(["-U",_user,"-P",_pass])
    
        args.append(target)
        log.debug('Extract args: {}'.format(args))
        
        process_result=subprocess.Popen(args, stderr=subprocess.PIPE, stdout=subprocess.PIPE,shell=False)
        output,success,self.error_message=parse_out(process_result)
        #log.debug(output)
        for mtype,message in output:
            if mtype=='SEVERE':  #PRINT OUT ONLY SEVERE MESSAGES
                #log.debug(f'Message type:{mtype},Message:{message}')
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
                commitout,ignore,message=parse_out(result)
                log.debug('No errors from commit')
                self.result=True
                return
            except AuthenticationError:
                log.debug('Authentication error')
                self.error_message='Authentication error'
            except NotFound:
                log.debug('Error 404 : Not Found')
                self.error_message='Error 404'
            except Exception as e:
                log.debug(e)
                self.error_message=f'Unknown error: {e}'
        self.result=False
    
def parse_out(result):
    #calling a java app produces no stdout -- but for debug, output it if any
    #log.debug(result.__dict__)
    if result.stdout:
       sout=bytes(result.stdout.read()).decode()
       if sout != '':
           print('STDOUT from Java process: {}'.format(sout))
    output=[]
    message=''
    error_message=''
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
                log.info(f'\"{message}\"')
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
                error_message=message
            else: #NOT A HEADER
                message+=line
#            print ("test:", line.rstrip())
        else:
            break
#    print (vars(result))
#    print (output)

    return output, postsolr,error_message

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
        
