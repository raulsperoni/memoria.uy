from celery import shared_task
from celery.utils.log import get_task_logger
from core.models import (
    Noticia,
    Entidad,
    NoticiaEntidad,
    VoterClusterRun,
    VoterCluster,
    VoterProjection,
    NoticiaProjection,
    VoterClusterMembership,
    ClusterVotingPattern,
    Voto,
)
from core import parse
from django.core.cache import cache
from django.core.mail import get_connection, send_mail
from django.db.models import Max, OuterRef, Q, Subquery
from django.contrib.auth import get_user_model
from django.conf import settings
from functools import wraps
from core import url_requests
from django.utils import timezone
import time
import numpy as np

logger = get_task_logger(__name__)


def task_lock(timeout=60 * 10):
    """
    Decorator that prevents a task from being executed concurrently.
    Uses Django's cache to create a lock based on the task name and arguments.

    Args:
        timeout: Lock timeout in seconds (default: 10 minutes)
    """

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Create a unique lock key based on the task name and arguments
            task_name = func.__name__
            # For tasks with an ID parameter, use it as part of the lock key
            lock_args = []
            for arg in args:
                if isinstance(arg, (int, str)):
                    lock_args.append(str(arg))

            lock_kwargs = []
            for key, value in kwargs.items():
                if isinstance(value, (int, str)):
                    lock_kwargs.append(f"{key}:{value}")

            lock_key = (
                f"task_lock:{task_name}:{':'.join(lock_args)}:{':'.join(lock_kwargs)}"
            )

            # Try to acquire the lock
            acquired = cache.add(lock_key, "locked", timeout)

            if acquired:
                try:
                    # Execute the task
                    return func(*args, **kwargs)
                finally:
                    # Release the lock
                    cache.delete(lock_key)
            else:
                logger.info(
                    f"Task {task_name} with args {args} and kwargs {kwargs} is already running. Skipping."
                )
                return None

        return wrapper

    return decorator


@shared_task
@task_lock(timeout=60 * 30)  # 30 minutes lock to avoid concurrent runs
def refresh_proxy_list(max_proxies: int = 20, test_url: str = "https://www.google.com"):
    """
    Periodically refresh and validate the proxy list.
    This task should be scheduled to run at regular intervals.

    Args:
        max_proxies: Maximum number of proxies to validate and store
        test_url: URL to test the proxies against

    Returns:
        Number of working proxies found
    """
    logger.info("Starting proxy list refresh task")

    # First, clear the existing proxy cache to fetch fresh proxies
    url_requests.clear_proxy_cache()

    # Get and validate proxies
    working_proxies = url_requests.get_validated_proxies(
        max_proxies=max_proxies, test_url=test_url
    )

    # Update the proxy list in the url_requests module
    url_requests.update_proxy_list(working_proxies)

    logger.info(
        f"Proxy list refresh completed. Found {len(working_proxies)} working proxies"
    )
    return len(working_proxies)


@shared_task
@task_lock()
def enrich_from_captured_html(noticia_id):
    """
    Extract entities and metadata directly from captured HTML using LLM.
    Single-step enrichment that replaces the old 2-phase approach.

    Flow:
    1. Get Noticia with captured_html
    2. Extract entities, metadata, and fix missing title/image/desc in one call
    3. Save entities and update metadata if needed

    Args:
        noticia_id: ID of the Noticia to enrich
    """
    try:
        noticia = Noticia.objects.get(id=noticia_id)

        if not noticia.captured_html:
            logger.warning(f"No captured HTML for noticia {noticia_id}")
            return None

        # Check if already processed
        if noticia.entidades.exists():
            logger.info(f"Noticia {noticia_id} already has entities, skipping")
            return noticia_id

        logger.info(
            f"Extracting entities and metadata from HTML for noticia {noticia_id}"
        )

        # Extract everything in one LLM call
        articulo = parse.parse_noticia_from_html(noticia.captured_html)

        if not articulo:
            logger.error(f"Failed to parse HTML for noticia {noticia_id}")
            return None

        # Update metadata if LLM found better values
        updated = False
        if articulo.titulo and (
            not noticia.meta_titulo or len(noticia.meta_titulo) < 10
        ):
            noticia.meta_titulo = articulo.titulo
            updated = True
            logger.info(f"Updated title for noticia {noticia_id}: {articulo.titulo}")

        if articulo.imagen and not noticia.meta_imagen:
            noticia.meta_imagen = articulo.imagen
            updated = True
            logger.info(f"Updated image for noticia {noticia_id}: {articulo.imagen}")

        if articulo.descripcion and not noticia.meta_descripcion:
            noticia.meta_descripcion = articulo.descripcion
            updated = True
            logger.info(f"Updated description for noticia {noticia_id}")

        if updated:
            noticia.save()

        # Save entities if found
        if articulo.entidades:
            for entidad_nombrada in articulo.entidades:
                logger.info(
                    f"Found entity: {entidad_nombrada.nombre} "
                    f"({entidad_nombrada.tipo}, "
                    f"{entidad_nombrada.sentimiento})"
                )

                entidad, _ = Entidad.objects.get_or_create(
                    nombre=entidad_nombrada.nombre, tipo=entidad_nombrada.tipo
                )

                NoticiaEntidad.objects.get_or_create(
                    noticia=noticia,
                    entidad=entidad,
                    defaults={"sentimiento": entidad_nombrada.sentimiento},
                )

            logger.info(
                f"Saved {len(articulo.entidades)} entities for noticia {noticia_id}"
            )
        else:
            logger.info(f"No entities found in noticia {noticia_id}")

        return noticia_id

    except Noticia.DoesNotExist:
        logger.error(f"Noticia {noticia_id} does not exist")
        return None
    except Exception as e:
        logger.exception(
            f"Unexpected error in enrich_from_captured_html for "
            f"noticia {noticia_id}: {e}"
        )
        return None


