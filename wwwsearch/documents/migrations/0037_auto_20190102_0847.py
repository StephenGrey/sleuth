# Generated by Django 2.0.6 on 2019-01-02 08:47

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('documents', '0036_file_error_messsage'),
    ]

    operations = [
        migrations.RenameField(
            model_name='file',
            old_name='error_messsage',
            new_name='error_message',
        ),
    ]
