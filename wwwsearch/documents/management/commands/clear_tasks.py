# -*- coding: utf-8 -*-

from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand, CommandError
from documents import redis_cache



class Command(BaseCommand):
    help = 'clear redis tasks'
    
    def handle(self, *args, **options):
        r=redis_cache.redis_connection
        r.flushall()
        
        print("""
Cleared all tasks in redis
                            """)
