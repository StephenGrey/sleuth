# -*- coding: utf-8 -*-
"""
SEARCH VIEWS

Derived originally from Django forms tutorial 
https://docs.djangoproject.com/en/1.11/topics/forms/
https://docs.djangoproject.com/en/1.11/ref/forms/api/   getting data back from forms
plus looking at simple search page in haystack templates.
https://docs.djangoproject.com/en/1.11/topics/auth/default/ authentication

"""
from __future__ import unicode_literals
from .forms import SearchForm
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.http import HttpResponseRedirect
#from parseresults import parseSolrResults as parse
#import pickle, re, sys
#from search_solr import solrSearch
import solrSoup, re, os, logging
from usersettings import userconfig as config
log = logging.getLogger('ownsearch')
core=config['Cores']['coredefault'] #the name of the index to use within the Solr backend


@login_required
def do_search(request,page=0,searchterm='',direction='',pagemax=0,sorttype=''):
    page=int(page) #urls always returns strings only
    #print('page',page,'searchterm',searchterm,'direction',direction)
    if direction == 'next':
        page=page+1
    if direction == 'back':
        page=page-1
    #print('page',page)
    if page > 0: #if page already set then proceed directly with search
        form = SearchForm()
        resultlist,resultcount=solrSoup.solrSearch(searchterm,sorttype,(page-1)*10)
        pagemax=int(resultcount/10)+1
    # if this is a POST request we need to process the form data
    elif request.method == 'POST': #if data posted from from
        # create a form instance and populate it with data from the request:
        form = SearchForm(request.POST)
        # check whether it's valid:
        if form.is_valid():
            # process the data in form.cleaned_data as required
            #print(form)
            searchterm=form.cleaned_data['search_term']
            sorttype=form.cleaned_data['SortType']
            try:
                resultlist,resultcount=solrSoup.solrSearch(searchterm,sorttype,0)
                pagemax=int(resultcount/10)+1
                if resultcount > 10:
                    page = 1
                else:
                    page = 0
            except Exception, e: #exception on SOlr connection should be caught in solrSoup
                print str(e)
                resultlist=[]
                resultcount=-1
#negative resultcount is used as an error code; -2 sent from solrSoup is connnection error

    # if a GET (or any other method) we'll create a blank form
    else:
        form = SearchForm()
        resultlist = []
        resultcount=-1

    return render(request, 'searchform.html', {'form': form, 'pagemax': pagemax, 'results': resultlist, 'searchterm': searchterm, 'resultcount': resultcount, 'page':page, 'sorttype': sorttype})

def get_content(request,doc_id,searchterm): #make a page showing the extracted text, highlighting searchterm
    result=solrSoup.getcontents(doc_id)[0]
    rawtext=result[config[core]['rawtext']]
    docname=result['docname'] 
    docpath=result[config[core]['docpath']]
    cleaned=re.sub('(\n[\s]+\n)+', '\n', rawtext) #cleaning up chunks of white space
    lastscrap=''
    try:
        splittext=re.split(searchterm,cleaned,flags=re.IGNORECASE) #make a list of text scraps, removing search term
        if len(splittext) > 1:
            lastscrap=splittext.pop() #remove last entry if more than one, as this last is NOT followed by searchterm
    except:
        splittext=[cleaned]
    return render(request, 'contentform.html', {'doc_id': doc_id, 'splittext': splittext, 'searchterm': searchterm, 'lastscrap': lastscrap, 'docname':docname, 'docpath':docpath})


