# -*- coding: utf-8 -*-
from __future__ import unicode_literals, print_function
from builtins import str
from ownsearch import solrJson as s
from documents import updateSolr as u
from documents import file_utils
from configs import config
import subprocess, logging, os,shlex, time, re
log = logging.getLogger('ownsearch.solrICIJ')


try:
    TIMEOUT=int(config['Solr']['solrtimeout'])
except:
    log.info('No timeout value stored in configs')
    TIMEOUT=600 #seconds

try:
    MEM_MIN=int(config['Extract']['memory_min'])
    MEM_MAX=int(config['Extract']['memory_max'])
except:
    log.info('No memory max-min values stored in configs')
    MEM_MIN=512
    MEM_MAX=1024

MEM_MIN_ARG=f"-Xms{MEM_MIN}m"
MEM_MAX_ARG=f"-Xmx{MEM_MAX}m"

class AuthenticationError(Exception):
    pass

class NotFound(Exception):
    pass

class TimedOut(Exception):
    pass

#EXTRACT A FILE TO SOLR INDEX (defined in mycore (instance of solrSoup.SolrCore))
#returns solrSoup.MissingConfigData error if path missing to extract.jar


class OutParser():
    def __init__(self):
        self._message=''
        self.log_message=''
        self.success=False
        self.error_message=''
        
    def process(self,_line):
        #log.debug(_line)
        if self.is_time(_line):
            #log.debug('date registered')
            self.output() #new log message, output previous
            self._message=''
            self.log_message=''
        self.logger(_line)
        self._message+=_line+'\t'
        
    def output(self):
        if self._message:
            #log.debug(self.log_message)
            #log.debug(self._message)
            self.parse()
            self.log_out()
                
    def parse(self):
        if 'Document added to Solr' in self._message:
            self.success=True
            self.log_message='WARNING'
        elif 'Error 401' in self._message:
            raise AuthenticationError
        elif 'Error 404' in self._message:
            raise NotFound
        elif "not a valid OOXML (Office Open XML) file" in self._message:
            self.error_message='ICIJ ext: not valid OOXML file'
        
        elif 'The tikaDocument could not be parsed' in self._message:
            self.error_message='ICIJ ext: parse failure'
        elif 'The extraction result could not be outputted' in self._message:
            self.error_message='ICIJ ext: Solr output fail' 
            
    
    def logger(self,_text):
        try:
            error=re.match('[A-Z]*:',_text[:10])[0][:-1]
            if error in ('INFO', 'WARNING','ERROR','SEVERE','CRITICAL','WARNING','WARN','DEBUG','FATAL','TRACE'):
                self.log_message=error
        except:
            pass
    
    def log_out(self):
        if self.log_message:
            if self.log_message=='ERROR' or self.log_message=='FATAL' or self.log_message=='SEVERE':
               log.error(f'Extract log: {self._message}')
            elif self.log_message=='DEBUG' or self.log_message=='INFO':
               log.debug(f'Extract log: {self._message}')
            else:
               log.info(f'Extract log: {self._message}')
               

    @staticmethod
    def is_time(_text):
        return re.match(r'.*,*.\d:\d\d?:\d\d? (AM|PM)',_text[:25])


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
            if not self.success and not self.error_message:
                self.error_message='ICIJ extract fail'
            return #return True on success
        except IOError as e:
            log.error('File cannot be opened')
            self.error_message='Error opening file'
        except s.SolrConnectionError as e:
            log.error('Connection error')
            self.error_message='Connection error'
        except TimedOut:
            log.error('Timed Out in ICIJ extractor')
            self.error_message='Timed out in ICIJ extractor'
        self.result= False  #if error return False

    def tryextract(self):
        try:
            extractpath=config['Extract']['extractpath'] #get location of Extract java JAR
            assert os.path.exists(extractpath)
        except KeyError as e:
            raise s.MissingConfigData
        except AssertionError as e:
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

        self.run_command(args)
        self.success=self.log_parser.success
        self.error_message=self.log_parser.error_message
        
        if self.success == True:
            log.info('Successful extract')
            #commit the results
            log.debug ('Committing ..')
            args=["java","-jar",extractpath,"commit","-s"]
            args.append(solrurl) #tests - add deliberate error
    
            if _user and _pass:
                args.extend(["-U",_user,"-P",_pass])
            
            try:
                #result=subprocess.Popen(args, stderr=subprocess.PIPE, stdout=subprocess.PIPE,shell=False)
                #commitout,ignore,message=parse_out(result)
                self.run_command(args)
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
        
    def run_command(self,args):
        process = subprocess.Popen(args,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        #shlex.split(command) TODO
        _timeout=time.time()+TIMEOUT
        self.log_parser=OutParser()
        while True:
            output = process.stderr.readline()
            _poll=process.poll()
            #log.debug(output)
#            log.debug(_poll)
            if not _poll:
                time.sleep(0.05) #if nothing going on, spare the CPU
            if output == '' and _poll is not None:
                break
            elif output == b'' and _poll ==0:
                break
            if output:
                line=output.decode().strip() #convert bytes to string; strip white space
                #log.debug(line)
                self.log_parser.process(line)
            if time.time()>_timeout:
                process.kill()
                raise TimedOut('Extract process killed after TimeOut')
        self.log_parser.output()
        rc = process.poll()
        self.rc=rc


    
def parse_out(result):
    #calling a java app produces no stdout -- but for debug, output it if any
    #log.debug(result.__dict__)
    if result.stdout:
       sout=bytes(result.stdout.read()).decode()
       if sout != '':
           log.debug('STDOUT from Java process: {}'.format(sout))
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
        
