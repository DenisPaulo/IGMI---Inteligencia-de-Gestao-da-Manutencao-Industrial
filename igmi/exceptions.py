class IGMIError(Exception):
    """Falha controlada da camada IGMI."""

class WarehouseAusente(IGMIError):
    """Warehouse ainda não gerado."""

class QualidadeBloqueada(IGMIError):
    """Os checks bloqueantes não passaram."""

class EscopoInvalido(IGMIError):
    """A linha solicitada não está cadastrada."""
