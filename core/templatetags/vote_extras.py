from django import template

register = template.Library()


@register.filter
def vote_count(votos, opinion):
    """
    Given a queryset of votes and an opinion string, returns the count.
    Usage: {{ noticia.votos|vote_count:"buena" }}
    """
    return votos.filter(opinion=opinion).count()
