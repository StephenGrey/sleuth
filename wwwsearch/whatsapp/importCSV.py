# -*- coding: utf-8 -*-
from __future__ import unicode_literals, print_function
from .models import Message,PhoneNumber
from datetime import datetime
import csv,pytz, os 
#import ast, iso8601
#import json, collections

class BadPath(Exception):
    pass

class NullDate(Exception):
    pass

class Importer:
    def __init__(self,f,maxloop=100000):
        if not os.path.exists(f) or f is None:
            raise BadPath
        self.main(f,maxloop)
        
    def main(self,path,maxloop):
        with open(path) as f:
            reader = csv.reader(f)
            #first line is column headers
            row=next(reader)
            counter=0
            print('Column headers: {}'.format(row))
            while row:
                try:
                    counter+=1
                    if counter>maxloop:
                        break
                    row=next(reader,None) # Don't raise exception if no line exists                
                    print(row)
                    if not row:
                        break
                    self.parserow(row)
                except NullDate as e:
                    continue
#                except Exception as e:
#                    print('Error after reached row '+str(counter))
#                    print(e)
                    
            # print(vars(post))
            print(str(counter)+'  posts added to database')
    
    
    def parserow(self,row):
# ID,Date,Time,Sent/received,From,To,Country,Number,WhatsApp group,Message
        post=Message()   
        post.originalID=row[0]
        datestring=row[1] +'T'+row[2]
        post.send_time=self.fetchdate(datestring)
        post.to_number=row[5]
        post.from_number=row[4]
        post.whatsapp_group=row[8]
        post.messagetext=row[9]
        print (post)
        post.save()
    
    def fetchdate(self,datestring):
        try:
            if not datestring:
                raise NullDate
            date=datetime.strptime(datestring,'%d/%m/%YT%H:%M:%S')
#            date=iso8601.parse_date(datestring) -- convert a string in ISO8601
            date=timeaware(date)
            #print(datestring,date)
        except ValueError:
            raise NullDate
        return date


class NameImporter(Importer):
    def parserow(self,row):
# ID,Date,Time,Sent/received,From,To,Country,Number,WhatsApp group,Message
        post=PhoneNumber()   
        post.originalID=row[5]
#        datestring=row[1] +'T'+row[2]
#        post.send_time=self.fetchdate(datestring)
        post.number=row[0]
        post.name=row[1]
        if row[2].lower()=='true':
            post.verifed=True
        else:
            post.verified=False
        post.name_exmessage=row[4]
        post.name_source=row[3]
        post.name_possible=''
        post.original_ID=row[5]
        post.notes=''
        print (post)
        post.save()
"""
Model CSV:
0NUMBER,1POSSIBLE NAME,2VERIFIED,3NAME SOURCE,4NAME IN MESSAGE,5ORIGINAL_ID
 """     

        
def timeaware(dumbtimeobject):
    return pytz.timezone("GMT").localize(dumbtimeobject)
#Mac / Linux stores all file times etc in GMT, so localise to GMT



