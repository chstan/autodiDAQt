from typing import Any, Dict

__all__ = (
    "AttrDict",
    "deep_update",
    "map_tree_leaves",
    "map_treelike_nodes",
)


class AttrDict(dict):
    def nested_get(self, key_seq, default, safe_early_terminate=False):
        key_seq = list(key_seq)
        first, rst = key_seq[0], key_seq[1:]

        try:
            item = getattr(self, first)
        except (AttributeError, KeyError) as e:
            if safe_early_terminate or not rst:
                return default

            raise e

        if not rst:
            return item

        if not isinstance(item, AttrDict) and safe_early_terminate:
            return default

        return item.nested_get(rst, default, safe_early_terminate=safe_early_terminate)

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


def deep_update(src: Dict[Any, Any], dest: Dict[Any, Any]) -> Dict[Any, Any]:
    """
    Similar to ``dict.update``, except that we also ``deep_update``
    any dictionaries we find inside of the destination. This is useful for
    nested default settings, for instance.

    Args:
        src: The dictionary which should be used for updates in ``dest``
        dest: The target which should be updated in place. This instance is also returned.

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
    return dest


def map_treelike_nodes(tree, transform):
    if not isinstance(transform, dict):
        transform = {
            dict: transform,
            list: lambda x: x,
        }

    if isinstance(tree, dict):
        for k, v in tree.items():
            if isinstance(v, (dict, list)):
                tree[k] = map_treelike_nodes(v, transform)
    if isinstance(tree, list):
        for i, item in enumerate(tree):
            if isinstance(item, (dict, list)):
                tree[i] = map_treelike_nodes(item, transform)

    return transform[type(tree)](tree)


def map_tree_leaves(tree: dict, transform):
    for k, v in tree.items():
        if isinstance(v, dict):
            map_tree_leaves(v, transform)
        else:
            tree[k] = transform(v)

    return tree
