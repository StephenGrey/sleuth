# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from django.db import models
from usersettings import userconfig as config
from django.contrib.auth.models import Group, User

# Create your models here.
collectionbasepath=config['Models']['collectionbasepath']

class Collection(models.Model):
    path = models.FilePathField('File path',path=collectionbasepath, allow_files=False,allow_folders=True,recursive=True, max_length=150)
    indexedFlag = models.BooleanField('Indexed')
    core = models.ForeignKey(
        'Index',
        on_delete=models.CASCADE,
    )
    source = models.ForeignKey(
        'Source',
        on_delete=models.CASCADE,
        null=False,
    )
    def __str__(self):
        return self.path

class Source(models.Model):
    sourceDisplayName=models.CharField('Source Display Name',max_length=30,default='',blank=True)
    sourcename=models.CharField('Sourcename',max_length=10,default='')
    def __str__(self):
        return self.sourcename

class Index(models.Model):
    #coreID=models.CharField('Core ID (1-10)',max_length=10,default='')
    coreDisplayName=models.CharField('Core Display Name',max_length=30,default='',blank=True)
    corename=models.CharField('Corename',max_length=20,default='')
    usergroup=models.ForeignKey(Group,on_delete=models.CASCADE)
    def __str__(self):
        return self.corename

class File(models.Model):
    collection = models.ForeignKey(
        'Collection',
        on_delete=models.CASCADE,
    )
    filepath=models.FilePathField('File path',path=collectionbasepath, allow_files=True,allow_folders=False,recursive=True)
    indexedSuccess = models.BooleanField('IndexedOK',default=False)
    indexedTry=models.BooleanField('IndexedTry',default=False)
    indexUpdateMeta=models.BooleanField('UpdateMeta',default=False)
    is_folder=models.BooleanField('IsFolder',default=False)
    hash_contents = models.CharField('Hash contents',max_length=200,default='')
    hash_filename = models.CharField('Hash doc name',max_length=200,default='')
    filename=models.CharField('Filename',max_length=100,default='')
    fileext=models.CharField('File Extension',max_length=10,default='')
    filesize = models.IntegerField('Filesize',default=0)
    last_modified=models.DateTimeField('date modified',blank=True)
    solrid=models.CharField('Solr ID',max_length=100,default='',blank=True)
    child=models.BooleanField('Child document',default=False) #if an extracted child doc (e.g. attachment or embedded image)

    def __str__(self):
        return self.filepath

class UserEdit(models.Model):
    solrid=models.CharField('Solr ID',max_length=100,default='',blank=True)
    usertags = models.CharField('New user tags',max_length=31,default='',blank=True)
    username= models.CharField('user name',max_length=50,default='',blank=True)
    time_modified=models.DateTimeField('time modified',blank=True,null=True)
    corename=models.CharField('Corename',max_length=20,default='')
    index_updated=models.BooleanField('Index Updated',default=False)

    def __str__(self):
        return "Change #{}: \"{}\" added by \"{}\" to solrdoc \"{}\" in index \"{}\"".format(self.pk,self.usertags,self.username,self.solrid,self.corename)

class SyncStatus(models.Model):
    remote_useredit_lastid=models.IntegerField('Last imported edit id',default=1)
    
    