class StringlyError(Exception): pass
class SerializationError(StringlyError):
    def __init__(self, ctx, msg):
        if ctx:
            msg = f'in {ctx}: {msg}'
        super().__init__(msg)
class ImportFunctionError(StringlyError): pass
