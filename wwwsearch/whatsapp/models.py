# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models

class Message(models.Model):
    messagetext=models.CharField('Message',max_length=65536,default='',blank=True)
    from_number=models.CharField('From',max_length=30,default='')
    to_number=models.CharField('To',max_length=30,default='')
    whatsapp_group=models.CharField('Group',max_length=60,default='')
    send_time=models.DateTimeField('Sent',blank=True)
    personal=models.BooleanField('Personal',default=False)
    original_ID=models.CharField('Original_ID_',max_length=10,default='')
    def __str__(self):
        return "Message from {} to {} in group {} : {}".format(self.from_number,self.to_number,self.whatsapp_group,self.messagetext)

class PhoneNumber(models.Model):
    number=models.CharField('Number',max_length=30,default='')
    name=models.CharField('Name',max_length=60,default='')
    verified=models.BooleanField('Verified',default=False)
    name_exmessage=models.CharField('Name in Message',max_length=200,default='')
    name_source=models.CharField('Name source',max_length=30,default='')
    name_possible=models.CharField('Possible name',max_length=30,default='')
    original_ID=models.CharField('Original_ID_',max_length=10,default='')
    notes=models.CharField('Notes',max_length=250,default='')
    def __str__(self):
        return self.number


# Create your models here.
