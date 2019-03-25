# Generated by Django 2.1 on 2019-01-10 17:32

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('documents', '0037_merge_20181223_1736'),
    ]

    operations = [
        migrations.RenameField(
            model_name='file',
            old_name='error_messsage',
            new_name='error_message',
        ),
        migrations.AlterField(
            model_name='collection',
            name='path',
            field=models.FilePathField(allow_files=False, allow_folders=True, max_length=150, path='R:\\', recursive=True, verbose_name='File path'),
        ),
        migrations.AlterField(
            model_name='file',
            name='filepath',
            field=models.FilePathField(path='R:\\', recursive=True, verbose_name='File path'),
        ),
    ]