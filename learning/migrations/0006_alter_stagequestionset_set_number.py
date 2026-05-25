import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('learning', '0005_alter_learningstage_stage_number_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='stagequestionset',
            name='set_number',
            field=models.PositiveSmallIntegerField(validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(3)], verbose_name='شماره نمونه سوال'),
        ),
    ]
