__all__ = ('AttrDict',)

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

