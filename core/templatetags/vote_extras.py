from django import template

register = template.Library()


@register.filter
def vote_count(votos, opinion):
    """
    Given a queryset of votes and an opinion string, returns the count.
    Usage: {{ noticia.votos|vote_count:"buena" }}
    """
    return votos.filter(opinion=opinion).count()


@register.filter
def get_item(dictionary, key):
    """
    Get item from dictionary by key.
    Usage: {{ mydict|get_item:mykey }}
    """
    if dictionary is None:
        return None
    return dictionary.get(key)


@register.filter
def mul(value, arg):
    """
    Multiply value by arg.
    Usage: {{ value|mul:100 }}
    """
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return 0


@register.filter
def div(value, arg):
    """
    Divide value by arg.
    Usage: {{ value|div:total }}
    """
    try:
        arg_float = float(arg)
        if arg_float == 0:
            return 0
        return int(float(value) / arg_float)
    except (ValueError, TypeError, ZeroDivisionError):
        return 0
