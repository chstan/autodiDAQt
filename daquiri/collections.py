__all__ = ('AttrDict',)

class AttrDict(dict):
    def __getitem__(self, k):
        """
        Rewraps the item in an AttrDict if possible to allow "." chaining
        :param
        :return:
        """
        item = super().__getitem__(k)
        if isinstance(item, dict):
            return AttrDict(item)

        return item

    __getattr__ = __getitem__
    __setattr__ = dict.__setitem__

def map_treelike_nodes(tree, transform):
    if not isinstance(transform, dict):
        transform = {
            dict: transform,
            list: lambda x: x,
        }

    if isinstance(tree, dict):
        for k, v in tree.items():
            if isinstance(v, (dict, list,)):
                tree[k] = map_treelike_nodes(v, transform)
    if isinstance(tree, list):
        for i, item in enumerate(tree):
            if isinstance(item, (dict, list,)):
                tree[i] = map_treelike_nodes(item, transform)

    return transform[type(tree)](tree)

def map_tree_leaves(tree: dict, transform):
    for k, v in tree.items():
        if isinstance(v, dict):
            map_tree_leaves(v, transform)
        else:
            tree[k] = transform(v)

    return tree

