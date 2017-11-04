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
from django.db.models.base import ObjectDoesNotExist
#from parseresults import parseSolrResults as parse
#import pickle, re, sys
#from search_solr import solrSearch
import solrSoup, re, os, logging, unicodedata
from usersettings import userconfig as config
log = logging.getLogger('ownsearch')
docbasepath=config['Models']['collectionbasepath']

#cores=solrSoup.getcores()
#print(cores)
#defaultcoreID=config['Solr']['defaultcoreid']
#if defaultcoreID not in cores:
#    try:
#        defaultcoreID=cores.keys()[0]  #take any old core, if default not found
#    except Exception as e:
#        defaultcoreID='1' #and if no cores defined , just make it 1
#docbasepath=config['Models']['collectionbasepath']

##set up solr indexes
@login_required
def authcores(request):
    cores={}
    choice_list=()
    thisuser=request.user
    groupids=[group.id for group in thisuser.groups.all()]
    corelist=(SolrCore.objects.filter(usergroup_id__in=groupids))
    
    for core in corelist:
        cores[core.id]=solrSoup.SolrCore(core.corename)
        corenumber=str(core.id)
        coredisplayname=core.coreDisplayName
        choice_list +=((corenumber,coredisplayname),) #value/label
    try:
        defaultcoreID=int(config['Solr']['defaultcoreid'])
        assert defaultcoreID in cores
                
    except Exception as e:
        print(e)
        try:
            defaultcoreID=cores.keys()[0]  #take any old core, if default not found
        except Exception as e:
            print(e)
            cores={}
            defaultcoreID=0
    return cores, defaultcoreID, choice_list

def authfile(request,hashcontents):
    matchfiles=File.objects.filter(hash_contents=hashcontents)
    #collection that contain the file
    collection_ids=[matchfile.collection_id for matchfile in matchfiles]
    #indexes that contain the file
    coreids=[collection.core_id for collection in Collection.objects.filter(id__in=collection_ids)]
    #user groups that user belongs to
    authgroupids=[group.id for group in request.user.groups.all()]
    #indexes that user is authorised for
    authcoreids=[core.id for core in SolrCore.objects.filter(usergroup_id__in=authgroupids)]
    #test if indexes containing file match authorised indexes
    if not set(authcoreids).isdisjoint(coreids):
        print('authorised for download')
        for matchfile in matchfiles:
            if os.path.exists(matchfile.filepath):
                return matchfile
    return None
        
def authid(request,doc):
    coreid=Collection.objects.get(id=doc.collection_id).core_id
    #print(coreid)
    #user groups that user belongs to
    authgroupids=[group.id for group in request.user.groups.all()]
    #print(authgroupids)
    #indexes that user is authorised for
    authcoreids=[core.id for core in SolrCore.objects.filter(usergroup_id__in=authgroupids)]
    #print(authcoreids)
    if coreid in authcoreids:
        return True
    else:
        return False


@login_required
def do_search(request,page=0,searchterm='',direction='',pagemax=0,sorttype=''):

#GET AUTHORISED CORES AND DEFAULT
    corelist,defaultcoreID,choice_list=authcores(request)
    print(choice_list)
#GET THE INDEX get the solr index, a SolrCore object, or choose the default
    if 'mycore' not in request.session:  #set default if no core selected
        request.session['mycore']=defaultcoreID
    coreID=int(request.session.get('mycore'))
    if coreID in corelist:
        mycore=corelist[coreID]
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
        form = SearchForm(choice_list,str(coreID))
        resultlist,resultcount=solrSoup.solrSearch(searchterm,sorttype,(page-1)*10,core=mycore)
        pagemax=int(resultcount/10)+1

#PROCESS FORM DATA - INDEX AND SEARCHTERM CHOICES AND THEN DO FIRST SEARCH
    # if this is a POST request we need to process the form data
    elif request.method == 'POST': #if data posted from form

        # create a form instance and populate it with data from the request:
        form = SearchForm(choice_list,str(coreID),request.POST)
        # check whether it's valid:
        if form.is_valid():
            # process the data in form.cleaned_data as required
            #print(form)
            searchterm=form.cleaned_data['search_term']
            sorttype=form.cleaned_data['SortType']
            coreselect=int(form.cleaned_data['CoreChoice'])
            if coreselect != coreID:  #NEW INDEX SELECTED
                #print('change core')
                coreID=coreselect  #new solr core ID
                request.session['mycore']=coreID  #store the chosen index
                mycore=corelist[coreID]  #select new SolrCore object
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
        form = SearchForm(choice_list,str(coreID))
        resultlist = []
        resultcount=-1
    #print (resultlist)
    return render(request, 'searchform.html', {'form': form, 'pagemax': pagemax, 'results': resultlist, 'searchterm': searchterm, 'resultcount': resultcount, 'page':page, 'sorttype': sorttype})

@login_required
def download(request,doc_id,hashfilename): #download a document from the docstore
    #print doc_id,hashfilename
    
    #MAKE CHECKS BEFORE DOWNLOAD
    #check file exists in database and hash matches
    try:
        thisfile=File.objects.get(id=doc_id)
        assert thisfile.hash_filename==hashfilename
    except AssertionError as e:
        print ('Hash Mismatch Error',e)
        return HttpResponse('File not stored on server')
    except ObjectDoesNotExist as e:
        print ('File ID does not exist',e)
        return HttpResponse('File not stored on server')
    #check user authorised to download
    if authid(request,thisfile) is False:
        return HttpResponse('File NOT authorised for download')    
    #DEBUG THE DOWNLOAD SHOULD BE LOGGED

    file_path = thisfile.filepath
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
    coreID=int(request.session.get('mycore'))
    corelist,defaultcoreID,choice_list=authcores(request)
    
    if coreID:
        mycore=corelist[coreID]
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
            
            matchfile=authfile(request,hashcontents)
            if matchfile is None:
                auth=False
                matchfileid=''
                hashfilename=''
            else:
                print(matchfile.filename)
                auth=True
                matchfile_id=matchfile.id
                hashfilename=matchfile.hash_filename
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
            return render(request, 'contentform.html', {'docsize':docsize, 'doc_id': doc_id, 'splittext': splittext, 'searchterm': searchterm, 'lastscrap': lastscrap, 'docname':docname, 'docpath':docpath, 'hashfile':hashfilename, 'fileid':matchfile_id,'docexists':local})
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
    coreID=int(request.session.get('mycore'))
    corelist,defaultcoreID,choice_list=authcores(request)
    if coreID:
        mycore=corelist[coreID]
        
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


