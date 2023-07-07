# -*- coding: utf-8 -*-
from __future__ import unicode_literals, print_function
from .models import Message,PhoneNumber
from datetime import datetime
import csv,pytz, os, re
#import ast, iso8601
#import json, collections

"""
['#', 'Chat #', 'Identifier', 'Start Time: Date', 'Start Time: Time', 'Last Activity: Date', 'Last Activity: Time', 'Name', 'Description', 'Participant photo #1', 'Participant photo #2', 'Participant photo #3', 'Participant photo #4', 'Participant photo #5', 'Participant photo #6', 'Participant photo #7', 'Participant photo #8', 'Participant photo #9', 'Participant photo #10', 'Participant photo #11', 'Participants', 'Number of attachments', 'Source', 'Account', 'Deleted - Chat', 'Tag Note - Chat', 'Carved', 'Manually decoded', 'Instant Message #', 'From', 'To', 'Participants Timestamps', 'Cc', 'Bcc', 'Priority', 'Subject', 'Body', 'Status', 'Platform', 'Label', 'Location', 'Timestamp: Date', 'Timestamp: Time', 'Delivered: Date', 'Delivered: Time', 'Read: Date', 'Read: Time', 'Attachment #1', 'Attachment #1 - Details', 'Attachment #2', 'Attachment #2 - Details', 'Deleted - Instant Message', 'Tag Note - Instant Message', 'Source file information', 'Starred message', 'Message Carved', 'Message Manually decoded']

[(0, '\ufeff#'), (1, 'Chat #'), (2, 'Identifier'), (3, 'Start Time: Date'), (4, 'Start Time: Time'), (5, 'Last Activity: Date'), (6, 'Last Activity: Time'), (7, 'Name'), (8, 'Description'), (9, 'Participant photo #1'), (10, 'Participant photo #2'), (11, 'Participant photo #3'), (12, 'Participant photo #4'), (13, 'Participant photo #5'), (14, 'Participant photo #6'), (15, 'Participant photo #7'), (16, 'Participant photo #8'), (17, 'Participant photo #9'), (18, 'Participant photo #10'), (19, 'Participant photo #11'), (20, 'Participants'), (21, 'Number of attachments'), (22, 'Source'), (23, 'Account'), (24, 'Deleted - Chat'), (25, 'Tag Note - Chat'), (26, 'Carved'), (27, 'Manually decoded'), (28, 'Instant Message #'), (29, 'From'), (30, 'To'), (31, 'Participants Timestamps'), (32, 'Cc'), (33, 'Bcc'), (34, 'Priority'), (35, 'Subject'), (36, 'Body'), (37, 'Status'), (38, 'Platform'), (39, 'Label'), (40, 'Location'), (41, 'Timestamp: Date'), (42, 'Timestamp: Time'), (43, 'Delivered: Date'), (44, 'Delivered: Time'), (45, 'Read: Date'), (46, 'Read: Time'), (47, 'Attachment #1'), (48, 'Attachment #1 - Details'), (49, 'Attachment #2'), (50, 'Attachment #2 - Details'), (51, 'Deleted - Instant Message'), (52, 'Tag Note - Instant Message'), (53, 'Source file information'), (54, 'Starred message'), (55, 'Message Carved'), (56, 'Message Manually decoded')]

"""
class BadPath(Exception):
    pass

class NullDate(Exception):
    pass

class Importer:
    def __init__(self,f,maxloop=100000,default='',message_source='New WhatsApps',message_type='WhatsApp'):
        if not os.path.exists(f) or f is None:
            raise BadPath
        self.default=default

        self.message_type=message_type
        self.message_source=message_source
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
                    #print(row)
                    if not row:
                        break
                    #self.parserow(row)
                    self.parserow(row)
                except NullDate as 	e:
                    continue
#                except Exception as e:
#                    print('Error after reached row '+str(counter))
#                    print(e)
                    
            # print(vars(post))
            print(str(counter)+'  posts added to database')
    
    
    def check_row(self,row):
        send_time=self.new_fetchdate(row[42])
        posts=Message.objects.filter(original_ID=row[0],send_time=send_time)
        if len(posts)>1:
            #print(posts)
            posts[1].delete()
            print('deleted')
    
    def parserow(self,row):
# ID,Date,Time,Sent/received,From,To,Country,Number,WhatsApp group,Message

        post=Message()   
        original_ID=row[0]        
        send_time=self.new_fetchdate(row[42])
        
        try:
            post,created=Message.objects.get_or_create(send_time=send_time,original_ID=original_ID)
        except Exception as e:
            print (e)
            print(row)
            return
        
        
        _to=self.parse_number(row[30])
        #print(f"TO: {_to[0]},{_to[1]}")

        if not _to[0] and row[7]:
            post.to_number=0
        elif not _to[0]:
        	post.to_number=self.default
        else:
            post.to_number=_to[0]
        	
        _from=self.parse_number(row[29])
        if not _from[0]:
           _from=self.parse_number(row[2])
        #print(f"FROM: {_from[0]},{_from[1]}")
        post.from_number=_from[0]
        post.whatsapp_group=row[7]
        post.messagetext=row[36]
        
        post.messagetype=self.message_type
        post.message_source=self.message_source
        post.attach1_path=row[47]
        post.attach2_path=row[49]

        try:
            post.save()
        except Exception as e:
            print(e)
            print(post.__dict__)
            print(row[29],row[30])
    
    def parse_number(self,text):
        if text=='System Message System Message':
            return text,'System'
        matches=re.match('(.*)@(.*)',text)
        try:
            return matches[1],matches[2]
        except:
            
            return None,None
            
    def parse_name(self,text):
        
        try:
            return re.match('([A-Za-z0-9_.]*) (.*)',text)[2]
        except:
            return None
            
    def new_fetchdate(self,timestamp):
        try:
            timezone=re.match('.*UTC(.?.?).*',timestamp)[1]
            z=timezone[0]+f"{int(timezone[1]):0>2d}00"
            
            stamp=datetime.strptime(timestamp[:19]+" "+z,'%d/%m/%Y %H:%M:%S %z')
            return stamp
            
        except Exception as e:
            print(e)
            timezone=''



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


class NewNameImporter(Importer):
    def parserow(self,row):
        #post,created=
        
        _to=self.parse_number(row[30])
        #print(f"TO: {_to[0]},{_to[1]}")

        if _to[0] and _to[1]:
            card,created=PhoneNumber.objects.get_or_create(number=_to[0])
            if created:
                to_name=self.parse_name(_to[1])
                print(to_name,_to[0])
                card.name=to_name
                card.save()
            
            
            
        _from=self.parse_number(row[29])
        if _from[0] and _from[1]:
            card,created=PhoneNumber.objects.get_or_create(number=_from[0])
            if created:
                from_name=self.parse_name(_from[1])
                if from_name:
                    print(from_name,_from[0])
                    card.name=from_name
                    card.save()                    
                
#           from_number=self.parse_name(_from[1])
#           print(from_number)
        #print(f"FROM: {_from[0]},{_from[1]}")
        #post.from_number=_from[0]

        
        	

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



