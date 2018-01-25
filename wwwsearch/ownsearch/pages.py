# -*- coding: utf-8 -*-
from __future__ import unicode_literals

class Page:
    def __init__(self,page_number=0,searchterm='',direction='',pagemax=0,sorttype='',tag1field='',tag1='',tag2field='',tag2='',tag3field='',tag3=''):
        self.page_number=page_number
        self.searchterm=searchterm
        self.direction=direction
        self.pagemax=pagemax
        self.sorttype=sorttype
        self.tag1field=tag1field
        self.tag1=tag1
        self.tag2field=tag2field
        self.tag2=tag2
        self.tag3field=tag3field
        self.tag3=tag3
        
        
    def clear_(self):
        self.facets=[]
        self.facets2=[]
        self.facets3=[]
        self.tag1=''
        self.results=[]
        self.backpage,self.nextpage='',''
        self.resultcount=0
        self.pagemax=''
	

