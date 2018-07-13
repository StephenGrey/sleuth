# -*- coding: utf-8 -*-
import logging, re,json,requests
log = logging.getLogger('documents.api')
from django.contrib.admin.views.decorators import staff_member_required
from .models import UserEdit
from django.http import JsonResponse, HttpResponse
from django.core import serializers
from django.urls import reverse
from documents import updateSolr
from ownsearch import solrJson
from usersettings import userconfig

try:
    REMOTE_URL=userconfig['Remote']['remote_url']
    REMOTE_USER=userconfig['Remote']['django_user']
    REMOTE_PASSWORD=userconfig['Remote']['remote_url']
    TIMEOUT=int(userconfig['Remote']['timeout'])
except:
    log.info('Missing remote API settings in user configs')
    REMOTE_URL,REMOTE_USER,REMOTE_PASSWORD,TIMEOUT='','','',5

class NotFound(Exception):
    pass
    
class Updater():
    def __init__(self,remote_url=REMOTE_URL,session='',remote_startid=1):
        self.url=remote_url
        print('REMOTE',self.url)
        self.remote_startid=remote_startid
        if not session:
            self.session=requests.Session()
        else:
            self.session=session
        

    def process(self):
        updateid=self.remote_startid
        jsonstring=True
        while jsonstring != b'{"result": false}':
            jsonstring=get_api_result(self.session,self.url,updateid=updateid)
            print(jsonstring)
            process_api_result(jsonstring)
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


#RECEIVE FROM API

def get_api_result(session,url,updateid=1,selftest=False):
    if selftest:
        res=session.get(reverse('api_changes',kwargs={'user_edit_id':updateid}))
    else:
        url='{}/api/changes/{}'.format(url,updateid)
        print(url)
        res=session.get(url,timeout=TIMEOUT)
    if res.status_code == 404:
        raise NotFound("URL {} not found".format(url))
    print(res.status_code)
    return res.content

    
def process_api_result(jsonstring):
    """take API result and save to model database, set flag to update index"""
    decoded_data=deserial(jsonstring)
    for deserialized_object in decoded_data:
        set_flag(deserialized_object,attr='index_updated',value=False)
        save_or_append(deserialized_object)

def update_unprocessed(admin=False,test=False):
    cores={}
    for edit in unprocessed_edits(obj=UserEdit):
        print(edit,edit.solrid,edit.corename,deserial_taglist(edit.usertags))
        if edit.corename not in cores:
            if admin:
                cores.update({edit.corename:solrJson.SolrCore(edit.corename,test=test)})
            else:
                #check for permissions
                pass                
        
        update_edit(edit,cores,test=test)

def update_edit(edit,cores,test=False):
    core=cores[edit.corename]
    updateresult=updateSolr.updatetags(edit.solrid,core,deserial_taglist(edit.usertags),test=test)
    if not updateresult:
        print("UPDATE FAILED for edit: {}".format(edit))    

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