@shared_task
def check_and_trigger_clustering():
    """
    Check if clustering should be triggered based on vote count.

    Triggers clustering if:
    - At least 10 new votes since last successful run
    - Last run was more than 1 hour ago (to avoid too frequent runs)

    Returns:
        dict: Result of clustering or None if skipped
    """
    logger.info("Checking if clustering should be triggered")

    # Get last successful run
    last_run = (
        VoterClusterRun.objects.filter(status="completed")
        .order_by("-completed_at")
        .first()
    )

    if last_run:
        # Count votes since last run
        votes_since_last = Voto.objects.filter(
            fecha_voto__gt=last_run.completed_at
        ).count()

        time_since_last = timezone.now() - last_run.completed_at
        hours_since_last = time_since_last.total_seconds() / 3600

        logger.info(
            f"Last run: {last_run.completed_at}, "
            f"votes since: {votes_since_last}, "
            f"hours since: {hours_since_last:.1f}"
        )

        # Don't trigger if less than 1 hour ago
        # if hours_since_last < 1:
        #     logger.info("Skipping: last run was less than 1 hour ago")
        #     return None

        # Don't trigger if less than 10 new votes
        if votes_since_last < 2:
            logger.info(f"Skipping: only {votes_since_last} votes since last run")
            return None
    else:
        # No previous run, check if we have enough votes
        total_votes = Voto.objects.count()
        if total_votes < 150:  # 50 voters * 3 votes minimum
            logger.info(f"Skipping: only {total_votes} total votes (need ~150 minimum)")
            return None

    logger.info("Triggering clustering")
    return update_voter_clusters.delay()


