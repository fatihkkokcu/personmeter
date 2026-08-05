from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0007_alter_person_id'),
    ]

    operations = [
        migrations.AddField(
            model_name='category',
            name='color',
            field=models.CharField(
                choices=[
                    ('#c2603f', 'Clay'),
                    ('#2e7d64', 'Pine'),
                    ('#3f6fa8', 'Denim'),
                    ('#7a5ea8', 'Iris'),
                    ('#b58224', 'Amber'),
                    ('#4a8090', 'Slate blue'),
                    ('#8a6a52', 'Walnut'),
                    ('#a8455f', 'Rose'),
                ],
                default='#69727a',
                help_text="Hex colour used for this category's tags and placeholders.",
                max_length=7,
            ),
        ),
    ]
