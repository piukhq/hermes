import threading
import base64
from typing import Optional, NamedTuple, List
import paramiko
import paramiko.auth_handler


class HostKey(NamedTuple):
    host: str
    keytype: str
    key: str

    @property
    def parsed_key(self) -> paramiko.RSAKey:
        if self.keytype == "ssh-ed25519":
            return paramiko.Ed25519Key(data=base64.b64decode(self.key))
        elif self.keytype == "ssh-rsa":
            return paramiko.RSAKey(data=base64.b64decode(self.key))
        else:
            pass


def password_and_key_sftp_client(host, port, host_keys, username, password, pkey):
    host_key_collection = paramiko.HostKeys()
    server_hostkey_name = "[{}]:{}".format(host, port) if port != 22 else host

    for host_key in host_keys:
        host_key_collection.add(host_key.host, host_key.keytype, host_key.parsed_key)

    transport = paramiko.Transport((host, port))
    transport.start_client(event=None, timeout=15)
    remote_key = transport.get_remote_server_key()

    if not host_key_collection.check(server_hostkey_name, remote_key):
        raise paramiko.BadHostKeyException(server_hostkey_name, remote_key, host_keys[0].parsed_key)

    transport.auth_publickey(username, pkey, event=None)

    # Setup an auth handler
    pw_auth_event = threading.Event()
    pw_auth_handler = paramiko.auth_handler.AuthHandler(transport)
    transport.auth_handler = pw_auth_handler

    # Get transport lock so other threads cant sent stuff
    transport.lock.acquire()

    # Assemble auth event
    pw_auth_handler.auth_event = pw_auth_event
    pw_auth_handler.auth_method = 'password'
    pw_auth_handler.username = username
    pw_auth_handler.password = password

    # Sent auth message
    userauth_message = paramiko.message.Message()
    userauth_message.add_string('ssh-userauth')
    userauth_message.rewind()
    pw_auth_handler._parse_service_accept(userauth_message)
    transport.lock.release()
    pw_auth_handler.wait_for_response(pw_auth_event)

    if not transport.is_authenticated():
        raise ValueError("Failed to authenticate with multi-factor auth")
    return transport.open_sftp_client()


def get_sftp_client(
        host: str,
        port: int,
        username: str,
        host_keys: List[HostKey],
        password: Optional[str] = None,
        pkey: Optional[paramiko.RSAKey] = None) -> paramiko.SFTPClient:

    if (pkey and not password) or (password and not pkey):
        ssh_client = paramiko.SSHClient()
        for host_key in host_keys:
            ssh_client.get_host_keys().add(host_key.host, host_key.keytype, host_key.parsed_key)
        if pkey:
            ssh_client.connect(hostname=host, port=port, username=username, pkey=pkey)
        else:
            ssh_client.connect(hostname=host, port=port, username=username, password=password)
        return ssh_client.open_sftp()
    elif pkey and password:
        return password_and_key_sftp_client(host, port, host_keys, username, password, pkey)

    raise ValueError("password and or private key must be provided")
