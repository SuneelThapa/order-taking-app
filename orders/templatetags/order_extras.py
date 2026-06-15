from django import template

register = template.Library()


@register.filter
def get_item(dictionary, key):
    """
    Get a dict value by key in templates.
    Tries the key as-is first, then as string, then as int.
    Usage: {{ mydict|get_item:key }}
    """
    if not dictionary:
        return ""
    # Try original key, then string, then int conversion
    if key in dictionary:
        return dictionary[key]
    try:
        if str(key) in dictionary:
            return dictionary[str(key)]
        if int(key) in dictionary:
            return dictionary[int(key)]
    except (ValueError, TypeError):
        pass
    return ""