"""Excepciones que lanza ecuadata."""


class EcuadataError(Exception):
    """Clase base de todos los errores de ecuadata."""


class SourceUnavailableError(EcuadataError):
    """No se pudo contactar a la institución, o el archivo solicitado no existe."""


class ParseError(EcuadataError):
    """Un archivo descargado no tiene el formato que espera el parser.

    Casi siempre significa que la institución cambió el formato del archivo. Por favor abra
    un issue en el repositorio.
    """


class OfflineError(EcuadataError):
    """El modo sin conexión está activo y los datos solicitados no están en el caché."""
