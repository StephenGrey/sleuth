# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from __future__ import print_function
from builtins import str #backwards to 2.X
import os
from . import solrcursor
from .updateSolr import remove_filepath_or_delete_solrrecord
from configs import config
DOCSTORE=config['Models']['collectionbasepath'] #get base path of the docstore

class IndexChecker:
    def __init__(self,mycore,test=False):
        self.mycore=mycore
        self.test=test
        self.process()
        
    def process(self):
        res=False
        while True:
            res = solrcursor.cursor_next(self.mycore,searchterm='*',highlights=False,lastresult=res)
            if res == False:
                break
            elif not res.results:
                break
            else:
                for doc in res.results:
                    self.check(doc)
                    
    def check(self,doc):
        paths=doc.data['docpath']
        for path in paths:
            if path.startswith('http'):
                continue
            if path.startswith('/whatsapp/'):
                continue
            fullpath=os.path.join(DOCSTORE,path)
            #print(fullpath)
            if not os.path.exists(fullpath):
                print(f'Solrdoc id: \"{doc.id}\" Fullpath \"{fullpath}\" does not exist')
                result=remove_filepath_or_delete_solrrecord(doc.id,path,self.mycore)
                print(f'Filepath removed')
                