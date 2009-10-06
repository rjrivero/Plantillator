#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent

try:
    from IPy import IP
except ImportError:
    # Tengo que asegurarme de que el modulo IPy es alcanzable.
    import sys
    import os
    path = __path__[0]
    path = os.path.sep.join((path, "..", "IPy"))
    sys.path.append(path)
    from IPy import IP


__all__ = []
