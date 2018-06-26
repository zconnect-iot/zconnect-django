# Generated by Django 2.0.2 on 2018-05-22 09:40

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('zconnect', '0002_create_other_models'),
        ('organizations', '0003_field_fix_and_editable'),
        ('zc_test_app', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='zctestdevice',
            name='orgs',
            field=models.ManyToManyField(blank=True, help_text="Organizations that 'own' this device", related_name='devices', related_query_name='device', to='organizations.Organization', verbose_name='organizations'),
        ),
        migrations.AddField(
            model_name='zctestdevice',
            name='product',
            field=models.ForeignKey(default=None, on_delete=django.db.models.deletion.PROTECT, to='zconnect.Product'),
            preserve_default=False,
        ),
    ]
