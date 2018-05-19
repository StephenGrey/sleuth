# -*- coding: utf-8 -*-
"""
Markup raw text for display

"""
from __future__ import unicode_literals
from whatsapp.models import Message #for test
import re

testdata="is there a link here http://google.com and another one https://www.dogfish.com or just example.com or maybe www.me.net"
    

def urls(data=testdata):
    regex=getGRUBER()
    markedup=regex.sub(r'<a href="\1">\1</a>',data)
    
    return markedup
    
#    
#    print(GRUBER_PAT.findall(testdata))
#    
#    print(re.sub(GRUBER_PAT,'LINK\0',testdata))
#       
#    for group in GRUBER_PAT.findall(testdata):
#        print (group)
#        
#    print [mgroups[0] for mgroups in GRUBER_URLINTEXT_PAT.findall(testdata) ]
#
#def urls(text):
#    GRUBER_PAT=getregex()
#
#    for mgroups in GRUBER_PAT.findall(text):
#        print (mgroups[0])
#        print (text) 
#        GRUBER_PAT.sub(r'<a href="\1">\1</a>',text)   
#    
#    splits=re.split(GRUBER_PAT,text)
#    if len(splits)>1:
#       print(splits)
#       
#       
#       
       
def test():
    regex=getGRUBER()

    n=0
    ms=Message.objects.all()
    for m in ms:
       n +=1
       if n>1500:
           break
       #print(m.messagetext)
       markedup=urls(m.messagetext)
       print(markedup)
       
def getGRUBER():
    return re.compile(ur'(?i)\b((?:https?://|www\d{0,3}[.]|[a-z0-9.\-]+[.][a-z]{2,4}/)(?:[^\s()<>]|\(([^\s()<>]+|(\([^\s()<>]+\)))*\))+(?:\(([^\s()<>]+|(\([^\s()<>]+\)))*\)|[^\s`!()\[\]{};:\'".,<>?\xab\xbb\u201c\u201d\u2018\u2019]))')
