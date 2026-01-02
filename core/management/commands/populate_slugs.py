# populate_slugs.py

from django.core.management.base import BaseCommand
from django.utils.text import slugify
from core.models import Noticia


class Command(BaseCommand):
    help = "Generate slugs for all noticias that don't have one"

    def handle(self, *args, **options):
        noticias_without_slug = Noticia.objects.filter(slug__isnull=True)
        count = noticias_without_slug.count()

        if count == 0:
            self.stdout.write(
                self.style.SUCCESS("All noticias already have slugs")
            )
            return

        self.stdout.write(
            f"Found {count} noticias without slugs. Generating..."
        )

        used_slugs = set(
            Noticia.objects.filter(slug__isnull=False).values_list(
                "slug", flat=True
            )
        )

        for noticia in noticias_without_slug:
            base_slug = slugify(
                noticia.meta_titulo or f"noticia-{noticia.pk}"
            )
            slug = base_slug
            counter = 1

            while slug in used_slugs:
                slug = f"{base_slug}-{counter}"
                counter += 1

            noticia.slug = slug
            used_slugs.add(slug)
            noticia.save(update_fields=["slug"])

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully generated slugs for {count} noticias"
            )
        )
