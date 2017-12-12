# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from django.shortcuts import render
from .models import BlogPost
from django.http import HttpResponse
from django.http import HttpResponseRedirect

# Create your views here.

def scrapeview(request):
    return HttpResponseRedirect('/scraper/id=9000')

def blogview(request,doc_id):
    docid=int(doc_id)
    try:
        body=BlogPost.objects.get(id=docid).body
    except BlogPost.DoesNotExist:
        body=None
    #return HttpResponse(b.body)
    return render(request, 'blogpost.html', {'body':body, 'docid':docid})