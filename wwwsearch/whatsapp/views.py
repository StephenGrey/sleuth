# -*- coding: utf-8 -*-
"""
View WhatsApp conversations 

"""
from __future__ import unicode_literals
from django.shortcuts import render
from django.http import JsonResponse, HttpResponse
from django.db.models import Q,Count #Count to count up unique entries
from .models import Message, PhoneNumber
from .forms import PhoneNumberForm
import operator #for sorting
import json, logging
from .conversation import Conversation, get_name, list_messages
log=logging.getLogger('ownsearch.whatsapp.views')


def home(request):    
    """To/From list of contacts with message count"""
    try:
        combo=list_messages()
        return render(request, 'whatsapp/list.html',{'list': combo})
    except Exception as e:
        log.error('Error fetching list of WhatsApp messages: {}'.format(e))
        return HttpResponse('Error fetching list of WhatsApp messages')

def messages(request,filter1='',filter2=''):
    """Display a WhatsApp conversation"""
    try:
        log.info('User \'{}\' listing phone records with filters: {}'.format(request.user.username,filter1,filter2))    
        c=Conversation(filter1,filter2,request=request)
        if c.messages==[]:
            return HttpResponse('No messages')
        return render(request, 'whatsapp/messages.html',{'list': c.messages, 'filter1': c.node1, 'filter2':c.node2, 'filter1_name':c.node1_name, 'filter2_name':c.node2_name, 'filter2_records':c.node2_records, 'filter1_records':c.node1_records, 'preview_html':c.preview_html, 'phonenumber_panel_html': c.phonenumber_panel_html  })
    except Exception as e:
        log.error('Error fetching WhatsApp conversation: {}'.format(e))
        return HttpResponse('Error fetching WhatsApp conversation')
        

def post_namefiles(request):
    """Use Ajax to update records for WhatsApp contact"""
    errorjson={'saved':False, 'verified':False}
    try:
        if request.is_ajax():
            if request.method == 'POST':
                log.debug('Raw Data: {}'.format( request.body))
                response_json = json.dumps(request.POST)
                data = json.loads(response_json)
                log.debug ("Json data: {}.".format(data))
                postdata=request.POST
                result,verified,message=update_phonerecords(data,request.user.username,postdata)
                log.debug("Message: {}".format(message))
                print(message,type(message))
                jsonresponse = {
                'saved': result,
                'verified':verified,
                'message': message
                }
                log.debug('Json response:{}'.format(jsonresponse))
                return JsonResponse(jsonresponse)
            else:
                return JsonResponse(errorjson)
        else:
            return HttpResponse('API call: Not Ajax')
    except Exception as e:
        return JsonResponse(errorjson)


def update_phonerecords(jsondata,username,postdata):
    """update phonebook model from from data"""
    #returns Successful Update(True/False), Verified Record(True/False),Errors
    log.info('User \'{}\' updating phone records with data: {}'.format(username,jsondata))
    try:
        form=PhoneNumberForm(postdata)
        #log.debug('Form data: {}'.format(form.__dict__))
        log.debug('Data posted: {}'.format(postdata))
        
        if form.is_valid():
            log.debug('form is valid')
            log.debug('Cleaned data: {}'.format(form.cleaned_data))
            data=form.cleaned_data
            pid=postdata.get('record-ID')
            if pid=='':
                log.warning('No record found')
                return False, None,None
            existing=PhoneNumber.objects.get(id=pid)
            
            personal=data.get('personal')
            if personal=='true' and existing.personal==False:
                existing.personal=True
                personal_change=True
            elif personal=='false' and existing.personal==True:
                existing.personal=False
                personal_change=False
            else:
                personal_change=None
            verified=data.get('verified')
            if verified==True and existing.verified==False:
                existing.verified=True
                verified_change=True
            elif verified==False and existing.verified==True:
                existing.verified=False
                verified_change=False
            else:
                verified_change=None
            csrf=data.get('csrfmiddlewaretoken')
            existing.name=data['name']
            existing.name_source=data['name_source']
            existing.name_possible=data['name_possible']
            existing.notes=data['notes']
            existing.save() 
            log.info("New data saved")
            log.debug("Data saved: {}".format(existing.__dict__))
            return True,verified_change,None 
        else:
            print('form not valid; errors: {}'.format(form.errors))
            return False,False,form.errors.as_json()

    except Exception as e:
        log.error("Failed to edit phone record data with saved data: {} and error {}".format(postdata,e))
        return False,None,None

