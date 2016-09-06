import subprocess
import re
'''
Module to help with management of linux network interfaces.
It will provide a NetworkInterface object, which allows for simple manipulations
of network interfaces. 

>>> if = NetworkInterface('eth0')
>>> if.ip
'192.168.10.2'
>>> if.ip('192.168.10.3')
'192.168.10.3'
>>> if.mac()
'00:00:00:00:00:02'
>>> if.link()
True
>>> if.link(False)
>>> if.link()
False
>>> if.link(True)
>>> if.link
True

It will also allow for an easy way to make calls to
iproute2 the command, 
>>> networkinterfaces.ip('link', ['add', 'type', 'veth'])

or

>>> networkinterfaces.ip_link('add', 'type', 'veth')

'''

class NetworkInterfaceError(Exception):
    pass

class IPRoute2Error(Exception):
    pass

class NetworkInterface():
    def __init__(self, name):
        self.name = name

    def link(self, linkstate=None):
        pass

    def mac(self, mac=None):
        pass

    def ip(self, ip=None):
        pass

def ifnames():
    '''
    return a list of strings representing the interfaces on the system.
    '''
    lines = iplink()
    return map(lambda l: re.split(r'\s+', l)[1], lines)

IP_COMMAND='/sbin/ip'

def ip(command, 
   do, 
   family='inet', 
   oneline=False,
   remove_backslash=False,
   lines=True):
    '''
    Run an iproute2 command, returning it's output.
    Block until it returns.

    command -- string, command name such as 'address'
    do -- list of parameters, like ['add', 'type', 'veth']

    returns -- standard output, either a single string or a list.
    raises -- IPRoute2Error if returncode != 0, which will contain stderr.
    family -- string, 'inet', 'inet6', or 'link'.
    oneline -- boolean, pass the -o oneline parameter to ip.
    remove_backslash -- boolean, remove the backslashes caused by oneline.
    lines -- boolean, split output into lines.
    '''

    cmd = [IP_COMMAND, '-family', family]
    if oneline:
        cmd.append('-o')
    cmd.append(command)
    cmd.extend(do)
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    proc.wait()
    if proc.returncode != 0:
        stderr = proc.stderr.read()
        raise IPRoute2Error("command {} failed: stderr: {}\ncode\n{}".format(
            cmd,
            proc.stderr.read(),
            proc.returncode))

    out = proc.stdout.read()
    if remove_backslash:
        out = filter(lambda c: c != '\\', out)
    if lines:
        out = out.split('\n')[:-1]

    return out
                        

def iplink(*do, **kwargs):
    '''
    wrap ip link, simply an alias to the ip function.
    '''
    do = list(do)
    if 'dev' in kwargs:
        do.extend(('dev', kwargs['dev']))
    return ip('link', 
            do, 
            family='link', 
            oneline=True, 
            remove_backslash=True, 
            lines=True)

def ipaddr(family, *do, **kwargs):
    '''
    wrap ip addr
    '''
    do = list(do)
    if 'dev' in kwargs:
        do.extend(('dev', kwargs['dev']))
    return ip('address', 
            do, 
            family=str(family), 
            oneline=True, 
            remove_backslash=True,
            lines=True)
