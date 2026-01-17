"""
Diagnose cluster issues - check if clusters have voting patterns.

Usage:
    python manage.py diagnose_cluster [cluster_id]
"""

from django.core.management.base import BaseCommand
from core.models import VoterCluster, ClusterVotingPattern, VoterClusterMembership


class Command(BaseCommand):
    help = 'Diagnose cluster issues'

    def add_arguments(self, parser):
        parser.add_argument(
            'cluster_id',
            type=int,
            nargs='?',
            help='Specific cluster ID to diagnose (optional)'
        )

    def handle(self, *args, **options):
        cluster_id = options.get('cluster_id')
        
        # Get latest run
        from core.models import VoterClusterRun
        run = VoterClusterRun.objects.filter(
            status='completed'
        ).order_by('-created_at').first()
        
        if not run:
            self.stdout.write(self.style.ERROR('No completed clustering run found'))
            return
        
        self.stdout.write(f"Analyzing run: {run.id} (created: {run.created_at})")
        self.stdout.write("=" * 80)
        
        if cluster_id is not None:
            clusters = run.clusters.filter(cluster_id=cluster_id, cluster_type='group')
        else:
            clusters = run.clusters.filter(cluster_type='group').order_by('cluster_id')
        
        for cluster in clusters:
            self.stdout.write(f"\nCluster {cluster.cluster_id}:")
            self.stdout.write(f"  Size: {cluster.size} members")
            self.stdout.write(f"  Consensus: {cluster.consensus_score or 0:.2%}")
            
            # Count voting patterns
            pattern_count = cluster.voting_patterns.count()
            self.stdout.write(f"  Voting patterns: {pattern_count}")
            
            if pattern_count == 0:
                self.stdout.write(self.style.WARNING(
                    f"  ⚠️  WARNING: Cluster has {cluster.size} members but NO voting patterns!"
                ))
                
                # Check if this is a data issue - verify run parameters
                run_params = run.parameters or {}
                time_window = run_params.get('time_window_days', 30)
                self.stdout.write(
                    f"  Run parameters: time_window={time_window}d, "
                    f"min_votes_per_voter={run_params.get('min_votes_per_voter', 3)}"
                )
                
                # Check memberships
                memberships = VoterClusterMembership.objects.filter(cluster=cluster)
                self.stdout.write(f"  Memberships in DB: {memberships.count()}")
                
                # Sample a few members to see if they have votes and which noticias
                sample_members = memberships[:5]
                if sample_members:
                    self.stdout.write("  Sample members:")
                    from core.models import Voto
                    all_noticia_ids = set()
                    individual_noticia_sets = []
                    
                    run_params = run.parameters or {}
                    time_window = run_params.get('time_window_days', 30)
                    min_votes = run_params.get('min_votes_per_voter', 3)
                    from django.utils import timezone
                    from datetime import timedelta
                    cutoff_date = timezone.now() - timedelta(days=time_window)
                    
                    for membership in sample_members:
                        if membership.voter_type == 'user':
                            all_votes = Voto.objects.filter(usuario_id=membership.voter_id)
                            recent_votes = all_votes.filter(fecha_voto__gte=cutoff_date)
                        else:  # session
                            all_votes = Voto.objects.filter(session_key=membership.voter_id)
                            recent_votes = all_votes.filter(fecha_voto__gte=cutoff_date)
                        
                        total_vote_count = all_votes.count()
                        recent_vote_count = recent_votes.count()
                        noticia_ids = set(recent_votes.values_list('noticia_id', flat=True))
                        all_noticia_ids.update(noticia_ids)
                        individual_noticia_sets.append(noticia_ids)
                        
                        qualified = "✓" if recent_vote_count >= min_votes else "✗"
                        self.stdout.write(
                            f"    {qualified} {membership.voter_type}:{membership.voter_id[:20]}... - "
                            f"{recent_vote_count}/{total_vote_count} votes in window "
                            f"on {len(noticia_ids)} noticias"
                        )
                    
                    # Check if there's overlap
                    if len(sample_members) > 1:
                        total_individual = sum(len(s) for s in individual_noticia_sets)
                        self.stdout.write(
                            f"  Total unique noticias in sample: {len(all_noticia_ids)} "
                            f"(sum of individual: {total_individual})"
                        )
                        if len(all_noticia_ids) == total_individual:
                            self.stdout.write(self.style.WARNING(
                                "  ⚠️  No overlap: Each member voted on different noticias!"
                            ))
                        else:
                            overlap_count = total_individual - len(all_noticia_ids)
                            self.stdout.write(
                                f"  ✓ Overlap detected: {overlap_count} shared votes"
                            )
                            
                            # Check if these noticias are in the time window
                            from django.utils import timezone
                            from datetime import timedelta
                            from core.models import Voto
                            
                            time_window = run.parameters.get('time_window_days', 30) if run.parameters else 30
                            cutoff_date = timezone.now() - timedelta(days=time_window)
                            
                            recent_votes = Voto.objects.filter(
                                noticia_id__in=all_noticia_ids,
                                fecha_voto__gte=cutoff_date
                            ).values_list('noticia_id', flat=True).distinct()
                            
                            self.stdout.write(
                                f"  Noticias in time window ({time_window}d): "
                                f"{len(set(recent_votes))} out of {len(all_noticia_ids)}"
                            )
                            
                            if len(set(recent_votes)) < len(all_noticia_ids):
                                self.stdout.write(self.style.WARNING(
                                    f"  ⚠️  Some noticias voted by members are OUTSIDE time window!"
                                ))
            else:
                # Show top patterns
                top_patterns = cluster.voting_patterns.order_by('-consensus_score')[:3]
                self.stdout.write("  Top voting patterns:")
                for pattern in top_patterns:
                    self.stdout.write(
                        f"    Noticia {pattern.noticia_id}: "
                        f"{pattern.count_buena}B/{pattern.count_mala}M/{pattern.count_neutral}N "
                        f"(consensus: {pattern.consensus_score:.2%})"
                    )
