# -*- coding: utf-8 -*-
from __future__ import unicode_literals, print_function
from .models import BlogPost
import csv, iso8601,pytz, os, ast
from ownsearch import solrJson as s
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
                post.solrID=hash256(post.body.encode('utf-8')) #using the hash of the HTML body as the doc ID
                post.save()
            except Exception as e:
                print('reached row '+str(counter))
                print(e)
                
        # print(vars(post))
        print(str(counter)+'  posts added to database')
        

def getsolrID(postID):
    try:
        post= BlogPost.objects.get(originalID=postID)
        try:
            assert post.solrID is not None
            assert post.solrID is not u''
        except:
            post.solrID=hash256(post.body.encode('utf-8')) #using the hash of the HTML body as the doc ID
            post.save()
        return post.solrID
    except Exception as e:
        print(e)
        return ''
        


#update solr docs from CSV, first line contains row names; 
#solr ID field is taken from the model database and referenced by original ID field.
def addTagsFromCSV(path,mycore):
        assert os.path.exists(path)
        assert mycore.ping()
        with open(path) as f:
            reader = csv.reader(f)
            #first line should be field names; must include 'originalID' - referencing existing item in stored BlogPost model
            row=next(reader)
            fieldnames=row
            try:
                assert 'sb_databaseid' in fieldnames
            except:
                return False
            maxloop=25000
            counter=0
            changes=[]
            print(row)
            while row:
                try:
                    if counter>maxloop:
                        break
                    row=next(reader)
#                    print(row)
                    doc={}
                    updated=False
                    for n, value in enumerate(row):
                        if value=='NA':
                            continue
                        else:
                            try:
                                trylist=ast.literal_eval(value)
                                #convert the string list to an actual list 
                            except ValueError: #if it isn't a list, stick to a string
                                trylist=value
                            doc[fieldnames[n]]={"set":trylist}
                    if len(doc)>1:#only update if some valid fields to set
                        doc['id']=getsolrID(doc.pop('sb_databaseid')['set'])
                    #changes.append(doc)
                        jsondoc=json.dumps([doc])
                        print(jsondoc)
                        counter+=1
                        result,status=u.post_jsonupdate(jsondoc,mycore)
                        if status is False:
                            print (result,status)
                except Exception as e:
                    print('reached row '+str(counter))
                    print(e)
#            print(changes)
            print(str(counter-1)+' posts modified in database')
        
def checkbase():
    for x in range(3289,30000):
        try:
            b=BlogPost.objects.get(originalID=x)
            if x%100==0:
                print(x)
        except Exception as e:
            print(e)
            print('Blogpost with ID '+str(x)+'  not found')


def extractbase(idstart=0,idstop=2,mycore=s.SolrCore('test1')):
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
    #print(vars(post))
    doc=collections.OrderedDict()  #keeps the JSON file in a nice order
    if not post.solrID:
        doc['id']=hash256(post.body.encode('utf-8')) #using the hash of the HTML body as the doc ID
    else:
        doc['id']=post.solrID #hash256(post.body.encode('utf-8')) #using the hash of the HTML body as the doc ID
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
"""
>>> i.BlogPost.objects.all()[0].__dict__
'solrID': u'', ', 'name': u'That crook Schembri was in court today, pleading that he is not a crook', 'pubdate': None, 'url': u'https://daphnecaruanagalizia.com/', 'text': u'Former Opposition leader Simon Busuttil testified in court this morning, as did the Prime Minister\u2019s More', '_state': <django.db.models.base.ModelState object at 0x106040e10>, 'id': 7432, 'originalID': u'0'}
"""

def updateindex(post,mycore):
    solrid=getsolrID(post.originalID)
    print('SolrID',solrid)
    doc=collections.OrderedDict()  #keeps the JSON file in a nice order
    doc['id']=solrid #hash256(post.body.encode('utf-8')) #using the hash of the HTML body as the doc ID
    doc[mycore.rawtext]={"set":post.text}
    doc[mycore.hashcontentsfield]={"set":doc['id']} #also store hash in its own standard field
    doc[mycore.docnamefield]={"set":post.name}
    if post.pubdate:
        doc[mycore.datefield]={"set":s.ISOtimestring(post.pubdate)}
    else:
        print('missing pubdate')
    jsondoc=json.dumps([doc])
    #print(jsondoc)
    result,status=u.post_jsonupdate(jsondoc,mycore)
    print (result,status)
    return


#add a new document ('doc') to the solr index
def makejson(doc):   #the changes use standard fields (e.g. 'date'); so parse into actual solr fields
    a=collections.OrderedDict()  #keeps the JSON file in a nice order
    a['doc']=doc
    aa=collections.OrderedDict()
    aa['add']=a
    data=json.dumps([aa])
    return data

#add a tag field to the existing doc ... 
def addtags(solrid,tags,mycore):
    doc=collections.OrderedDict()  #keeps the JSON file in a nice order
    doc['id']=solrid #using the hash of the HTML body as the doc ID
    doc['sb_taglist1']={"set":tags}
    jsondoc=json.dumps([doc])
#    print(jsondoc)
    result,status=u.post_jsonupdate(jsondoc,mycore)

def checksolr(mycore):
    maxcount=25000
    counter=0
    for post in BlogPost.objects.all():
        counter+=1
        if counter>maxcount:
            break
#        print(post.id,post.name,post.pubdate)
        solrID=getsolrID(post.originalID)
        try:
            docs=s.getmeta(solrID,mycore)
            doc=docs[0]
            if not doc.docname or not doc.date:
                print('missing meta:',post.id,post.name,post.pubdate)
                print(doc.docname,doc.date)
                try:
                    updateindex(post,mycore)
                except Exception as e:
                    print(e)                	
        except Exception as e:
            print(e)
            print('no solr doc found for post ',post.id,post.name)
        
    return