"""
Debug aggregation for a specific cluster.

Usage:
    python manage.py debug_aggregation <cluster_id>
"""

from django.core.management.base import BaseCommand
from core.models import VoterCluster, VoterClusterMembership, VoterClusterRun
from core.clustering import build_vote_matrix, compute_cluster_voting_aggregation
from scipy.sparse import issparse
import numpy as np


class Command(BaseCommand):
    help = 'Debug aggregation for a cluster'

    def add_arguments(self, parser):
        parser.add_argument('cluster_id', type=int, help='Cluster ID to debug')

    def handle(self, *args, **options):
        cluster_id = options['cluster_id']
        
        # Get latest run
        run = VoterClusterRun.objects.filter(
            status='completed'
        ).order_by('-created_at').first()
        
        if not run:
            self.stdout.write(self.style.ERROR('No completed clustering run found'))
            return
        
        cluster = run.clusters.filter(
            cluster_id=cluster_id,
            cluster_type='group'
        ).first()
        
        if not cluster:
            self.stdout.write(self.style.ERROR(f'Cluster {cluster_id} not found'))
            return
        
        self.stdout.write(f"Debugging Cluster {cluster_id}")
        self.stdout.write("=" * 80)
        
        # Rebuild vote matrix with same parameters
        run_params = run.parameters or {}
        time_window = run_params.get('time_window_days', 30)
        min_votes = run_params.get('min_votes_per_voter', 3)
        
        self.stdout.write(f"Rebuilding vote matrix: time_window={time_window}d, min_votes={min_votes}")
        vote_matrix, voter_ids_list, noticia_ids_list = build_vote_matrix(
            time_window_days=time_window,
            min_votes_per_voter=min_votes
        )
        
        self.stdout.write(f"Matrix shape: {vote_matrix.shape}")
        self.stdout.write(f"Voters in matrix: {len(voter_ids_list)}")
        self.stdout.write(f"Noticias in matrix: {len(noticia_ids_list)}")
        
        # Get cluster members
        memberships = VoterClusterMembership.objects.filter(cluster=cluster)
        self.stdout.write(f"\nCluster members: {memberships.count()}")
        
        # Map members to matrix indices
        voter_id_to_index = {
            (vt, vid): idx for idx, (vt, vid) in enumerate(voter_ids_list)
        }
        
        cluster_member_indices = []
        members_not_in_matrix = []
        
        for membership in memberships:
            voter_key = (membership.voter_type, membership.voter_id)
            if voter_key in voter_id_to_index:
                cluster_member_indices.append(voter_id_to_index[voter_key])
            else:
                members_not_in_matrix.append(voter_key)
        
        self.stdout.write(f"Members in matrix: {len(cluster_member_indices)}")
        if members_not_in_matrix:
            self.stdout.write(self.style.WARNING(
                f"Members NOT in matrix: {len(members_not_in_matrix)}"
            ))
            for vt, vid in members_not_in_matrix[:3]:
                self.stdout.write(f"  {vt}:{vid[:20]}...")
        
        if not cluster_member_indices:
            self.stdout.write(self.style.ERROR("No cluster members found in matrix!"))
            return
        
        # Get noticias voted by cluster members
        from core.models import Voto
        from django.utils import timezone
        from datetime import timedelta
        
        cutoff_date = timezone.now() - timedelta(days=time_window)
        member_voter_keys = [
            (m.voter_type, m.voter_id) for m in memberships
        ]
        
        # Get all noticias voted by members
        member_noticia_ids = set()
        for vt, vid in member_voter_keys[:10]:  # Sample first 10
            if vt == 'user':
                votes = Voto.objects.filter(usuario_id=vid, fecha_voto__gte=cutoff_date)
            else:
                votes = Voto.objects.filter(session_key=vid, fecha_voto__gte=cutoff_date)
            noticia_ids = set(votes.values_list('noticia_id', flat=True))
            member_noticia_ids.update(noticia_ids)
        
        self.stdout.write(f"\nSample noticias voted by members: {len(member_noticia_ids)}")
        self.stdout.write(f"Noticias in matrix: {len(noticia_ids_list)}")
        
        # Check overlap
        noticias_in_matrix = set(noticia_ids_list)
        overlap = member_noticia_ids & noticias_in_matrix
        self.stdout.write(f"Overlap: {len(overlap)} noticias")
        
        if len(overlap) == 0:
            self.stdout.write(self.style.ERROR(
                "⚠️  PROBLEM: No overlap between member votes and matrix noticias!"
            ))
            self.stdout.write(f"  Member noticias (sample): {sorted(list(member_noticia_ids))[:5]}")
            self.stdout.write(f"  Matrix noticias (sample): {sorted(list(noticias_in_matrix))[:5]}")
        else:
            self.stdout.write(f"  Overlapping noticias: {sorted(list(overlap))[:5]}")
        
        # Try aggregation
        self.stdout.write(f"\nAttempting aggregation with {len(cluster_member_indices)} members...")
        cluster_members_array = np.array(cluster_member_indices)
        
        # Debug: Check what votes are in the matrix for these members
        self.stdout.write("\nDebugging matrix contents:")
        sample_member_idx = cluster_member_indices[0] if cluster_member_indices else None
        if sample_member_idx is not None:
            row = vote_matrix[sample_member_idx, :]
            if issparse(row):
                # Convert to CSR to access indices/data
                row_csr = row.tocsr()
                non_zero_indices = row_csr.indices
                non_zero_values = row_csr.data
                self.stdout.write(
                    f"  Member {sample_member_idx} has {len(non_zero_indices)} votes in matrix"
                )
                if len(non_zero_indices) > 0:
                    sample_noticia_indices = non_zero_indices[:5]
                    self.stdout.write("  Sample noticia indices in matrix:")
                    for nidx in sample_noticia_indices:
                        if nidx < len(noticia_ids_list):
                            self.stdout.write(
                                f"    Index {nidx} -> Noticia {noticia_ids_list[nidx]}"
                            )
                    
                    # Debug: Check if these noticias are found during aggregation
                    self.stdout.write("\n  Checking if these noticias are found during aggregation:")
                    vote_matrix_csr = vote_matrix.tocsr()
                    for nidx in sample_noticia_indices[:3]:
                        if nidx < len(noticia_ids_list):
                            noticia_id = noticia_ids_list[nidx]
                            # Access column the same way as in compute_cluster_voting_aggregation
                            column = vote_matrix_csr[:, nidx]
                            # For CSR, accessing a column returns a column vector (1D)
                            # We need to get the row indices that have non-zero values
                            if issparse(column):
                                # For a column vector CSR, we need to use nonzero() to get row indices
                                # column.nonzero() returns (row_indices, col_indices)
                                row_indices_with_votes, _ = column.nonzero()
                                row_indices_with_votes = row_indices_with_votes.tolist()
                                # Get the data values for those rows
                                data_values = column.data
                            else:
                                # Dense case
                                row_indices_with_votes = np.where(column != 0)[0].tolist()
                                data_values = column[column != 0]
                            
                            cluster_members_in_column = [v for v in cluster_member_indices if v in row_indices_with_votes]
                            
                            # Debug: Check if sample_member_idx is in the column
                            sample_in_column = sample_member_idx in row_indices_with_votes
                            
                            # Also check the actual value in the matrix directly
                            if sample_member_idx < vote_matrix.shape[0] and nidx < vote_matrix.shape[1]:
                                # Access directly from the original matrix
                                row_data = vote_matrix[sample_member_idx, :]
                                if issparse(row_data):
                                    row_csr = row_data.tocsr()
                                    if nidx in row_csr.indices:
                                        idx_pos = np.where(row_csr.indices == nidx)[0]
                                        if len(idx_pos) > 0:
                                            actual_value = row_csr.data[idx_pos[0]]
                                        else:
                                            actual_value = 0.0
                                    else:
                                        actual_value = 0.0
                                else:
                                    actual_value = float(row_data[nidx])
                            else:
                                actual_value = None
                            
                            self.stdout.write(
                                f"    Noticia {noticia_id} (idx {nidx}): "
                                f"{len(row_indices_with_votes)} total votes, "
                                f"{len(cluster_members_in_column)} from cluster, "
                                f"sample member {sample_member_idx} in column: {sample_in_column}, "
                                f"actual value at [{sample_member_idx}, {nidx}]: {actual_value}"
                            )
                            
                            # Debug: Show some of the row indices that voted
                            if len(row_indices_with_votes) > 0:
                                self.stdout.write(
                                    f"      Sample voters who voted: {row_indices_with_votes[:5]}"
                                )
                                self.stdout.write(
                                    f"      Sample cluster members: {cluster_member_indices[:5]}"
                                )
                                # Check if there's any overlap
                                overlap = set(row_indices_with_votes) & set(cluster_member_indices)
                                self.stdout.write(
                                    f"      Overlap: {len(overlap)} members"
                                )
                                if len(overlap) > 0:
                                    self.stdout.write(
                                        f"      Overlapping members: {list(overlap)[:5]}"
                                    )
        
        aggregation = compute_cluster_voting_aggregation(
            cluster_members_array,
            voter_ids_list,
            vote_matrix,
            noticia_ids_list
        )
        
        self.stdout.write(f"\nAggregation result: {len(aggregation)} noticias")
        if aggregation:
            for noticia_id, agg in list(aggregation.items())[:5]:
                self.stdout.write(
                    f"  Noticia {noticia_id}: "
                    f"{agg['buena']}B/{agg['mala']}M/{agg['neutral']}N "
                    f"(total: {agg['total']})"
                )
        else:
            self.stdout.write(self.style.ERROR("⚠️  Aggregation returned empty dict!"))
            # Additional debugging
            self.stdout.write("\nDebugging why aggregation is empty:")
            self.stdout.write(f"  Cluster members: {len(cluster_member_indices)}")
            self.stdout.write(f"  Noticias in list: {len(noticia_ids_list)}")
            self.stdout.write(f"  Matrix shape: {vote_matrix.shape}")
            
            # Check if members have any votes in matrix
            total_votes_in_matrix = 0
            for member_idx in cluster_member_indices[:10]:  # Sample first 10
                row = vote_matrix[member_idx, :]
                if issparse(row):
                    # Convert to CSR to access indices
                    row_csr = row.tocsr()
                    total_votes_in_matrix += len(row_csr.indices)
            self.stdout.write(
                f"  Total votes in matrix (sample of 10 members): {total_votes_in_matrix}"
            )
