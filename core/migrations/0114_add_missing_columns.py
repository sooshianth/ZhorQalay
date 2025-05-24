from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0113_barbary_varedkonandeh_and_more'),
    ]

    operations = [
        migrations.RunSQL(
            """
            ALTER TABLE core_cargoproduct 
            ADD COLUMN vared_konandeh_id integer REFERENCES core_varedkonandeh(id);
            """,
            """
            ALTER TABLE core_cargoproduct 
            DROP COLUMN vared_konandeh_id;
            """
        ),
    ] 