# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from django.http import HttpResponse
from django.shortcuts import render
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.models import User, Group, Permission
from ownsearch import authorise
import logging
log = logging.getLogger('ownsearch.testviews')
# Create your views here.

def index(request):
    log.debug(request.__dict__)
    log.debug(request.user)
    this_user=request.user
    log.debug(request.user.__dict__)
    log.debug(type(request.user))
    log.debug(User.objects.all())
    log.debug(Group.objects.all())
    log.debug(this_user.groups.all())
    authcores=authorise.AuthorisedCores(this_user)
    log.debug(authcores.__dict__)
    return HttpResponse ("Test only")


