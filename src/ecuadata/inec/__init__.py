"""Instituto Nacional de Estadística y Censos (INEC).

>>> import ecuadata as ec
>>> ipc = ec.inec.ipc(start="2020-01")                       # índice de precios al consumidor
>>> inflacion = ec.inec.ipc(measure="annual_change")["general"]  # inflación anual, %
"""

from ecuadata.inec._ipc import ipc

__all__ = ["ipc"]
