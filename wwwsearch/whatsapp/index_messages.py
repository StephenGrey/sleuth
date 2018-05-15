# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from .models import Message
from . import views
import json, collections 
from .conversation import Conversation, list_messages  
from ownsearch.hashScan import hash256 #to calculate SolrID
from ownsearch import solrJson as s
from documents import updateSolr as u

def main(node1,mycore,sourcetext='WhatsApp'): # 
    """store messages to and from node"""
    combo = list_messages()
    for number,count,namerecord in combo:
        if number==node1:
            continue
        print(node1,number,namerecord)
        c=Conversation(node1=node1,node2=number)        
        result,status=extractpost(c,mycore,sourcetext)
        #solrID=models.CharField('solrID',max_length=64,blank=True)
        print (status)
        
#EXTRACT INDIVIDUAL SOLR DOC FROM BLOGPOST
def extractpost(conversation,mycore,sourcetext='Test source'):
    """extract message data to solr doc"""

    doc=collections.OrderedDict()  #keeps the JSON file in a nice order    
#    #choose an ID for the solr record
    doc[mycore.unique_id]=hash256(conversation.text.encode('utf-8')) #using the hash of the HTML body as the doc ID
    if mycore.hashcontentsfield != mycore.unique_id:
        doc[mycore.hashcontentsfield]=doc[mycore.unique_id] #also store hash in its own standard field
    doc[mycore.rawtext]=conversation.text
    doc['preview_html']=conversation.preview_html
#    doc['database_originalID']=''
#    doc['SBdata_ID']=''
    doc[mycore.sourcefield]=sourcetext
    if conversation.end_time:
        doc[mycore.datefield]=s.ISOtimestring(conversation.end_time)        
    doc[mycore.docpath]=conversation.url
    doc[mycore.preview_url]=conversation.url
#    doc['thumbnailurl']=post.thumburl
    doc[mycore.docnamesourcefield]=conversation.name    
    jsondoc=json.dumps([doc])
    
    result,status=u.post_jsondoc(jsondoc,mycore)
    return result,status
#        
#        

            	
