from django import template

register = template.Library()


@register.filter
def vote_count(votos, opinion):
    """
    Given a queryset of votes and an opinion string, returns the count.
    Usage: ***REMOVED******REMOVED*** noticia.votos|vote_count:"buena" ***REMOVED******REMOVED***
    """
    return votos.filter(opinion=opinion).count()
