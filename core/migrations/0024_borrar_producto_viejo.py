# Borra el producto anterior (votar noticias, mapa de clusters, perfiles).
# Sin datos que conservar. Hijos antes que padres para que SQLite y Postgres
# no tengan que reescribir tablas campo por campo.

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0023_add_reengagement_email_enabled"),
    ]

    operations = [
        migrations.DeleteModel(name="ClusterVotingPattern"),
        migrations.DeleteModel(name="NoticiaEntidad"),
        migrations.DeleteModel(name="NoticiaProjection"),
        migrations.DeleteModel(name="VoterProjection"),
        migrations.DeleteModel(name="VoterClusterMembership"),
        migrations.DeleteModel(name="Voto"),
        migrations.DeleteModel(name="ReengagementEmailLog"),
        migrations.DeleteModel(name="UserProfile"),
        migrations.DeleteModel(name="ClusterNameCache"),
        migrations.DeleteModel(name="VoterCluster"),
        migrations.DeleteModel(name="VoterClusterRun"),
        migrations.DeleteModel(name="Noticia"),
    ]
