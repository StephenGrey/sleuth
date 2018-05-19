# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from .models import Message, PhoneNumber
from django.template.loader import render_to_string
from django.db.models import Q,Count #Count to count up unique entries
from django.utils.safestring import SafeText
from ownsearch import markup
import operator

class Conversation():
    "parse a WhatsApp conversation from Message model"""
    def __init__(self,node1='',node2='',request=''):
        self.request=request
        self.start_time=''
        self.end_time=''
        self.node1=node1
        self.node1_name,verified1=get_name(node1)
        self.node1_records=get_number_record(node1)
        self.node2=node2
        self.node2_name,verified2=get_name(node2)
        self.node2_records=get_number_record(node2)
        self.get_conversation()
        self.get_text_to_index()
#        if self.messages==[]:
#            print('No messages')
#            return
        self.get_html()
        if request != '':
            self.get_panelhtml()
        self.name="WhatsApps to/from {}({}) & {} ({})".format(self.node1_name,self.node1,self.node2_name,self.node2)
        
        """url to conversation"""
        if self.node1 and self.node2:
            self.url="/whatsapp/{}/{}".format(self.node1,self.node2)
        elif self.node1:
            self.url="/whatsapp/{}".format(self.node1)
        else:
            self.url=''
        
    def get_conversation(self):
        """filter the conversation from database"""
    	  #filter1,filter2):
        self.messages=[]
        #print('Filters {}, {}'.format(self.node1,self.node2))
        filtered=Message.objects.filter(Q(to_number=self.node1) | Q(from_number=self.node1) | Q(whatsapp_group=self.node1))
        if self.node2:
            #print('second filter {}'.format(self.node2))
            filtered=filtered.filter(Q(to_number=self.node2) | Q(from_number=self.node2) | Q(whatsapp_group=self.node2))
        
        #print(filtered[0].send_time)
        
        if filtered: #if any messages, set max / min times default to first message
            self.start_time=filtered[0].send_time
            self.end_time=filtered[0].send_time

                
            for message in filtered:    
                #print(message.to_number,message.from_number, message.whatsapp_group)
                if message.from_number=='0':
                    continue
                if message.to_number=='0':
                    message.to_number=message.whatsapp_group
                    #print(message.to_number, message.whatsapp_group)
                if message.to_number==self.node1:
                    received=True
                else:
                    received=False
                            
                #adjust start / finish dates    
                if message.send_time < self.start_time:
                    self.start_date=message.send_time
                if message.send_time > self.end_time:
                    self.end_time=message.send_time
                
                if message.from_number==self.node1:
                    sendname=self.node1_name
                elif message.from_number==self.node2:
                    sendname=self.node2_name
                else:
                    sendname,sendverified=get_name(message.from_number)	
                
                message.text_markedup=markup.urls(message.messagetext)
                
                self.messages.append((message,received,message.whatsapp_group,sendname))
        
    def get_text_to_index(self):
        """extract clean text to index"""
        self.text='FROM: {} TO: {} \n'.format(self.node1,self.node2)
        for message,received,group,sendname in self.messages:
            if received:
                self.text += 'RECEIVED:'
            else:
                self.text += 'SENT: '
            if group:
                self.text+='GROUP: {} \n'.format(group)
            self.text+='SENDER NAME: {} '.format(sendname)
            self.text+='TIME: {} '.format(message.send_time)
            self.text+='MESSAGE: {} \n'.format(message.messagetext)

            
    def get_html(self):
        """make HTML to display the conversation"""

        context={'list': self.messages,'filter1': self.node1, 'filter2':self.node2}

        self.preview_html=render_to_string('whatsapp/conversation.html',context)
    
    def get_panelhtml(self):
        context={'list': self.messages,'filter1': self.node1, 'filter2':self.node2}
        print('getting panel html')
        panel1,panel2=SafeText(),SafeText()
        if self.node1 and self.node1_records:
            context['filter']='1'
            context['filternumber']=self.node1
            context['filter_name']=self.node1_name 
            context['filter_records']=self.node1_records            	

            panel1=render_to_string('whatsapp/phonenumber_panel.html',context, request=self.request)

        if self.node2 and self.node2_records:
            context['filter']='2'
            context['filternumber']=self.node2
            context['filter_name']=self.node2_name 
            context['filter_records']=self.node2_records            	

            panel2=render_to_string('whatsapp/phonenumber_panel.html',context, request=self.request)
        panel_html=panel1+panel2
        self.phonenumber_panel_html=panel_html

def get_number_record(number):
    name_lookup=PhoneNumber.objects.filter(number=number)
    if name_lookup:
        return name_lookup[0]
    else:
        return None

def get_name(number):
    number_record=get_number_record(number)
    if number_record:
        name=getattr(number_record,'name',None)
        verified=number_record.verified
    else:
        return '',None
    if name:
        return name,verified
    else:
        return '',verified


def list_messages():
    to_numbers=Message.objects.values("to_number").distinct().annotate(n=Count("pk"))
    todict={}
    combo=[]
    for item in to_numbers:
        number=item['to_number']
        todict[number]=item['n']
        
    from_numbers=Message.objects.values("from_number").distinct().annotate(n=Count("pk"))
    
    for item in from_numbers:
        number=item['from_number']
        name,verified=get_name(number)
        combo.append((number,item['n']+todict.pop(number,0),name,verified))

    #add unique items (i.e 'to numbers' not in the 'from' list)
    for number in todict:
        name,verified=get_name(number)
        combo.append((number,todict[number],name,verified))
    
    #add group messages
    glist=list_groupmessages()
    combo +=glist
    
    #now sort it all
    combo=sorted(combo,key=operator.itemgetter(1),reverse=True)
    return combo

def list_groupmessages():
    grouplist=[]
    groups=Message.objects.values("whatsapp_group").distinct().annotate(n=Count("pk"))
    for item in groups:
        if item['whatsapp_group'] is '':
            continue
        grouplist.append((item['whatsapp_group'],item['n'],'Group',None))    
    return grouplist