@shared_task
@task_lock(timeout=60 * 30)  # 30 min lock
def update_voter_clusters(time_window_days=30, min_voters=10, min_votes_per_voter=3):
    """
    Compute voter clusters based on voting patterns (Polis-style).

    This implements the full clustering pipeline:
    1. Build sparse vote matrix
    2. Compute sparsity-aware PCA (2D projection)
    3. Run k-means clustering (base clusters)
    4. Run hierarchical grouping (auto-select k)
    5. Create subgroups within groups
    6. Compute consensus metrics
    7. Save results to database

    Args:
        time_window_days: Only include votes from last N days
        min_voters: Minimum voters required to run clustering
        min_votes_per_voter: Minimum votes to include a voter

    Returns:
        dict: {
            'cluster_run_id': int,
            'n_voters': int,
            'n_clusters': int,
            'computation_time': float
        }
    """
    from core.clustering import (
        build_vote_matrix,
        compute_sparsity_aware_pca,
        cluster_voters,
        group_clusters,
        create_subgroups,
        compute_cluster_voting_aggregation,
        compute_cluster_consensus,
        compute_distance_to_centroid,
        compute_silhouette_score,
    )

    start_time = time.time()
    logger.info(
        f"Starting voter clustering: "
        f"time_window={time_window_days}d, "
        f"min_voters={min_voters}"
    )

    # Create run record
    run = VoterClusterRun.objects.create(
        status="running",
        parameters={
            "time_window_days": time_window_days,
            "min_voters": min_voters,
            "min_votes_per_voter": min_votes_per_voter,
        },
    )

    try:
        # Step 1: Build vote matrix
        logger.info("Step 1: Building vote matrix")
        vote_matrix, voter_ids_list, noticia_ids_list = build_vote_matrix(
            time_window_days=time_window_days, min_votes_per_voter=min_votes_per_voter
        )

        n_voters = len(voter_ids_list)
        n_noticias = len(noticia_ids_list)

        if n_voters < min_voters:
            error_msg = f"Insufficient voters: {n_voters} < {min_voters}"
            logger.warning(error_msg)
            run.status = "failed"
            run.error_message = error_msg
            run.save()
            return {"error": error_msg}

        # Step 2: PCA (biplot - voters and noticias)
        logger.info("Step 2: Computing SVD biplot")
        pca_result = compute_sparsity_aware_pca(vote_matrix, n_components=2)
        projections = pca_result['voter_projections']
        noticia_projections = pca_result['noticia_projections']
        variance_explained = pca_result['variance_explained']
        vote_counts = pca_result['voter_vote_counts']
        noticia_vote_counts = pca_result['noticia_vote_counts']

        # Step 3: Base clustering
        logger.info("Step 3: Running base k-means clustering")
        k_base = min(10, max(10, n_voters // 10))
        base_labels, base_centroids, base_inertia = cluster_voters(
            projections, vote_counts, k=k_base
        )

        # Step 4: Group clustering
        logger.info("Step 4: Running hierarchical group clustering")
        group_labels, best_k_groups, silhouette_scores = group_clusters(
            base_labels, projections, k_range=(2, 5)
        )

        # Step 5: Subgroups
        logger.info("Step 5: Creating subgroups")
        subgroup_labels_dict = create_subgroups(group_labels, projections, k_subgroup=3)

        # Step 6: Save to database
        logger.info("Step 6: Saving results to database")

        # 6.1: Save projections
        projection_objs = [
            VoterProjection(
                run=run,
                voter_type=voter_ids_list[i][0],
                voter_id=voter_ids_list[i][1],
                projection_x=float(projections[i, 0]),
                projection_y=float(projections[i, 1]),
                n_votes_cast=int(vote_counts[i]),
            )
            for i in range(n_voters)
        ]
        VoterProjection.objects.bulk_create(projection_objs)
        logger.info(f"Saved {len(projection_objs)} voter projections")

        # 6.1b: Save noticia projections (biplot)
        noticia_projection_objs = [
            NoticiaProjection(
                run=run,
                noticia_id=noticia_ids_list[j],
                projection_x=float(noticia_projections[j, 0]),
                projection_y=float(noticia_projections[j, 1]),
                n_votes=int(noticia_vote_counts[j]),
            )
            for j in range(n_noticias)
        ]
        NoticiaProjection.objects.bulk_create(noticia_projection_objs)
        logger.info(f"Saved {len(noticia_projection_objs)} noticia projections")

        # 6.2: Save base clusters
        base_cluster_objs = []
        for cluster_id in range(k_base):
            cluster_mask = base_labels == cluster_id
            size = int(np.sum(cluster_mask))

            if size == 0:
                continue

            base_cluster_objs.append(
                VoterCluster(
                    run=run,
                    cluster_id=cluster_id,
                    cluster_type="base",
                    size=size,
                    centroid_x=float(base_centroids[cluster_id, 0]),
                    centroid_y=float(base_centroids[cluster_id, 1]),
                )
            )

        VoterCluster.objects.bulk_create(base_cluster_objs)
        logger.info(f"Saved {len(base_cluster_objs)} base clusters")

        # 6.3: Save base cluster memberships
        base_cluster_obj_map = {c.cluster_id: c for c in base_cluster_objs}
        membership_objs = []

        for i in range(n_voters):
            cluster_id = int(base_labels[i])
            if cluster_id not in base_cluster_obj_map:
                continue

            cluster_obj = base_cluster_obj_map[cluster_id]
            distance = compute_distance_to_centroid(
                projections[i], base_centroids[cluster_id]
            )

            membership_objs.append(
                VoterClusterMembership(
                    cluster=cluster_obj,
                    voter_type=voter_ids_list[i][0],
                    voter_id=voter_ids_list[i][1],
                    distance_to_centroid=float(distance),
                )
            )

        VoterClusterMembership.objects.bulk_create(membership_objs)
        logger.info(f"Saved {len(membership_objs)} memberships")

        # 6.4: Compute and save voting patterns for base clusters
        logger.info("Computing cluster voting patterns")
        voting_pattern_objs = []

        for cluster_id in range(k_base):
            cluster_mask = base_labels == cluster_id
            cluster_members = np.where(cluster_mask)[0]

            if len(cluster_members) == 0:
                continue

            cluster_obj = base_cluster_obj_map.get(cluster_id)
            if not cluster_obj:
                continue

            # Aggregate votes
            aggregation = compute_cluster_voting_aggregation(
                cluster_members, voter_ids_list, vote_matrix, noticia_ids_list
            )

            # Compute consensus
            cluster_votes = {nid: agg for nid, agg in aggregation.items()}
            consensus = compute_cluster_consensus(cluster_votes)

            # Update cluster consensus score
            cluster_obj.consensus_score = float(consensus)
            cluster_obj.save()

            # Save voting patterns per noticia
            for noticia_id, vote_agg in aggregation.items():
                # Determine majority opinion
                max_opinion = max(
                    vote_agg.items(), key=lambda x: x[1] if x[0] != "total" else 0
                )[0]

                # Calculate consensus for this specific noticia
                total = vote_agg["total"]
                noticia_consensus = vote_agg[max_opinion] / total if total > 0 else 0

                voting_pattern_objs.append(
                    ClusterVotingPattern(
                        cluster=cluster_obj,
                        noticia_id=noticia_id,
                        count_buena=vote_agg.get("buena", 0),
                        count_mala=vote_agg.get("mala", 0),
                        count_neutral=vote_agg.get("neutral", 0),
                        consensus_score=float(noticia_consensus),
                        majority_opinion=max_opinion,
                    )
                )

        ClusterVotingPattern.objects.bulk_create(voting_pattern_objs)
        logger.info(f"Saved {len(voting_pattern_objs)} voting patterns")

        # 6.5: Save group clusters
        group_cluster_objs = []
        for group_id in np.unique(group_labels):
            group_mask = group_labels == group_id
            group_projections = projections[group_mask]
            size = int(np.sum(group_mask))

            if size == 0:
                continue

            centroid = group_projections.mean(axis=0)

            group_cluster_objs.append(
                VoterCluster(
                    run=run,
                    cluster_id=int(group_id),
                    cluster_type="group",
                    size=size,
                    centroid_x=float(centroid[0]),
                    centroid_y=float(centroid[1]),
                )
            )

        VoterCluster.objects.bulk_create(group_cluster_objs)
        logger.info(f"Saved {len(group_cluster_objs)} group clusters")

        # 6.6: Save group memberships and voting patterns
        group_cluster_obj_map = {
            c.cluster_id: c for c in group_cluster_objs
        }

        group_membership_objs = []
        for i in range(n_voters):
            group_id = int(group_labels[i])
            if group_id not in group_cluster_obj_map:
                continue

            cluster_obj = group_cluster_obj_map[group_id]
            group_centroid = projections[group_labels == group_id].mean(axis=0)
            distance = compute_distance_to_centroid(
                projections[i], group_centroid
            )

            group_membership_objs.append(
                VoterClusterMembership(
                    cluster=cluster_obj,
                    voter_type=voter_ids_list[i][0],
                    voter_id=voter_ids_list[i][1],
                    distance_to_centroid=float(distance),
                )
            )

        VoterClusterMembership.objects.bulk_create(group_membership_objs)
        logger.info(f"Saved {len(group_membership_objs)} group memberships")

        # 6.7: Compute voting patterns for group clusters
        group_voting_pattern_objs = []
        for group_id in np.unique(group_labels):
            if group_id not in group_cluster_obj_map:
                continue

            cluster_obj = group_cluster_obj_map[group_id]
            cluster_mask = group_labels == group_id
            cluster_members = np.where(cluster_mask)[0]

            if len(cluster_members) == 0:
                continue

            vote_agg = compute_cluster_voting_aggregation(
                cluster_members, voter_ids_list, vote_matrix, noticia_ids_list
            )

            for noticia_id, agg in vote_agg.items():
                total = agg["buena"] + agg["mala"] + agg["neutral"]
                if total == 0:
                    continue

                max_opinion = max(
                    ["buena", "mala", "neutral"],
                    key=lambda x: agg[x]
                )
                noticia_consensus = agg[max_opinion] / total

                group_voting_pattern_objs.append(
                    ClusterVotingPattern(
                        cluster=cluster_obj,
                        noticia_id=noticia_id,
                        count_buena=agg["buena"],
                        count_mala=agg["mala"],
                        count_neutral=agg.get("neutral", 0),
                        consensus_score=float(noticia_consensus),
                        majority_opinion=max_opinion,
                    )
                )

        ClusterVotingPattern.objects.bulk_create(group_voting_pattern_objs)
        logger.info(f"Saved {len(group_voting_pattern_objs)} group voting patterns")

        # Step 7: Generate LLM descriptions for group clusters
        logger.info("Step 7: Generating LLM descriptions for group clusters")
        from core.clustering.metrics import compute_cluster_entities

        for group_id, cluster_obj in group_cluster_obj_map.items():
            try:
                # 7.1: Get top noticias with highest consensus
                top_patterns = ClusterVotingPattern.objects.filter(
                    cluster=cluster_obj
                ).order_by('-consensus_score')[:10]

                top_noticias = []
                for pattern in top_patterns:
                    noticia = pattern.noticia
                    top_noticias.append({
                        'titulo': noticia.mostrar_titulo or noticia.enlace,
                        'resumen': noticia.meta_descripcion or '',
                        'majority_opinion': pattern.majority_opinion,
                        'consensus': pattern.consensus_score or 0.5,
                    })

                # 7.2: Get distinctive entities
                entities_pos, entities_neg = compute_cluster_entities(
                    cluster_obj, top_n=5
                )

                # 7.3: Generate description with LLM
                description = parse.generate_cluster_description(
                    top_noticias=top_noticias,
                    entities_positive=entities_pos,
                    entities_negative=entities_neg,
                    cluster_size=cluster_obj.size,
                    consensus_score=cluster_obj.consensus_score or 0.5,
                )

                # 7.4: Save to cluster
                if description:
                    cluster_obj.llm_name = description.nombre[:100]
                    cluster_obj.llm_description = description.descripcion
                    cluster_obj.top_entities_positive = entities_pos
                    cluster_obj.top_entities_negative = entities_neg
                    cluster_obj.description_generated_at = timezone.now()
                    cluster_obj.save()
                    logger.info(
                        f"Generated description for group {group_id}: "
                        f"{description.nombre}"
                    )
                else:
                    # Still save entities even if LLM fails
                    cluster_obj.top_entities_positive = entities_pos
                    cluster_obj.top_entities_negative = entities_neg
                    cluster_obj.save()
                    logger.warning(
                        f"LLM description failed for group {group_id}, "
                        f"saved entities only"
                    )

            except Exception as e:
                logger.error(
                    f"Error generating description for group {group_id}: {e}"
                )
                continue

        # 6.8: Compute overall silhouette score
        silhouette = compute_silhouette_score(projections, base_labels)

        # Update run metadata
        run.status = "completed"
        run.completed_at = timezone.now()
        run.n_voters = n_voters
        run.n_noticias = n_noticias
        run.n_clusters = len(base_cluster_objs)
        run.computation_time = time.time() - start_time
        run.parameters.update(
            {
                "variance_explained": variance_explained.tolist(),
                "k_base": k_base,
                "k_groups": best_k_groups,
                "silhouette_score": float(silhouette),
                "silhouette_scores_by_k": {
                    str(k): float(s) for k, s in silhouette_scores.items()
                },
            }
        )
        run.save()

        logger.info(
            f"Clustering complete: {n_voters} voters, "
            f"{run.n_clusters} clusters, "
            f"{run.computation_time:.2f}s, "
            f"silhouette={silhouette:.3f}"
        )

        return {
            "cluster_run_id": run.id,
            "n_voters": run.n_voters,
            "n_clusters": run.n_clusters,
            "computation_time": run.computation_time,
            "silhouette_score": float(silhouette),
        }

    except Exception as e:
        logger.exception(f"Error in update_voter_clusters: {e}")
        run.status = "failed"
        run.error_message = str(e)
        run.computation_time = time.time() - start_time
        run.save()
        raise


@shared_task
@task_lock(timeout=60 * 30)  # 30 min lock
def send_reengagement_emails(days_inactive=7, max_emails=500, notify_staff=True):
    """
    Send a playful re-engagement email to users who have been inactive.

    Inactive means:
    - last_login is older than days_inactive (or null)
    - last vote is older than days_inactive (or null)
    """
    now = timezone.now()
    threshold = now - timezone.timedelta(days=days_inactive)

    last_vote_subquery = (
        Voto.objects.filter(usuario=OuterRef("pk"))
        .values("usuario")
        .annotate(last_vote=Max("fecha_voto"))
        .values("last_vote")[:1]
    )

    User = get_user_model()
    inactive_users = (
        User.objects.filter(is_active=True)
        .exclude(email="")
        .annotate(last_vote=Subquery(last_vote_subquery))
        .filter(
            Q(last_login__isnull=True) | Q(last_login__lt=threshold),
            Q(last_vote__isnull=True) | Q(last_vote__lt=threshold),
        )
        .order_by("id")[:max_emails]
    )

    if not inactive_users.exists():
        logger.info("No inactive users found for reengagement email task")
        return {"sent": 0, "skipped": 0, "staff_notified": False}

    latest_run = (
        VoterClusterRun.objects.filter(status="completed")
        .order_by("-completed_at")
        .first()
    )
    bubble_names = []
    if latest_run:
        group_clusters = (
            VoterCluster.objects.filter(run=latest_run, cluster_type="group")
            .order_by("-size")
        )
        for cluster in group_clusters:
            bubble_names.append(cluster.llm_name or f"Grupo {cluster.cluster_id}")

    if bubble_names:
        bubbles_line = ", ".join(bubble_names)
    else:
        bubbles_line = "todavia no tenemos burbujas publicadas"

    site_url = getattr(settings, "SITE_URL", "https://memoria.uy")
    connection = get_connection()

    sent_count = 0
    skipped_count = 0
    sent_recipients = []

    for user in inactive_users:
        pending_count = (
            Noticia.objects.exclude(votos__usuario=user).count()
        )
        if pending_count == 0:
            skipped_count += 1
            continue

        display_name = user.get_full_name().strip() or user.email

        user_cluster_name = None
        if latest_run:
            membership = (
                VoterClusterMembership.objects.filter(
                    cluster__run=latest_run,
                    cluster__cluster_type="group",
                    voter_type="user",
                    voter_id=str(user.id),
                )
                .select_related("cluster")
                .first()
            )
            if membership:
                user_cluster_name = (
                    membership.cluster.llm_name
                    or f"Grupo {membership.cluster.cluster_id}"
                )

        subject = "Tenes noticias para votar en memoria.uy"
        lines = [
            f"Hola {display_name},",
            "",
            f"Hace {days_inactive} dias que no te vemos por memoria.uy.",
            f"Tenes {pending_count} noticias para votar.",
            "",
            f"Las burbujas actuales son: {bubbles_line}.",
        ]
        if user_cluster_name:
            lines.append(f"Tu burbuja actual es: {user_cluster_name}.")
        lines.extend(
            [
                "En cual estas?",
                "",
                f"Entrar a votar: {site_url}",
                "",
                "Gracias!",
            ]
        )

        try:
            send_mail(
                subject=subject,
                message="\n".join(lines),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                connection=connection,
            )
            sent_count += 1
            sent_recipients.append(user.email)
        except Exception as exc:
            logger.error(
                f"Failed to send reengagement email to {user.email}: {exc}"
            )
            skipped_count += 1

    staff_notified = False
    if notify_staff:
        staff_emails = list(
            User.objects.filter(is_active=True, is_staff=True)
            .exclude(email="")
            .values_list("email", flat=True)
        )
        if staff_emails:
            staff_subject = "Resumen de emails de reenganche enviados"
            staff_lines = [
                f"Se enviaron {sent_count} emails de reenganche.",
                f"Se omitieron {skipped_count} usuarios.",
                "",
                "Destinatarios:",
            ]
            if sent_recipients:
                staff_lines.extend(sent_recipients)
            else:
                staff_lines.append("Ninguno.")

            try:
                send_mail(
                    subject=staff_subject,
                    message="\n".join(staff_lines),
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=staff_emails,
                    connection=connection,
                )
                staff_notified = True
            except Exception as exc:
                logger.error(
                    f"Failed to send staff summary email: {exc}"
                )

    logger.info(
        "Reengagement email task finished. "
        f"Sent={sent_count}, skipped={skipped_count}"
    )
    return {
        "sent": sent_count,
        "skipped": skipped_count,
        "staff_notified": staff_notified,
    }
