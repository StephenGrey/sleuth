# -*- coding: utf-8 -*-
# Generated by Django 1.11.4 on 2017-10-07 17:04
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('documents', '0014_auto_20170925_0955'),
    ]

    operations = [
        migrations.AddField(
            model_name='solrcore',
            name='corename',
            field=models.CharField(default='', max_length=20, verbose_name='Corename'),
        ),
    ]
