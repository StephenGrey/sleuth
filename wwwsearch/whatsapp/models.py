# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models

"""
['#', 'Chat #', 'Identifier', 'Start Time: Date', 'Start Time: Time', 'Last Activity: Date', 'Last Activity: Time', 'Name', 'Description', 'Participant photo #1', 'Participant photo #2', 'Participant photo #3', 'Participant photo #4', 'Participant photo #5', 'Participant photo #6', 'Participant photo #7', 'Participant photo #8', 'Participant photo #9', 'Participant photo #10', 'Participant photo #11', 'Participants', 'Number of attachments', 'Source', 'Account', 'Deleted - Chat', 'Tag Note - Chat', 'Carved', 'Manually decoded', 'Instant Message #', 'From', 'To', 'Participants Timestamps', 'Cc', 'Bcc', 'Priority', 'Subject', 'Body', 'Status', 'Platform', 'Label', 'Location', 'Timestamp: Date', 'Timestamp: Time', 'Delivered: Date', 'Delivered: Time', 'Read: Date', 'Read: Time', 'Attachment #1', 'Attachment #1 - Details', 'Attachment #2', 'Attachment #2 - Details', 'Deleted - Instant Message', 'Tag Note - Instant Message', 'Source file information', 'Starred message', 'Message Carved', 'Message Manually decoded']
"""

class Message(models.Model):
    messagetext=models.CharField('Message',max_length=65536,default='',blank=True)
    from_number=models.CharField('From',max_length=30,default='')
    to_number=models.CharField('To',max_length=30,default='')
    messagetype=models.CharField('Message_Type',max_length=30,default='WhatsApp')
    message_source=models.CharField('Source',max_length=30,default='')
    whatsapp_group=models.CharField('Group',max_length=60,default='')
    attachments_number=models.IntegerField('Attachments',default=0)
    attach1_path=models.CharField('Attach1',max_length=200,default='')
    attach2_path=models.CharField('Attach2',max_length=200,default='')
    send_time=models.DateTimeField('Sent',blank=True)
    personal=models.BooleanField('Personal',default=False)
    original_ID=models.CharField('Original_ID_',max_length=10,default='')
    def __str__(self):
        return "Message from {} to {} in group {} : {}".format(self.from_number,self.to_number,self.whatsapp_group,self.messagetext)

class PhoneNumber(models.Model):
    number=models.CharField('Number',max_length=30,default='')
    name=models.CharField('Name',max_length=60,default='')
    verified=models.BooleanField('Verified',default=False)
    personal=models.BooleanField('Personal',default=False)
    photo_path=models.CharField('PhotoPath',max_length=200,default='')
    name_exmessage=models.CharField('Name in Message',max_length=200,default='')
    name_source=models.CharField('Name source',max_length=30,default='')
    name_possible=models.CharField('Possible name',max_length=30,default='')
    original_ID=models.CharField('Original_ID_',max_length=10,default='')
    notes=models.CharField('Notes',max_length=250,default='')
    def __str__(self):
        return self.number


# Create your models here.
