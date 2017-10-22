# -*- coding: utf-8 -*-
"""
SEARCH VIEWS

"""
from __future__ import unicode_literals
from .forms import SearchForm
from documents.models import File,Collection,SolrCore
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.http import HttpResponseRedirect
#from parseresults import parseSolrResults as parse
#import pickle, re, sys
#from search_solr import solrSearch
import solrSoup, re, os, logging, unicodedata
from usersettings import userconfig as config
log = logging.getLogger('ownsearch')

#set up solr indexes
cores=solrSoup.getcores()
defaultcoreID=config['Solr']['defaultcoreid']
if defaultcoreID not in cores:
    try:
        defaultcoreID=cores.keys()[0]  #take any old core, if default not found
    except:
        defaultcoreID='1' #get any cores.

@login_required
def do_search(request,page=0,searchterm='',direction='',pagemax=0,sorttype=''):

#GET THE INDEX get the solr index, a SolrCore object, or choose the the default
    if 'mycore' not in request.session:  #set default if no core selected
        request.session['mycore']=defaultcoreID
    coreID=request.session.get('mycore')
    if coreID in cores:
        mycore=cores[coreID]
    else:
        return HttpResponse('Missing config data for selected index ; retry')

#SET THE RESULT PAGE    
    page=int(page) #urls always returns strings only
    #print('page',page,'searchterm',searchterm,'direction',direction)
    if direction == 'next':
        page=page+1
    if direction == 'back':
        page=page-1
    #print('page',page)

#DO SEARCH IF PAGE ESTABLISHED 
    if page > 0: #if page value not default (0) then proceed directly with search
        form = SearchForm()
        resultlist,resultcount=solrSoup.solrSearch(searchterm,sorttype,(page-1)*10,core=mycore)
        pagemax=int(resultcount/10)+1

#PROCESS FORM DATA - INDEX AND SEARCHTERM CHOICES AND THEN DO FIRST SEARCH
    # if this is a POST request we need to process the form data
    elif request.method == 'POST': #if data posted from form
        # create a form instance and populate it with data from the request:
        form = SearchForm(request.POST)
        # check whether it's valid:
        if form.is_valid():
            # process the data in form.cleaned_data as required
            #print(form)
            searchterm=form.cleaned_data['search_term']
            sorttype=form.cleaned_data['SortType']
            coreselect=form.cleaned_data['CoreChoice']
            if coreselect != coreID:  #NEW INDEX SELECTED
                #print('change core')
                coreID=coreselect  #new solr core ID
                request.session['mycore']=coreID  #store the chosen index
                mycore=cores[coreID]  #select new SolrCore object
            #print (coreselect)
            if True:
                resultlist,resultcount=solrSoup.solrSearch(searchterm,sorttype,0,core=mycore)
                pagemax=int(resultcount/10)+1
                if resultcount > 10:
                    page = 1
                else:
                    page = 0
#commented out for debug: convert above into try statement
#            except Exception, e: #exception on SOlr connection should be caught in solrSoup
#                print ('error in do search',str(e))
#                resultlist=[]
#                resultcount=-1
#negative resultcount is used as an error code; -2 sent from solrSoup is connnection error

    # if a GET (or any other method) we'll create a blank form
    else:
        form = SearchForm()
        resultlist = []
        resultcount=-1
    #print (resultlist)
    return render(request, 'searchform.html', {'form': form, 'pagemax': pagemax, 'results': resultlist, 'searchterm': searchterm, 'resultcount': resultcount, 'page':page, 'sorttype': sorttype})

@login_required
def download(request,doc_relpath): #download a document from the docstore
    file_path = os.path.join(docbasepath,doc_relpath)    
    #print ('FILEPATHS (relative/full)',doc_relpath,file_path)
    if os.path.exists(file_path):
        cleanfilename=slugify(os.path.basename(file_path))
        with open(file_path, 'rb') as thisfile:
            response=HttpResponse(thisfile.read(), content_type='application/force-download')
            response['Content-Disposition'] = 'inline; filename=' + cleanfilename
            return response
        raise Http404
    else:
        return HttpResponse('File not stored on server')


