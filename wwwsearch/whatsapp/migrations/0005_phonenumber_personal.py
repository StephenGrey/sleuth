# -*- coding: utf-8 -*-
# Generated by Django 1.11.4 on 2018-05-16 21:47
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('whatsapp', '0004_auto_20180511_1427'),
    ]

    operations = [
        migrations.AddField(
            model_name='phonenumber',
            name='personal',
            field=models.BooleanField(default=False, verbose_name='Personal'),
        ),
    ]
