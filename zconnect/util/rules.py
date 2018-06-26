import rules
from rules.permissions import permissions


def override_perm(name, pred):
    """If a permission exists in the current default permission set, delete it
    and replace it with the new one

    This operates on the global default permissions

    Args:
        name (str): permission name (eg, zconnect.change_device)
        pred (function): function to call to check permission on object
    """
    try:
        rules.add_perm(name, pred)
    except KeyError:
        rules.remove_perm(name)
        rules.add_perm(name, pred)


def orify_perm(name, pred, first=False):
    """If a permission exists, orify it with the new one

    By default the existing one will be run first, to override this pass
    first=True

    Args:
        name (str): permission name (eg, zconnect.change_device)
        pred (function): function to call to check permission on object
        first (bool, optional): Whether to run the given predicate before any
            existing ones
    """
    try:
        rules.add_perm(name, pred)
    except KeyError:
        existing = permissions[name]
        rules.remove_perm(name)

        if first:
            new_pred = pred | existing
        else:
            new_pred = existing | pred

        rules.add_perm(name, new_pred)
