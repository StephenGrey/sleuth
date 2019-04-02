# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from ownsearch.pages import Page,quote_plus,unquote_plus
import logging,os
log=logging.getLogger('ownsearch.documentpage')
from ownsearch import authorise
from .forms import IndexForm, get_corechoices,SourceForm,get_sourcechoices
from .models import Collection,Index,Source
from .file_utils import make_relpath,new_is_inside,SqlFileIndex
from .management.commands import make_collection
from . import sql_connect as sql

class NoValidCore(Exception):
    pass

class NoValidCollection(Exception):
    pass

class CollectionPage(Page):
    def __init__(self,path=''):
        self.docpath=path
        self.url_path=quote_plus(path)
        log.debug(self.url_path)
    def getcores(self,this_user,stored_core=None):
        """get authorised solr cores , choosed stored core or default """
        self.getindexes(this_user)
        if stored_core==None or stored_core=='':
            self.stored_core=None
            if self.defaultcoreID:
                self.coreID=int(self.defaultcoreID)
                
            else:
                raise NoValidCore
        else:
            self.stored_core=stored_core
            self.coreID=int(stored_core)
        self.mycore=self.cores[self.coreID]
            
    def getindexes(self,thisuser):
        #set up solr indexes
        try:
            authcores=authorise.AuthorisedCores(thisuser)      
        except Exception as e:
            log.warning('No valid indexes defined in database')
            self.defaultcoreID='' #if no indexes, no valid default
        self.cores=authcores.cores
        self.defaultcoreID=authcores.defaultcore
        log.debug('CORES: '+str(self.cores)+' DEFAULT CORE:'+str(self.defaultcoreID))
        
    def chooseindexes(self,request_method,request_postdata='',test=False):
        if request_method=='POST' and request_postdata.get("checkindex_form"):
            if request_postdata.get("check_index"):
                self.check_index=True
                log.debug('setting check_index')
            else:
                self.check_index=False
                log.debug('clearing check_index')
            
        if request_method=='POST' and request_postdata.get('corechoice'): #if data posted => switch core
            form=IndexForm(request_postdata)
            if test:
            #NOT CLEAR WHY THIS SHOULD BE NECESSARY
                form.fields['corechoice'].choices=get_corechoices()
            self.post_indexform(form)
            self.form=IndexForm(initial={'corechoice':self.coreID})
            self.mycore=self.cores[self.coreID]
        else:
            self.form=IndexForm(initial={'corechoice':self.coreID})
            #log.debug('Form created: {} with choices: {}'.format(self.form.__dict__,self.form.fields['corechoice'].__dict__))
            self.mycore=self.cores[self.coreID]
            
    def post_indexform(self,form):
        """change index"""
        #log.debug('Form: {} Valid: {}'.format(form.__dict__,form.is_valid()))
        if form.is_valid():
            self.coreID=int(form.cleaned_data['corechoice'])
            self.validform=True
            self.form=form
            log.debug('change core to {}'.format(self.coreID))
            
        else:
            log.warning('posted form is not valid: {}'.format(form.errors))
            self.validform=False
            self.form=None
            
    def get_collections(self):
        self.myindex=Index.objects.get(id=self.coreID)
        log.debug('my Index: {}'.format(self.myindex))
        self.authorised_collections=Collection.objects.filter(core=self.myindex)
        self.authorised_collections_relpaths=[(make_relpath(c.path),c.id,c.live_update) for c in self.authorised_collections]

    def collection_updates(self,request_posted):
        _collection_IDs=request_posted.getlist('checked')
        if _collection_IDs:
            #validate
            try:
                _collections=[Collection.objects.get(id=int(c)) for c in _collection_IDs]
                for c in _collections:
                    assert c in self.authorised_collections
            except Exception as e:
                log.debug(e)
                raise NoValidCollection
            if request_posted.get('live-button'):
                log.debug('make live')
                for c in _collections:
                    c.live_update=True
                    c.save()
            elif request_posted.get('unlive-button'):
                log.debug('unmake live')
                for c in _collections:
                    c.live_update=False
                    c.save()
            elif request_posted.get('delete-button'):
                for c in _collections:
                    c.delete()
                    log.debug(f'deleted collection {c.path} with ID: {c.id}')
    
    
