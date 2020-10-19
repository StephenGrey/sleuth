# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from django.db import models
from configs import config
from django.contrib.auth.models import Group
from documents.models import Source
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
    source=models.ForeignKey(
        'documents.Source',
        on_delete=models.CASCADE,
        null=True,
    )

    def __str__(self):
        return self.name    

class Tag(models.Model):
    tag=models.CharField('tag',max_length=30,default='')
    def __str__(self):
        return self.tag    


