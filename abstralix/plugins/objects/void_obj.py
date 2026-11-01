from abstralix.plugins.base.base_object import BaseObjectPlugin


class VoidObjectPlugin(BaseObjectPlugin):
    name = "void"
    allowed_parents = ["file"]
    can_contain = []
    is_filesystem_node = False
