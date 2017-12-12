# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.contrib import admin

from .models import BlogPost, Tag

admin.site.register(BlogPost)
admin.site.register(Tag)


# Register your models here.
