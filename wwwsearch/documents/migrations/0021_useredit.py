# -*- coding: utf-8 -*-
# Generated by Django 1.11.4 on 2018-01-17 18:19
from __future__ import unicode_literals

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('documents', '0020_file_child'),
    ]

    operations = [
        migrations.CreateModel(
            name='UserEdit',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('solrid', models.CharField(blank=True, default='', max_length=100, verbose_name='Solr ID')),
                ('usertags', models.CharField(blank=True, default='', max_length=31, verbose_name='New user tags')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
