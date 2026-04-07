from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('monitor', '0002_alter_alertlog_id_alter_investmentplan_id'),
    ]

    operations = [
        migrations.CreateModel(
            name='PaperTrade',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('sembol', models.CharField(max_length=20)),
                ('strateji', models.CharField(
                    choices=[('kisa', 'Kısa Vade (3-7 gün)'), ('uzun', 'Uzun Vade (1-3 ay)')],
                    default='kisa', max_length=10
                )),
                ('giris_fiyat', models.DecimalField(decimal_places=4, max_digits=12)),
                ('adet', models.DecimalField(decimal_places=4, default=1, max_digits=12)),
                ('sanal_butce', models.DecimalField(decimal_places=2, default=1000, max_digits=12)),
                ('stop_pct', models.DecimalField(decimal_places=2, max_digits=6)),
                ('hedef_pct', models.DecimalField(decimal_places=2, max_digits=6)),
                ('giris_skoru', models.IntegerField(default=0)),
                ('giris_sinyali', models.CharField(default='AL', max_length=20)),
                ('acilis_tarihi', models.DateTimeField(auto_now_add=True)),
                ('durum', models.CharField(
                    choices=[('acik', 'Açık'), ('kapali', 'Normal Kapandı'),
                             ('stop', 'Stop-Loss'), ('hedef', 'Hedef Tuttu')],
                    default='acik', max_length=10
                )),
                ('cikis_fiyat', models.DecimalField(blank=True, decimal_places=4, max_digits=12, null=True)),
                ('cikis_tarihi', models.DateTimeField(blank=True, null=True)),
                ('kaz_kayip_pct', models.DecimalField(blank=True, decimal_places=2, max_digits=8, null=True)),
                ('kaz_kayip_tl', models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True)),
                ('not_alani', models.TextField(blank=True)),
            ],
            options={'ordering': ['-acilis_tarihi']},
        ),
    ]
