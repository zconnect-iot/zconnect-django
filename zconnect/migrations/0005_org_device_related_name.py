# Generated by Django 2.0.5 on 2018-05-10 15:45

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('zconnect', '0004_increase_last_name_length'),
    ]

    operations = [
        migrations.AlterField(
            model_name='device',
            name='orgs',
            field=models.ManyToManyField(blank=True, help_text="Organizations that 'own' this device", related_name='devices', related_query_name='device', to='organizations.Organization', verbose_name='organizations'),
        ),
    ]
