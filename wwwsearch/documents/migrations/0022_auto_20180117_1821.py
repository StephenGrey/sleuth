# -*- coding: utf-8 -*-
# Generated by Django 1.11.4 on 2018-01-17 18:21
from __future__ import unicode_literals

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('documents', '0021_useredit'),
    ]

    operations = [
        migrations.AlterField(
            model_name='useredit',
            name='user',
            field=models.ForeignKey(blank=True, on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL),
        ),
    ]