class FilesPage(CollectionPage):
    def __init__(self,request='',default_master='',path=''):
        self.request=request
        self.docpath=path
        
        if self.request and default_master:
            self.local_scanpath=request.session.get('scanfolder')
            self.masterindex_path=request.session.get('masterfolder',default_master)
            
            self.masterpath_url=f'/dups/folder/{self.masterindex_path}'
            log.debug(f'Masterindex path: {self.masterindex_path}')
            self.scanpath=self.local_scanpath
            log.debug(f'stored scanpath: {self.scanpath}')
    
    def get_stored(self,media_root):
        
        if self.scanpath:
            try:
                self.specs=SqlFileIndex(os.path.join(media_root,self.scanpath),label='local')
                #self.specs.hash_scan()
            except:
                self.specs=None
        else:
            self.specs=None
            
        try:
            self.masterspecs=SqlFileIndex(os.path.join(media_root,self.masterindex_path),label='master')
            log.debug(self.masterspecs)
            #self.masterspecs.hash_scan()
        except Exception as e:
            log.debug(e)
            self.masterspecs=None
        
    def remove_file(self,filepath):
        try:
            self.masterspecs.delete_record(filepath)
        except AttributeError:
            pass
        try:
            self.specs.delete_record(filepath)
        except AttributeError:
            pass
    def move_file(self,filepath,newpath):
        spec=None
        
        #get specs, if stored, and remove entry on source file
        if self.masterspecs:
            log.debug(self.masterspecs.folder_path)
            if new_is_inside(filepath,self.masterspecs.folder_path):
                spec=self.masterspecs.files.get(filepath)
                log.debug(spec)
                
        if self.specs:
                if new_is_inside(filepath,self.specs.folder_path):
                    if not spec:
                        spec=self.masterspecs.files.get(filepath)
        self.remove_file(filepath)
        
        #now add specs on destination fle
        if self.masterspecs:
            if new_is_inside(newpath,self.masterspecs.folder_path):
                log.debug('destination in master folder')
                self.masterspecs.update_record(newpath) #add the specs to the index
                try:
                    _hash=self.masterspecs.files[newpath].get('contents_hash')
                    log.debug(_hash)
                    if _hash:
                        self.masterspecs.hash_append(_hash,newpath)
                except KeyError:
                    pass
                self.masterspecs.sync()
            #self.masterspecs.hash_scan()
            
        if self.specs:
            if new_is_inside(newpath,self.specs.folder_path):
                self.specs.update_record(newpath)
                try:
                    _hash=self.specs.files[newpath].get('contents_hash')
                    log.debug(_hash)
                    if _hash:
                        self.specs.hash_append(_hash,newpath)
                except KeyError:
                    pass
                self.specs.sync()


class SolrFilesPage(CollectionPage):
    pass
        
class MakeCollectionPage(CollectionPage):
    def __init__(self,relpath='',rootpath=''):
        self.docpath=relpath
        self.rootpath=rootpath
        self.error=None
        self.success=False
        
    def make_sources(self,request_method,request_postdata,source_initial=None,live_default=False):
        if request_method=='POST' and request_postdata.get('make_collection'):
            form=SourceForm(request_postdata)
            if form.is_valid():
                self.validform=True
                self.source_form=form
                self.live_update=True if form.cleaned_data['live_update'] else False
                if request_postdata.get('sourcechoice'):
                    self.sourceID=int(form.cleaned_data['sourcechoice'])
                    log.debug('change source selection to {}'.format(self.sourceID))
                else:
                    self.sourceID=None
            else:
                log.warning('posted form is not valid: {}'.format(form.errors))
                self.validform=False
                self.source_form=None
                self.sourceID=None
        else:
            if not source_initial:
                try:
                    source_initial=get_sourcechoices()[0][0]
                except Exception as e:
                    log.error(e)
                    source_initial=None
            self.source_form=SourceForm(initial={'sourcechoice':source_initial,'live_update':self.live_update})
            self.sourceID=source_initial
        
    def check_path(self):
        log.debug(self.rootpath)
        log.debug(self.docpath)
        try:
            self._path=os.path.join(self.rootpath,self.docpath)
            assert self.path_exists
        except Exception as e:
            raise NoValidCollection('Not valid path')

        try:
            assert self.relpath_valid
        except Exception as e:
            raise NoValidCollection('Relative path not exists')
        assert self.valid_new_collection
        
    @property
    def valid_new_collection(self):
        for path,_id,live_update in self.authorised_collections_relpaths:
            if path==self.docpath:
                raise NoValidCollection('This collection exists already')
            elif path==".":
                raise NoValidCollection('The entire docstore is indexed \n- no need to add more collections')
            #is this new collection inside an existing one
            elif new_is_inside(self.docpath,path):
                raise NoValidCollection('This folder is inside an existing collection')
            elif path.startswith(self.docpath):
                raise NoValidCollection('This folder has existing one or more existing collections inside\n -- remove them first!')
        return True
            
    def make_collection(self):
        try:
            source=Source.objects.get(id=self.sourceID)
            collection,created=make_collection.make(path=self._path, source=source,_index=self.myindex,live_update=self.live_update)
            self.new_collection=collection
            self.success=created
            log.info(f'Collection with path {self._path} in index {self.myindex} created: {created}')
        except Exception as e:
            log.error(e)
            raise NoValidCollection("Error saving new collection")
        
        
        
        
    
    
    