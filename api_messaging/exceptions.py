
class MessageReject(Exception):
    pass


class MessageRequeue(Exception):
    pass


class MessageError(MessageReject):
    pass


class InvalidMessagePath(MessageReject):
    pass
