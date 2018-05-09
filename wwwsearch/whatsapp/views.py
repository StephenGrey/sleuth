# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from django.shortcuts import render
from django.http import HttpResponse
from django.db.models import Q,Count #Count to count up unique entries
from .models import Message
import operator #for sorting

def home(request):
    to_numbers=Message.objects.values("to_number").distinct().annotate(n=Count("pk"))
    todict={}
    for item in to_numbers:
        todict[item['to_number']]=item['n']
#        to_numbers=sorted([(number['to_number'],number['n']) for number in to_numbers],key=operator.itemgetter(1),reverse=True)
    from_numbers=Message.objects.values("from_number").distinct().annotate(n=Count("pk"))
    combo=[(number['from_number'],number['n']+todict.pop(number['from_number'],0)) for number in from_numbers]
    #add unique items (i.e 'to numbers' not in the 'from' list)
    for key in todict:
        combo.append((key,todict[key]))
    #now sort it all
    combo=sorted(combo,key=operator.itemgetter(1),reverse=True)

    return render(request, 'whatsapp/list.html',{'list': combo})

#    for number in [message.to_number for message in Message.objects.all()]:
#        numbers.append(number)
    return HttpResponse(combo)

def messages(request,filter1='',filter2=''):
    messages=[]
    print('Filters {}, {}'.format(filter1,filter2))
    filtered=Message.objects.filter(Q(to_number=filter1) | Q(from_number=filter1) | Q(whatsapp_group=filter1))
    if filter2:
        print('second filter {}'.format(filter2))
        filtered=filtered.filter(Q(to_number=filter2) | Q(from_number=filter2) | Q(whatsapp_group=filter2))
    for message in filtered:    
        print(message.to_number,message.from_number, message.whatsapp_group)
        if message.from_number=='0':
            continue
        if message.to_number=='0':
            message.to_number=message.whatsapp_group
            print(message.to_number, message.whatsapp_group)
        if message.to_number==filter1:
            received=True
        else:
            received=False
        messages.append((message,received))
    return render(request, 'whatsapp/messages.html',{'list': messages, 'filter1': filter1, 'filter2':filter2 })

# Create your views here.