##NOT IN USE _ THIS RETURNS FULL CONTENT WHICH WOULD BE TOO LARGE IF MASSIVE FILE
#@login_required
#def oldget_content(request,doc_id,searchterm): #make a page showing the extracted text, highlighting searchterm
#    #load solr index in use, SolrCore object
#    coreID=request.session.get('mycore')
#    if coreID:
#        mycore=cores[coreID]
#        
#            
#        results=solrSoup.getcontents(doc_id,core=mycore)
#        if len(results)>0:
#            result=results[0]
#            docsize=result['solrdocsize']
#            docpath=result['docpath']
#            rawtext=result['rawtext']
#            docname=result['docname']
#            hashcontents=result['hashcontents'] 
#        #check if file available for download
#            if os.path.exists(os.path.join(docbasepath,docpath)):
#                local=True
#            else:
#                local=False
#                print('File does not exist locally')
#        #check if file is registered and authorised to download
#            files=File.objects.filter(hash_contents=hashcontents)
#            if files.count()>0:
#                print(files,'authorised')
#                auth=True
#            else:
#                auth=False
#        #clean up the text for display
#            cleaned=re.sub('(\n[\s]+\n)+', '\n', rawtext) #cleaning up chunks of white space
#            lastscrap=''
#            try:
#                splittext=re.split(searchterm,cleaned,flags=re.IGNORECASE) #make a list of text scraps, removing search term
#                if len(splittext) > 1:
#                    lastscrap=splittext.pop() #remove last entry if more than one, as this last is NOT followed by searchterm
#            except:
#                splittext=[cleaned]
#            return render(request, 'contentform.html', {'docsize':docsize, 'doc_id': doc_id, 'splittext': splittext, 'searchterm': searchterm, 'lastscrap': lastscrap, 'docname':docname, 'docpath':docpath, 'docexists':local})
#        else:
#            return HttpResponse('Can\'t find document with ID '+doc_id+' COREID: '+coreID)
#    else:
#        return HttpResponseRedirect('/') 

@login_required
def get_content(request,doc_id,searchterm): #make a page showing the extracted text, highlighting searchterm
    #load solr index in use, SolrCore object
    coreID=request.session.get('mycore')
    if coreID:
        mycore=cores[coreID]
        contentsmax=50000
        #TEMP DEBUG
        results=solrSoup.gettrimcontents(doc_id,mycore,searchterm)
#        return HttpResponse(results)     
        if len(results)>0:
            result=results[0]
            if 'highlight' in results[0]:
                highlight=results[0]['highlight']
            else:
                highlight=''
            #print len(highlight)
            
            #detect if large file (contents greater or equal to max size)
            if len(highlight)==contentsmax:
               print('max contents')
               #go get large highlights instead
               res=get_bigcontent(request,doc_id,searchterm)
               return res
            docsize=result['solrdocsize']
            docpath=result['docpath']
            rawtext=result['rawtext']
            docname=result['docname']
            hashcontents=result['hashcontents']

        #check if file available for download
            if os.path.exists(os.path.join(docbasepath,docpath)):
                local=True
            else:
                local=False
                print('File does not exist locally')
        #check if file is registered and authorised to download
            files=File.objects.filter(hash_contents=hashcontents)
            if files.count()>0:
                #print(files,'authorised')
                auth=True
            else:
                auth=False
        #clean up the text for display
#            return HttpResponse(highlight)
            cleaned=re.sub('(\n[\s]+\n)+', '\n\n', highlight) #cleaning up chunks of white space
            #print cleaned
#            cleaned=highlight
            lastscrap=''
            try:
                splittext=re.split(searchterm,cleaned,flags=re.IGNORECASE) #make a list of text scraps, removing search term
                if len(splittext) > 1:
                    lastscrap=splittext.pop() #remove last entry if more than one, as this last is NOT followed by searchterm
            except:
                splittext=[cleaned]
            return render(request, 'contentform.html', {'docsize':docsize, 'doc_id': doc_id, 'splittext': splittext, 'searchterm': searchterm, 'lastscrap': lastscrap, 'docname':docname, 'docpath':docpath, 'docexists':local})
        else:
            return HttpResponse('Can\'t find document with ID '+doc_id+' COREID: '+coreID)
    else:
        return HttpResponseRedirect('/') 



