# -*- coding: utf-8 -*-
from django.contrib.auth.models import User, Group, Permission
from documents.models import Index
from ownsearch import solrJson,pages, solr_indexes

def make_admingroup(admin_user,verbose=True): 
    """make an adminusers group containing an admin user with all permissions"""  
    new_group, created = Group.objects.get_or_create(name='adminusers')
    if verbose and created:
        print('New group "adminusers" created')
    elif not created:
        print('Adminusers group already exists, or failed to create')
        
    #give all permissions to adminusers
    perms = Permission.objects.all()
    for p in perms:
        new_group.permissions.add(p)
    if verbose:
        print('Added full-permissions to "adminusers"')
    
    #add the admin user to adminusers group
    admin_user.groups.add(new_group)
    if verbose:
        print('Added admin user to "adminusers"')
#        
    """make a sample read-only usergroup group"""  
    new_usergroup, created = Group.objects.get_or_create(name='usergroup1')
    if verbose and created:
        print('New group "usergroup1" created')
    elif not created:
        print('"usergroup1" group already exists, or failed to create')

    #add the admin user to user group
    admin_user.groups.add(new_usergroup)
    if verbose:
        print('Added admin user to "usergroup1"')
    
    return new_group,new_usergroup

def make_default_index(new_usergroup,verbose=True,corename='coreexample'):
    """install a default solr index"""
    
    #check if default exists
    try:
        s=Index.objects.get(corename=corename)
        #make it part of usergroup1
        s.usergroup=new_usergroup
        s.save()
        
    except Index.DoesNotExist:
        if verbose:
            print('Installing \"{}\"'.format(corename))
        #add the default index, adding to usergroup1
        s,screated=Index.objects.get_or_create(corename=corename,usergroup=new_usergroup, coreDisplayName='Example index')
        
        if verbose and screated:
            print('Solr index installed: {}'.format(s))
        elif not screated:
            print('\'{}\' solr index already installed, or failed to create'.format(corename))
            

def check_solr(verbose=True):
    """ check if solr server is operating, and example index is present """
    try:
        server=solr_indexes.SolrServer()
        server.status_check()
        defaultstatus=server.status.get('coreexample')
        if defaultstatus:
            if defaultstatus.get('name')=='coreexample' and defaultstatus['index'].get('current')==True:
                mycore=solrJson.SolrCore('coreexample')
                if mycore.ping():
                    print('Solr server and "coreexample" index operating and installed')
                    
        return server
    except solrJson.SolrCoreNotFound as e:
        print('Solr core "coreexample" not found on solr server: check installation')
        print('\nNo response from url {}'.format(mycore.url))
        return server
    except solrJson.SolrConnectionError as e:
        print('\nError: cannot connect to Solr server')
        print('Solr server needs to be started.\n(You can use shortcut from SearchBox installation folder:\n\b ./lsolr start \b\nor check configs.)')
        return server
    
    """ make a test search, to test further configs """
    page=trysearch(mycore,verbose=verbose)
#    print('DUMMY SEARCH RESULT PAGE: {}'.format(page.__dict__))
    
    print('DEFAULTS INSTALLATION COMPLETE')
    return
        
def trysearch(mycore,verbose=True):
    if verbose:
        print('Running dummy search ...')
    page_number=1
    searchterm='Trump'
    page=pages.SearchPage(page_number=page_number,searchterm=searchterm,direction='',pagemax=0,sorttype='relevance',tag1field='',tag1='',tag2field='',tag2='',tag3field='',tag3='')
    #GET PARAMETERS
    page.safe_searchterm() #makes searchterm_urlsafe; all unicode 
    page.add_filters()       
    page.startnumber=0
    page.faceting=True
    page.mycore=mycore
    solrJson.pagesearch(page)
    if verbose:
        print('Search complete.')
    return page


    
    
    
