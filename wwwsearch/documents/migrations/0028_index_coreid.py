# Generated by Django 2.0.6 on 2018-06-29 19:19

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('documents', '0027_auto_20180322_0923'),
    ]

    operations = [
        migrations.AddField(
            model_name='index',
            name='coreID',
            field=models.CharField(default='', max_length=10, verbose_name='Core ID (1-10)'),
        ),
    ]
