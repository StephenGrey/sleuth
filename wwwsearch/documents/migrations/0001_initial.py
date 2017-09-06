# -*- coding: utf-8 -*-
# Generated by Django 1.11.4 on 2017-08-15 05:59
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Collection',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('path', models.FilePathField(max_length=150, path='/~', recursive=True, verbose_name='File path')),
                ('indexedFlag', models.BooleanField(verbose_name='Indexed')),
            ],
        ),
    ]
