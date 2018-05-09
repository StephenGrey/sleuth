# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from django.http import HttpResponse
from django.shortcuts import render
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.models import User, Group, Permission
from ownsearch import authorise

# Create your views here.

def index(request):
    print(request.__dict__)
    print(request.user)
    this_user=request.user
    print(request.user.__dict__)
    print(type(request.user))
    print(User.objects.all())
    print(Group.objects.all())
    print(this_user.groups.all())
    authcores=authorise.AuthorisedCores(this_user)
    print(authcores.__dict__)
    return HttpResponse ("Test only")


