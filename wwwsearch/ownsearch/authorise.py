# -*- coding: utf-8 -*-
"""
Authorise actions

"""
from __future__ import unicode_literals
from __future__ import print_function
from __future__ import absolute_import
from django.contrib.auth.models import User
from . import solrJson
from documents.models import File,Index,Collection
import logging,os
log = logging.getLogger('ownsearch.authorise')
from configs import config

try:
    DEFAULTCORE=config['Solr']['defaultcore']
except Exception as e:
    DEFAULTCORE=''
    log.debug('No default core set in userconfigs')

class NoValidCore(Exception):
    pass

class AuthorisedCores:
    """Check authorised indexes; from these choose stored core, else default, else any authorised"""
    def __init__(self,thisuser,storedcore=''):
        if True:
           self.cores,self.defaultcore,self.choice_list=authcores(thisuser)
           self.mycoreID=getcore(self.cores,storedcore,self.defaultcore)
           self.mycore=self.cores[self.mycoreID]
#        except Exception as e:
#           log.debug('Error: {}'.format(e.__dict__))
        log.debug('authcores: {}'.format(self.__dict__))

##set up solr indexes
def authcores(thisuser):
    """return dictionary of authorised indexes, a default ID, a list of authorised choices"""
    cores={}
    choice_list=() 

    groupids=[group.id for group in thisuser.groups.all()]
    log.debug('authorised groups for user: '+str(groupids))

    corelist=(Index.objects.filter(usergroup_id__in=groupids))
    log.debug('authorised core list '+str(corelist))
    
    
    ##make a choice list (ID, displayname) of authorised cores
    for core in corelist:
        cores[core.id]=solrJson.SolrCore(core.corename)
        corenumber=str(core.id)
        coredisplayname=core.coreDisplayName
        choice_list +=((corenumber,coredisplayname),) #value/label

    #calculate ID of authorised default core
    try:
        defaultcore=corelist.get(corename=DEFAULTCORE)
        defaultcoreID=defaultcore.id
    
    except Index.DoesNotExist:
        log.debug('Default core ('+str(DEFAULTCORE)+') set in userconfigs is not found in authorised indexes: first available is made default')
        try:
            #log.debug(str(cores)+' '+str(choice_list))
            defaultcoreID=int(choice_list[0][0])#if no default found, take first in list as new default

        except Exception as e:
            log.error('No valid and authorised index set in database: fix in /admin interface')
            log.debug(f"{e}")
            raise NoValidCore            
    return cores, defaultcoreID, choice_list

def getcore(cores,storedcore,defaultcore):
        if storedcore in cores:
            mycoreID=storedcore
        else:
            if defaultcore:
                mycoreID=defaultcore
            else:
                log.warning('Cannot find any valid coreID in authorised corelist')
                raise NoValidCore
        return mycoreID


#CHECK IF FILE WITH SAME HASH EXISTS IN DATABASE, AUTHORISED FOR DOWNLOAD AND IS PRESENT ON  MEDIA
def authfile(request,hashcontents,docname,acceptothernames=True):
    matchfiles=File.objects.filter(hash_contents=hashcontents) #find local registered files by hashcontents
    if matchfiles:
        log.debug('hashcontents: '+hashcontents)    
    #get authorised cores
        #user groups that user belongs to
        authgroupids=[group.id for group in request.user.groups.all()]
        log.debug('authorised groups for user: '+str(authgroupids))
        #indexes that user is authorised for
        authcoreids=[core.id for core in Index.objects.filter(usergroup_id__in=authgroupids)]
        log.debug(str(authcoreids)+'.. cores authorised for user')
        
    #find authorised file
        altlist=[]
        for f in matchfiles:
            fcore=Collection.objects.get(id=f.collection_id).core_id  #get core of database file
            if fcore in authcoreids and os.path.exists(f.filepath) and docname==f.filename:
                #FILE AUTHORISED AND EXISTS LOCALLY
                log.debug('matched authorised file'+f.filepath)
                return True,f.id,f.hash_filename
            
            #finding authorised file that match hash and exist locally but have different filename
            elif fcore in authcoreids and os.path.exists(f.filepath):
                altlist.append(f)
         #if no filenames match, return a hashmatch
        if acceptothernames and altlist:
            log.debug('hashmatches with other filenames'+str(altlist))
            #return any of them
            log.debug('returning alternative filename match'+altlist[0].filepath)
            return True,altlist[0].id,altlist[0].hash_filename

    return False,'',''
        
def authid(request,doc):
    coreid=Collection.objects.get(id=doc.collection_id).core_id
    #user groups that user belongs to
    authgroupids=[group.id for group in request.user.groups.all()]
    #indexes that user is authorised for
    authcoreids=[core.id for core in Index.objects.filter(usergroup_id__in=authgroupids)]
    if coreid in authcoreids:
        return True
    else:
        return False
        
def test(testuser='admin',storedcore=1):

    thisuser = User.objects.get(username=testuser)
    

    print(a,b,c)
    #test authcores
    acores=AuthorisedCores(thisuser,storedcore=storedcore)
    
    print(acores.__dict__)
    



