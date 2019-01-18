# -*- coding: utf-8 -*-
import logging, re,json,requests,getpass
log = logging.getLogger('documents.api')
from django.contrib.admin.views.decorators import staff_member_required
from .models import UserEdit,SyncStatus
from django.http import JsonResponse, HttpResponse
from django.core import serializers
from django.urls import reverse
from documents import updateSolr
from ownsearch import solrJson
from configs import config as userconfig

LOGIN_URL="/admin/login/"
API_URL="/documents/api/changes/"

log.info('launching API')
from watcher import watch_dispatch

try:
    REMOTE_URL=userconfig['Remote']['remote_url']
    REMOTE_USER=userconfig['Remote']['django_user']
    REMOTE_PASSWORD=userconfig['Remote']['remote_password']
    TIMEOUT=int(userconfig['Remote']['timeout'])
except:
    log.info('Missing remote API settings in user configs')
    REMOTE_URL,REMOTE_USER,REMOTE_PASSWORD,TIMEOUT='','','',5

class NotFound(Exception):
    pass
    
class Updater():
    def __init__(self,remote_url=REMOTE_URL,session='',remote_startid='',remote_user=REMOTE_USER,remote_password=REMOTE_PASSWORD):
        self.url=remote_url
        self.logged_in=False
        self.remote_password=remote_password
        self.remote_user=remote_user
        if not remote_startid:
            self.remote_startid=self.last_remoteid
        else:
            self.remote_startid=remote_startid
     
        if not session:
            self.session=requests.Session()
            if self.remote_user and self.remote_password:                
                self.log_in()
        else:
            self.session=session
            self.logged_in=True
    
    @property
    def last_remoteid(self):
        status,result=SyncStatus.objects.get_or_create(pk=1)
        return status.remote_useredit_lastid
    
    def log_in(self):
        try:
            geturl='{}{}'.format(REMOTE_URL,LOGIN_URL)
            #print(geturl)
            csrftoken=self.session.get(geturl).cookies.get_dict()['csrftoken']
            #print(csrftoken)
            
            headers={'X-CSRFToken': csrftoken, 'Referer': '{}/documents/api/changes/1'.format(REMOTE_URL)}
            posturl='{}{}?next={}1'.format(REMOTE_URL,LOGIN_URL,API_URL)
            #print(posturl)
            response=self.session.post(posturl,data={'username':self.remote_user,'password':self.remote_password},headers=headers)
            #print(response.__dict__)
            assert response.url=='{}/documents/api/changes/1'.format(REMOTE_URL)
            assert response.status_code==200
            self.logged_in=True        
        except Exception as e:
            log.debug(e)
            self.logged_in=False

    def process(self,test=False):
        if self.logged_in:
            self.import_loop(test=test)
            if self.lastremoteid != self.remote_startid:
                update_lastsync(self.lastremoteid) 
        else:
            print('Not logged in: NOT importing from API')
        #print(UserEdit.objects.all())

        #update local solr index
        update_unprocessed(admin=True,test=test)
    
    def import_loop(self,test=False):
        updateid=self.remote_startid
        
        self.lastremoteid=self.remote_startid
        jsonstring=True
        while jsonstring and jsonstring != b'{"result": false}':
            jsonstring=get_api_result(self.session,self.url,updateid=updateid)
            #print(jsonstring)
            try:
                process_api_result(jsonstring,test=test)
                self.lastremoteid=updateid
            except serializers.base.DeserializationError:
                print('Not decoded')
#                break        
            updateid+=1

        
    
    def ping_remote():
        pass
        
#SEND FROM API
@staff_member_required()
def api_changes(request,user_edit_id=1):
    """request user edits as json"""
    return HttpResponse(api_changes_json(user_edit_id=user_edit_id))

def api_changes_json(user_edit_id=1):
    error_data={'result':False}    
    try:
        record=UserEdit.objects.filter(id=user_edit_id)
        if record:
            jsondata=data = serializers.serialize('json', record) #, fields=('name','size'))
        #data.update({'result':True})
        else:
            jsondata=json.dumps(error_data)
    except Exception as e:
        jsondata=json.dumps({'error':'{}'.format(e)})
    return jsondata


@staff_member_required()
def api_task_progress(request,job):
    """API to check progress of task"""
    jsonresponse={'error':True, 'results':None,'message':f'Unknown error checking task {job}'}    
    try:
        if job.startswith('SB_TASK.CollectionScanAndExtract.'):
            #print(job)
            #print(watch_dispatch.r.hget(job,'sub_job_id'))
            sub_job_id=watch_dispatch.r.hget(job,'sub_job_id')
            if sub_job_id:
                sub_job='SB_TASK.'+sub_job_id
                results=watch_dispatch.r.hgetall(sub_job)
                results.update({'master_job': job})
            else:
                results=watch_dispatch.r.hgetall(job)
            results.update({'master_task':'scan_and_extract'})
            results.update({'master_task_status':watch_dispatch.r.hget(job,'status')})
        else:
            results=watch_dispatch.r.hgetall(job)
        log.debug(f'{job},{results}')
        #print(job,results)
        #{'counter':ext.counter,'skipped':ext.skipped,'failed':ext.failed,'failed_list':ext.failedlist})
        jsonresponse={'error':False, 'results':results,'message':'done'}
    except Exception as e:
        log.debug(e)
        #print(f'Error {e}')
    return JsonResponse(jsonresponse)

