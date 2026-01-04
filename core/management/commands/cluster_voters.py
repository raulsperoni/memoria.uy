"""
Management command to manually trigger voter clustering.

Usage:
    python manage.py cluster_voters
    python manage.py cluster_voters --days 60 --min-voters 100
"""

from django.core.management.base import BaseCommand
from core.tasks import update_voter_clusters


class Command(BaseCommand):
    help = 'Manually trigger voter clustering computation'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=30,
            help='Time window in days (default: 30)'
        )
        parser.add_argument(
            '--min-voters',
            type=int,
            default=50,
            help='Minimum voters required (default: 50)'
        )
        parser.add_argument(
            '--min-votes-per-voter',
            type=int,
            default=3,
            help='Minimum votes per voter (default: 3)'
        )
        parser.add_argument(
            '--async',
            action='store_true',
            dest='run_async',
            help='Run as Celery task (async)'
        )

    def handle(self, *args, **options):
        days = options['days']
        min_voters = options['min_voters']
        min_votes = options['min_votes_per_voter']
        run_async = options['run_async']

        self.stdout.write(
            f'Starting voter clustering: '
            f'days={days}, min_voters={min_voters}, '
            f'min_votes_per_voter={min_votes}'
        )

        if run_async:
            # Run as Celery task
            result = update_voter_clusters.delay(
                time_window_days=days,
                min_voters=min_voters,
                min_votes_per_voter=min_votes
            )
            self.stdout.write(
                self.style.SUCCESS(
                    f'Task dispatched: {result.id}'
                )
            )
        else:
            # Run synchronously
            try:
                result = update_voter_clusters(
                    time_window_days=days,
                    min_voters=min_voters,
                    min_votes_per_voter=min_votes
                )

                if 'error' in result:
                    self.stdout.write(
                        self.style.WARNING(f"Error: {result['error']}")
                    )
                else:
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"Clustering complete:\n"
                            f"  Run ID: {result['cluster_run_id']}\n"
                            f"  Voters: {result['n_voters']}\n"
                            f"  Clusters: {result['n_clusters']}\n"
                            f"  Time: {result['computation_time']:.2f}s\n"
                            f"  Silhouette: {result['silhouette_score']:.3f}"
                        )
                    )
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'Clustering failed: {e}')
                )
                raise
