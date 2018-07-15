# Generated by Django 2.0.6 on 2018-07-14 07:05

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('documents', '0030_useredit_index_updated'),
    ]

    operations = [
        migrations.CreateModel(
            name='SyncStatus',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('remote_useredit_lastid', models.IntegerField(default=0, verbose_name='Last imported edit id')),
            ],
        ),
    ]
