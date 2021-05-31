"""Module functions and classes for tagpack-tool"""

from tagpack._version import __version__


def get_version():
    return __version__


class TagPackFileError(Exception):
    """Class for TagPack file (structure) errors"""

    def __init__(self, message):
        super().__init__(message)


class ValidationError(Exception):
    """Class for schema validation errors"""

    def __init__(self, message):
        super().__init__("Schema Validation Error: " + message)


class StorageError(Exception):
    """Class for Cassandra-related errors"""

    def __init__(self, message, nested_exception=None):
        super().__init__("Cassandra Error: " + message)
        self.nested_exception = nested_exception

    def __str__(self):
        msg = super(StorageError, self).__str__()
        if self.nested_exception:
            msg = msg + '\nError Details: ' + str(self.nested_exception)
        return msg
