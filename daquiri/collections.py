from typing import Dict, Any

__all__ = ('AttrDict', 'map_tree_leaves', 'map_treelike_nodes',)


class AttrDict(dict):
    def __getitem__(self, k):
        """
        Rewraps the item in an AttrDict if possible to allow "." chaining

        Args:
            k (str): Key or item to find in the dictionary.

        Returns:
            Any: The value at the specified key, wrapped in an AttrDict if it was a dict.
        """
        item = super().__getitem__(k)
        if isinstance(item, dict):
            return AttrDict(item)

        return item

    __getattr__ = __getitem__
    __setattr__ = dict.__setitem__


def deep_update(src: Dict[Any, Any], dest: Dict[Any, Any]):
    """
    Similar to ``dict.update``, except that we also ``deep_update``
    any dictionaries we find inside of the destination. This is useful for
    nested default settings, for instance.

    Args:
        src:
        dest:

    Returns:
        The merged dictionaries.
    """

    for k, v in src.items():
        if isinstance(v, dict):
            if k not in dest:
                dest[k] = {}

            deep_update(v, dest[k])
        else:
            dest[k] = v


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

