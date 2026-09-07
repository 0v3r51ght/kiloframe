class KiloFrameError(Exception):
    """Base error suitable for display to the user."""


class ConfigurationError(KiloFrameError):
    pass


class ModelUnavailable(KiloFrameError):
    pass


class RuntimeUnavailable(KiloFrameError):
    pass


class SecurityError(KiloFrameError):
    pass


class PermissionDenied(SecurityError):
    pass


class ToolError(KiloFrameError):
    pass

