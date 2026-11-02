from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("learning", "0008_split_learning_stage_content_fields"),
    ]

    operations = [
        migrations.AlterField(
            model_name="stagequestion",
            name="question_type",
            field=models.CharField(
                choices=[
                    ("multiple_choice", "چهارگزینه‌ای"),
                    ("true_false", "صحیح-غلط"),
                    ("short_answer", "کوتاه پاسخ"),
                    ("descriptive", "تشریحی"),
                ],
                max_length=20,
                verbose_name="نوع سوال",
            ),
        ),
        migrations.AlterField(
            model_name="stagequestion",
            name="correct_answer",
            field=models.TextField(verbose_name="پاسخ صحیح"),
        ),
        migrations.AddField(
            model_name="stagequestion",
            name="ai_rubric",
            field=models.TextField(
                blank=True,
                help_text="برای سوال تشریحی: مفاهیمی که باید در پاسخ باشد، هر کدام در یک خط.",
                verbose_name="نکات کلیدی برای تصحیح هوشمند (اختیاری)",
            ),
        ),
        migrations.AlterField(
            model_name="userexamanswer",
            name="user_answer",
            field=models.TextField(blank=True, verbose_name="پاسخ کاربر"),
        ),
        migrations.AddField(
            model_name="userexamanswer",
            name="ai_similarity",
            field=models.PositiveSmallIntegerField(
                blank=True,
                null=True,
                verbose_name="درصد تطابق هوش مصنوعی",
            ),
        ),
        migrations.AddField(
            model_name="userexamanswer",
            name="ai_feedback",
            field=models.TextField(blank=True, verbose_name="بازخورد هوش مصنوعی"),
        ),
        migrations.AddField(
            model_name="userexamanswer",
            name="ai_graded_at",
            field=models.DateTimeField(
                blank=True,
                null=True,
                verbose_name="زمان تصحیح هوشمند",
            ),
        ),
    ]
