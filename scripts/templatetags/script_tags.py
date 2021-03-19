from django import template
from ..admin import DataScripts, SCRIPT_TITLES, SCRIPT_CLASSES

register = template.Library()


@register.tag
def script_list(parser, token):
    return ListScript()


class ListScript(template.Node):
    def render(self, context):
        lines = []
        for data_script in SCRIPT_CLASSES.keys():
            lines.append(f'<a href="scriptresult/run_script/{data_script.value}">find records for:'
                         f' {SCRIPT_TITLES[data_script]}</a>')
        return "<br/>".join(lines)


@register.tag
def script_id(parser, token):
    try:
        # split_contents() knows not to split quoted strings.
        tag_name, var = token.split_contents()
    except ValueError:
        raise(template.TemplateSyntaxError, f"{token.contents.split()[0]} tag requires a single argument")
    return IdOfScript(var)


class IdOfScript(template.Node):
    def __init__(self, var):
        self.script_name = var

    def render(self, context):
        return DataScripts.__getattr__(self.script_name).value


@register.tag
def script_title(parser, token):
    try:
        # split_contents() knows not to split quoted strings.
        tag_name, var = token.split_contents()
    except ValueError:
        raise(template.TemplateSyntaxError, f"{token.contents.split()[0]} tag requires a single argument")
    return TitleOfScript(var)


class TitleOfScript(template.Node):
    def __init__(self, var):
        self.script_name = var

    def render(self, context):
        return SCRIPT_TITLES[DataScripts.__getattr__(self.script_name)]