@login_required
def testsearch(request,doc_id,searchterm):
    coreID=request.session.get('mycore')
    if coreID:
        mycore=cores[coreID]
        results=solrSoup.testresponse(doc_id,mycore,searchterm)
        print results
        if len(results)>0:
            if 'highlight' in results[0]:
                highlight=results[0]['highlight']
                return HttpResponse(highlight)
        return HttpResponse(results)
    else:
        return HttpResponseRedirect('/')        
        
@login_required
def get_bigcontent(request,doc_id,searchterm): #make a page of highlights, for MEGA files
	  #load solr index in use, SolrCore object
    coreID=request.session.get('mycore')
    if coreID:
        mycore=cores[coreID]
        
        results=solrSoup.bighighlights(doc_id,mycore,searchterm)
#        print (str(results))
#        return HttpResponse(str(results))
        if len(results)>0:

            result=results[0]
            docsize=result['solrdocsize']
            docpath=result['docpath']
            rawtext=result['rawtext']
            docname=result['docname']
            hashcontents=result['hashcontents']
            highlights=result['highlight'] 
        #check if file available for download
            if os.path.exists(os.path.join(docbasepath,docpath)):
                local=True
            else:
                local=False
                print('File does not exist locally')
        #check if file is registered and authorised to download
            files=File.objects.filter(hash_contents=hashcontents)
            if files.count()>0:
                #print(files,'authorised') #DEBUG : need to add user check to authorise
                auth=True
            else:
                auth=False

        #clean up the text for display
#            if highlights:
#                firstscrap=highlights.pop(0)[0]
#            
#            else:
#                firstscrap=''
#            cleaned=re.sub('(\n[\s]+\n)+', '\n', rawtext) #cleaning up chunks of white space
#            
#            lastscrap=''
#            try:
#                splittext=re.split(searchterm,cleaned,flags=re.IGNORECASE) #make a list of text scraps, removing search term
#                if len(splittext) > 1:
#                    lastscrap=splittext.pop() #remove last entry if more than one, as this last is NOT followed by searchterm
#            except:
#                splittext=[cleaned]
#            print ('HIGHLIGHTS:' , highlights)
            
#            parsedhl=[]
#            for highlight in highlights:
#                parsedhl.append([highlight.replace('<em>','<b>').replace('</em>','</b>'),'TEST'])
#                
#            teststring=[['cat','dog'],['elephant\n\n cat','mousen\n\xa0 cat'],['', ' \n \n \n \n \n \n \n \n \n \n \n \n \n \n \n \n \n \n \n \n \n \n \n \n \n \n \n \n \n \n \n \n \n \n \n \n \n \n \n \n \n \n \n \n \n \n \n 2016-10-01 Donald '], [u'Trump', u' Tax Records Show He Could Have Avoided Taxes for Nearly Two Decades, The Times Found\n \n By DAVID BARSTOW, SUSANNE CRAIG, RUSS BUETTNER and MEGAN TWOHEYOCT. 1, 2016\n \n ELECTION 2016 By AINARA TIEFENTH\xc4LER and GABRIEL DANCE 1:22\n \n Trump\u2019s Tax Records\n \n Video\n \n Trump\u2019s Tax Records\n \n The New York Times obtained records from 1995 showing that Donald J. ']]
            return render(request, 'bigcontentform.html', {'docsize':docsize, 'doc_id': doc_id, 'highlights': highlights, 'searchterm': searchterm,'docname':docname, 'docpath':docpath, 'docexists':local})
        else:
            return HttpResponse('Can\'t find document with ID '+doc_id+' COREID: '+coreID)
    else:
        return HttpResponseRedirect('/') 


def slugify(value):
    """
    Normalizes string, converts to lowercase, removes non-alpha characters,
    and converts spaces to hyphens.
    """
    shortName, fileExt = os.path.splitext(value)
    value = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore')
    value = unicode(re.sub('[^\w\s-]', '', value).strip().lower())
    value = unicode(re.sub('[-\s]+', '-', value))
    return value+fileExt


