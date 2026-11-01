from abstralix.plugins.base.base_object import BaseObjectPlugin


class FolderObjectPlugin(BaseObjectPlugin):
    name = "folder"
    allowed_parents = ["root", "folder"]
    can_contain = ["folder", "file"]
    is_filesystem_node = True
