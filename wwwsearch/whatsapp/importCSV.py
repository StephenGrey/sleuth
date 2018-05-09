# -*- coding: utf-8 -*-
from __future__ import unicode_literals, print_function
from .models import Message
from datetime import datetime
import csv,pytz, os 
#import ast, iso8601
#import json, collections

class BadPath(Exception):
    pass

class NullDate(Exception):
    pass

class Importer:
    def __init__(self,f):
        if not os.path.exists(f) or f is None:
            raise BadPath
        self.main(f)
        
    def main(self,path,maxloop=20000):
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

        
def timeaware(dumbtimeobject):
    return pytz.timezone("GMT").localize(dumbtimeobject)
#Mac / Linux stores all file times etc in GMT, so localise to GMT



