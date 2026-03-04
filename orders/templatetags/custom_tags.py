from django import template

register = template.Library()


@register.filter
def getattr(obj, attr):
    return getattr(obj, attr)



@register.filter
def hasattr(obj, attr):
    return hasattr(obj, attr)