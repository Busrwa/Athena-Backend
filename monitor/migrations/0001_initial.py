from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='AlertLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('symbol', models.CharField(max_length=20)),
                ('signal', models.CharField(max_length=10)),
                ('score', models.IntegerField()),
                ('price', models.DecimalField(decimal_places=2, max_digits=12)),
                ('email_sent', models.BooleanField(default=False)),
                ('sent_at', models.DateTimeField(auto_now_add=True)),
                ('note', models.TextField(blank=True)),
            ],
            options={'ordering': ['-sent_at']},
        ),
        migrations.CreateModel(
            name='InvestmentPlan',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('symbol', models.CharField(max_length=20)),
                ('budget_tl', models.DecimalField(decimal_places=2, max_digits=12)),
                ('entry_price', models.DecimalField(decimal_places=2, max_digits=12, null=True, blank=True)),
                ('target_return_pct', models.DecimalField(decimal_places=2, default=15, max_digits=6)),
                ('stop_loss_pct', models.DecimalField(decimal_places=2, default=7, max_digits=6)),
                ('is_active', models.BooleanField(default=True)),
                ('athena_advice', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={'ordering': ['-created_at']},
        ),
    ]