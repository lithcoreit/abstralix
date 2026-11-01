from abstralix.plugins.base.base_object import BaseObjectPlugin


class FileObjectPlugin(BaseObjectPlugin):
    name = "file"
    allowed_parents = ["folder"]
    can_contain = ["void"]
    is_filesystem_node = True
