# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from django.db import models
from usersettings import userconfig as config
from django.contrib.auth.models import Group
# Create your models here.

class BlogPost(models.Model):
    pubdate=models.DateTimeField('date published',blank=True)
    url=models.URLField('blog url',blank=True)
    thumburl=models.URLField('thumbnail url',blank=True)
    text=models.TextField('blog contents',blank=True)
    body=models.TextField('html contents',blank=True)
    originalID=models.CharField('original ID',max_length=10,blank=True)
    name=models.CharField('blog title',max_length=100,default='Untitled')
    solrID=models.CharField('solrID',max_length=64,blank=True)
#    tag=models.ForeignKey(
#        'Tags',
#        on_delete=models.CASCADE,
#        blank=True,
#        default=''
#    )

    def __str__(self):
        return self.name    

class Tag(models.Model):
    tag=models.CharField('tag',max_length=30,default='')
    def __str__(self):
        return self.tag    



"""
class Collection(models.Model):
    path = models.FilePathField('File path',path=collectionbasepath, allow_files=False,allow_folders=True,recursive=True, max_length=150)
    indexedFlag = models.BooleanField('Indexed')
    core = models.ForeignKey(
        'SolrCore',
        on_delete=models.CASCADE,
    )
    def __str__(self):
        return self.path

class SolrCore(models.Model):
    coreID=models.CharField('Core ID (1-10)',max_length=10,default='')
    coreDisplayName=models.CharField('Core Display Name',max_length=10,default='',blank=True)
    corename=models.CharField('Corename',max_length=20,default='')
    usergroup=models.ForeignKey(Group)
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
    hash_contents = models.CharField('Hash contents',max_length=200,default='')
    hash_filename = models.CharField('Hash doc name',max_length=200,default='')
    filename=models.CharField('Filename',max_length=100,default='')
    fileext=models.CharField('File Extension',max_length=10,default='')
    filesize = models.IntegerField('Filesize',default=0)
    last_modified=models.DateTimeField('date modified',blank=True)
    solrid=models.CharField('Solr ID',max_length=100,default='',blank=True)

    def __str__(self):
        return self.filepath



"""

