# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models
from usersettings import userconfig as config

# Create your models here.
collectionbasepath=config['Models']['collectionbasepath']

class Collection(models.Model):
    path = models.FilePathField('File path',path=collectionbasepath, allow_files=False,allow_folders=True,recursive=True, max_length=150)
    indexedFlag = models.BooleanField('Indexed')
    def __str__(self):
        return self.path

class File(models.Model):
    collection = models.ForeignKey(
        'Collection',
        on_delete=models.CASCADE,
    )
    filepath=models.FilePathField('File path',path=collectionbasepath, allow_files=True,allow_folders=False,recursive=True)
    indexedSuccess = models.BooleanField('IndexedOK',default=False)
    indexedTry=models.BooleanField('IndexedTry',default=False)
    hash_contents = models.CharField('Hash contents',max_length=200,default='')
    hash_filename = models.CharField('Hash doc name',max_length=200,default='')
    filename=models.CharField('Filename',max_length=100,default='')
    fileext=models.CharField('File Extension',max_length=10,default='')
    filesize = models.IntegerField('Filesize',default=0)
    last_modified=models.DateTimeField('date modified',blank=True)
    solrid=models.CharField('Solr ID',max_length=100,default='',blank=True)

    def __str__(self):
        return self.filepath




