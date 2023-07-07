# Generated by Django 2.1.7 on 2021-04-23 08:06

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('whatsapp', '0005_phonenumber_personal'),
    ]

    operations = [
        migrations.AddField(
            model_name='message',
            name='attach1_path',
            field=models.CharField(default='', max_length=200, verbose_name='Attach1'),
        ),
        migrations.AddField(
            model_name='message',
            name='attach2_path',
            field=models.CharField(default='', max_length=200, verbose_name='Attach2'),
        ),
        migrations.AddField(
            model_name='message',
            name='attachments_number',
            field=models.IntegerField(default=0, verbose_name='Attachments'),
        ),
        migrations.AddField(
            model_name='message',
            name='messagetype',
            field=models.CharField(default='WhatsApp', max_length=30, verbose_name='Message_Type'),
        ),
        migrations.AddField(
            model_name='phonenumber',
            name='photo_path',
            field=models.CharField(default='', max_length=200, verbose_name='PhotoPath'),
        ),
    ]
