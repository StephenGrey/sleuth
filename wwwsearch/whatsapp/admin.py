# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.contrib import admin

# Register your models here.
# Register your models here.
from .models import Message, PhoneNumber

admin.site.register(Message)
admin.site.register(PhoneNumber)
