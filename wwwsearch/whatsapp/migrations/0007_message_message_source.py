# Generated by Django 2.1.7 on 2021-04-23 08:14

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('whatsapp', '0006_auto_20210423_0806'),
    ]

    operations = [
        migrations.AddField(
            model_name='message',
            name='message_source',
            field=models.CharField(default='', max_length=30, verbose_name='Source'),
        ),
    ]
