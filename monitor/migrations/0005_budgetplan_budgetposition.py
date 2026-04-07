from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('monitor', '0004_alter_papertrade_id'),
    ]

    operations = [
        migrations.CreateModel(
            name='BudgetPlan',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('toplam_butce', models.DecimalField(decimal_places=2, max_digits=14)),
                ('risk_profili', models.CharField(choices=[('dusuk', 'Düşük Risk'), ('orta', 'Orta Risk'), ('yuksek', 'Yüksek Risk')], default='orta', max_length=10)),
                ('max_hisse_sayisi', models.IntegerField(default=3)),
                ('is_active', models.BooleanField(default=True)),
                ('aciklama', models.TextField(blank=True)),
                ('athena_analiz', models.TextField(blank=True)),
                ('son_tarama', models.DateTimeField(blank=True, null=True)),
                ('olusturuldu', models.DateTimeField(auto_now_add=True)),
                ('guncellendi', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Bütçe Planı',
                'verbose_name_plural': 'Bütçe Planları',
                'ordering': ['-olusturuldu'],
            },
        ),
        migrations.CreateModel(
            name='BudgetPosition',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('sembol', models.CharField(max_length=20)),
                ('adet', models.DecimalField(decimal_places=2, max_digits=12)),
                ('giris_fiyat', models.DecimalField(decimal_places=4, max_digits=12)),
                ('stop_fiyat', models.DecimalField(decimal_places=4, max_digits=12)),
                ('hedef_fiyat', models.DecimalField(decimal_places=4, max_digits=12)),
                ('giris_skoru', models.IntegerField(default=0)),
                ('durum', models.CharField(choices=[('bekliyor', 'Athena önerdi, henüz alınmadı'), ('acik', 'Alındı — Açık Pozisyon'), ('hedef', 'Hedef Fiyata Ulaştı'), ('stop', 'Stop-Loss Tetiklendi'), ('kapali', 'Kapatıldı')], default='bekliyor', max_length=15)),
                ('acilis_tarihi', models.DateTimeField(auto_now_add=True)),
                ('kapanis_tarihi', models.DateTimeField(blank=True, null=True)),
                ('cikis_fiyat', models.DecimalField(blank=True, decimal_places=4, max_digits=12, null=True)),
                ('kaz_kayip_tl', models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True)),
                ('kaz_kayip_pct', models.DecimalField(blank=True, decimal_places=2, max_digits=8, null=True)),
                ('athena_not', models.TextField(blank=True)),
                ('plan', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='pozisyonlar', to='monitor.budgetplan')),
            ],
            options={
                'verbose_name': 'Bütçe Pozisyonu',
                'verbose_name_plural': 'Bütçe Pozisyonları',
                'ordering': ['-acilis_tarihi'],
            },
        ),
    ]