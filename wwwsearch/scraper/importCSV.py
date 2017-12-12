# -*- coding: utf-8 -*-
from __future__ import unicode_literals, print_function
from .models import BlogPost
import csv, iso8601,pytz
from ownsearch import solrSoup as s
from ownsearch.hashScan import hash256
import json, collections
from documents import updateSolr as u

def impCSV(path):
    with open(path) as f:
        reader = csv.reader(f)
        #first line is column headers
        row=next(reader)
        maxloop=100000
        counter=0
        print(row)
        while row:
            try:
                counter+=1
                if counter>maxloop:
                    break
                row=next(reader)
                post=BlogPost()
                post.originalID=row[0]
                post.name=row[1]
                post.url=row[2]
                datestring=row[3]
                try:
                    date=iso8601.parse_date(datestring)
                    post.pubdate=date
                except:
                    print('no date')
                post.thumburl=row[4]
                post.text=row[5]
                post.body=row[6]
                post.save()
            except Exception as e:
                print('reached row '+str(counter))
                print(e)
                
        # print(vars(post))
        print(str(counter)+'  posts added to database')
        
        
def checkbase():
    for x in range(3289,30000):
        try:
            b=BlogPost.objects.get(originalID=x)
            if x%100==0:
                print(x)
        except Exception as e:
            print(e)
            print('Blogpost with ID '+str(x)+'  not found')


def extractbase(idstart=0,idstop=1):
    mycore=s.SolrCore('test1')
    mycore.ping()
#    print(vars(mycore))   
    for x in range(idstart,idstop):
        try:
            b=BlogPost.objects.get(originalID=x)
            result,status=extractpost(b,mycore)
            print('Extracting to solr, title\"'+b.name+'\",\nID: '+str(b.id))
            print(result,status)
        except BlogPost.DoesNotExist as e:
            print(e)
            print('Blogpost with ID '+str(x)+'  not found')
    

def extractpost(post,mycore):
#    try:
#        post=BlogPost.objects.get(id=id)
#    except BlogPost.DoesNotExist:
#        print('post does not exist')
#        return False
#    print(vars(post))
    doc=collections.OrderedDict()  #keeps the JSON file in a nice order
    doc['id']=hash256(post.body.encode('utf-8')) #using the hash of the HTML body as the doc ID
    doc[mycore.hashcontentsfield]=doc['id'] #also store hash in its own standard field
    doc[mycore.rawtext]=post.text
    doc['preview_html']=post.body
    doc['database_originalID']=post.originalID
    doc['SBdata_ID']=post.id
    if post.pubdate:
        doc[mycore.datefield]=s.ISOtimestring(post.pubdate)
    doc[mycore.docpath]=post.url,
    doc['thumbnailurl']=post.thumburl
    doc[mycore.docnamefield]=post.name    
    jsondoc=json.dumps([doc])
    result,status=u.post_jsondoc(jsondoc,mycore)

    return result,status

def makejson(doc):   #the changes use standard fields (e.g. 'date'); so parse into actual solr fields
    a=collections.OrderedDict()  #keeps the JSON file in a nice order
    a['doc']=doc
    aa=collections.OrderedDict()
    aa['add']=a
    data=json.dumps([aa])
    return data

def addtags(doc):
    doc['id']=hash256(post.body.encode('utf-8')) #using the hash of the HTML body as the doc ID
    