# Generated by Django 2.0.2 on 2018-02-13 07:43

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('documents', '0025_useredit_corename'),
    ]

    operations = [
        migrations.AlterField(
            model_name='collection',
            name='path',
            field=models.FilePathField(allow_files=False, allow_folders=True, max_length=150, path='/Volumes/Crypt/ownCloud/', recursive=True, verbose_name='File path'),
        ),
        migrations.AlterField(
            model_name='file',
            name='filepath',
            field=models.FilePathField(path='/Volumes/Crypt/ownCloud/', recursive=True, verbose_name='File path'),
        ),
    ]