@staff_member_required()
def api_clear_tasks(request):
    """clear task from session"""
    log.debug('clearing tasks')
    request.session['tasks']=''
    return JsonResponse({'error':False})

@staff_member_required()
def api_check_redis(request):
    jsonresponse={'error':False}
    try:
        return JsonResponse({'redis_alive':redis_check()})
    except Exception as e:
        log.error(e)
        return JsonResponse({'redis_alive':'error'})

def redis_check():
    return watch_dispatch.r.ping()
    
    
@staff_member_required()
def api_check_taskmanager(request):
    pass
    
def taskmanager_check():
    return watch_dispatch.HBEAT.alive
    
    
    
	
	
	
#RECEIVE FROM API

def get_remotechanges(test=False,remote_startid=''):
    u=Updater(remote_password=getpass.getpass(prompt="Remote admin password"),remote_startid=remote_startid)
    u.process(test)

def get_api_result(session,url,updateid=1,selftest=False):
    if selftest:
        res=session.get(reverse('api_changes',kwargs={'user_edit_id':updateid}))
    else:
        url='{}/documents/api/changes/{}'.format(url,updateid)
        res=session.get(url,timeout=TIMEOUT)
    if res.status_code == 404:
        raise NotFound("URL {} not found".format(url))
    #print(res.content)
    return res.content
    
def process_api_result(jsonstring,test=False):
    """take API result and save to model database, set flag to update index"""
    decoded_data=deserial(jsonstring)
    for deserialized_object in decoded_data:
        log.debug('API result: {} in index {}'.format(deserialized_object.object,deserialized_object.object.corename))
        set_flag(deserialized_object,attr='index_updated',value=False)
        save_or_append(deserialized_object)

def update_unprocessed(admin=False,test=False):
    """update solr index with unprocessed edits"""
    cores={}
    edits=unprocessed_edits(obj=UserEdit)
    if not edits:
        log.debug('No new edits to process')
        return
    for edit in edits:
        log.debug('\n\nProcessing edit: {}'.format(edit))
        #print(edit.__dict__)
        new_taglist=deserial_taglist(edit.usertags)
#        print(edit)

        if edit.corename not in cores:
            if admin:
                cores.update({edit.corename:solrJson.SolrCore(edit.corename,test=test)})
            else:
                #check for permissions before edit
                break                  
        
        #check existing entry
        core=cores[edit.corename]
        try:
            existing_list=solrJson.getfield(edit.solrid,core.usertags1field,core)
            existing_list=[existing_list] if not isinstance(existing_list,list) else existing_list
            
            log.debug('Existing tags: {}  Changed tags: {}'.format(existing_list,new_taglist))
            if new_taglist!=existing_list:
                #now update solr
                goahead=input('Make change? (y/n)')
                if goahead[0]=='y' or goahead[0]=='Y':
                    #make change
                    result=update_edit(edit,cores,test=test)
                    if result:
                        #print('Changes made')
                        if not test:
                            edit.index_updated=True
                            edit.save()
                    else:
                        log.debug("UPDATE FAILED for edit: {}".format(edit))
                else:
                    #mark change ignored
                    if not test:
                        edit.index_updated=True
                        edit.save()
            else:
                log.debug('Identical: no update required')
                edit.index_updated=True
                edit.save()
                
            
        except solrJson.Solr404:
            existing_list=[]
            log.debug('Local index \"{}\" not available'.format(edit.corename))
            if not test:
                edit.index_updated=True
                edit.save()
            
        except solrJson.SolrDocNotFound:
            log.debug('Solr doc in edit not found - set edit as ignored')
            #mark change ignored
            if not test:
                edit.index_updated=True
                edit.save()
        
def update_edit(edit,cores,test=False):
    core=cores[edit.corename]
    return updateSolr.updatetags(edit.solrid,core,deserial_taglist(edit.usertags),test=test)            
def unprocessed_edits(obj=UserEdit):
    return getattr(obj,'objects').filter(index_updated=False)
    
        
def deserial(jsonstring):
    """list of decoded objects"""
    return [deserialized_object for deserialized_object in serializers.deserialize("json", jsonstring)]

def deserial_taglist(list_as_string):
    """convert list stored as string in a model into a python list"""
    if list_as_string:
        try:
            liststring_raw=re.match('\[(.*)\]',list_as_string)[1]
            liststring=re.split(',',liststring_raw)
            return [re.match('(\s?)u?\'(.*)\'',tag_raw)[2] for tag_raw in liststring]
        except TypeError:
            return []
    else:
        return []

def set_flag(this_object,value=True,attr='index_updated'):
    setattr(this_object,attr,value)
        
def savecheck(model_object,obj=UserEdit):
    """check if doc with same primary key exists in database"""
    try:
        pk=model_object.object.pk
        if getattr(obj,'objects').get(pk=pk):
            return False
        return True
    except Exception as e:
        log.debug(e)
        return False

def changes_append(change_object,obj=UserEdit):
    #alter imported object primary key 
    change_object.object.pk=getattr(obj,'objects').latest('pk').pk+1
    change_object.save()

def save_or_append(change_object):
    if savecheck(change_object):
        change_object.save()
    else:
        changes_append(change_object)

def update_lastsync(lastid):
    status,result=SyncStatus.objects.get_or_create(pk=1)
    status.remote_useredit_lastid=lastid

