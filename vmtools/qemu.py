import os
import subprocess

'''
Module to help start qemu VMs from python, and manipulate resulting process,
provides an object-oriented interface to the qemu command line; where objects
normally given on the command line as for example -netdev are created as objects
which may have as a bonus some minimal runtime checking of parameters.

The impetus for this is complicated qemu command line arguments for running VMs
to be throughput tested.
'''

class QemuCommandLineObj:
    def cmdline(self):
        raise RuntimeError("QemuCommandLineObj not implemented")

class BasicParameters(QemuCommandLineObj):
    def __init__(self, name='', memory=512, bootorder='cd', cpu='host'):
        self.name = name
        self.memory=memory
        self.bootorder=bootorder
        self.cpu = cpu

    def cmdline(self):
        return ['-name', self.name,
                '-m', str(self.memory),
                '-boot', self.bootorder,
                '-cpu', self.cpu]

class Device(QemuCommandLineObj):
    def __init__(self, driver, id, **kwargs):
        self.driver = driver
        self.props = kwargs
        self.id = id

    def cmdline(self):
        props_str = self.driver 
        if self.id:
            props_str += ',id=' + self.id

        for k, v in self.props.items():
            props_str += ',{}={}'.format(k, v)
        return ['-device', props_str]

class Drive(QemuCommandLineObj):
    def __init__(self, filename):
        self.filename = filename
    def cmdline(self):
        return ['-drive', 'file={}'.format(self.filename)]

def _build_cmdline(dashparam, *words, **values):
    li = [dashparam]
    paramstr = ','.join(words)
    for k,v in values.items():
        if k and v:
            paramstr += ',' + str(k) + '=' + str(v)
    li.append(paramstr)

    return li


class Numa(QemuCommandLineObj):
    def __init__(self, memdev, cpus=None):
        self.memdev = memdev
        self.cpus = cpus
    def cmdline(self):
        return _build_cmdline('-numa', 'node', 
                          memdev=self.memdev, 
                          cpus=self.cpus)

class NetworkPortNic(QemuCommandLineObj):
    '''
    Class representing a qemu network port.
    '''
    def __init__(self, model, mac=None):
        self.mac = mac
        self.model = model
    def cmdline(self):
        params = 'nic'
        if self.model:
            params += ',model=' + self.model
        if self.mac:
            params += ',macaddr=' + self.mac

        return ['-net', params]



class HugepageMemoryBack(QemuCommandLineObj):
    def __init__(self, id, size, path, share):
        self.size = size
        self.path = path
        self.share = 'on' if share else 'off'
        self.id = id
    def cmdline(self):
        params = 'memory-backend-file,id={},size={},mem-path={},share={}'.format(
                self.id,
                self.size,
                self.path,
                self.share)
        return ['-object', params]


class Chardev(QemuCommandLineObj):
    def __init__(self, id, backend, **kwargs):
        self.options = kwargs
        self.id = id
        self.backend = backend

    def cmdline(self):
        opts =  self.backend + ',id=' + self.id
        for k, v in self.options.items():
            opts += ',{}={}'.format(k, v)

        return ['-chardev', opts]

class Bridge(QemuCommandLineObj):
    def __init__(self, bridge=None, helper=None):
        self.bridge = bridge
        self.helper = helper
    def cmdline(self):
        opts = 'bridge'
        if self.bridge:
            opts += ',br=' + self.bridge
        if self.helper:
            opts += ',helper=' + self.helper

        return ['-net', opts]

class VhostUserNetdev(QemuCommandLineObj):
    '''
    A class representing a Vhostuser socket.
    '''
    def __init__(self, id, chardev, device):
        assert isinstance(chardev, Chardev)
        assert isinstance(device, Device)
        self.chardev = chardev
        self.device = device
        self.id = id

    def cmdline(self):
        args = []
        args.extend(self.chardev.cmdline())
        args.extend(self.device.cmdline())
        netdev = [ '-netdev',
                   'type=vhost-user,id={},chardev={},vhostforce'.format(
                       self.id,
                       self.chardev.id)]
        args.extend(netdev)
        return args



class QemuError(Exception):
    pass

class Qemu:
    '''
    A class wrapping a qemu command line VM instantiation, and potentially later
    allowing users to mount the VM image locally, chroot in and update, install
    packages, &c.

    '''
    executables = ['/usr/bin/kvm', '/bin/kvm']
    def __init__(self, basic_params, *extra_objects):
        '''
        basic_params -- a BasicParameters object with basic parameters.
        *extra_objects -- extra QemuCommandLine objects which will have their
            cmdline methods called, which are expected to be lists, which will
            be added to the command-line invocation.
        '''
        executable = None
        for _executable in Qemu.executables:
            if os.path.exists(_executable):
                executable = _executable

        if executable is None:
            raise QemuError("No kvm executable. is qemu installed?")

        self.cmdline = [executable]
        self.cmdline.extend(basic_params.cmdline())
        for e_o in extra_objects:
            self.cmdline.extend(e_o.cmdline())

    def launch(self):
        '''
        launch the VM. Returns a subprocess.Popen object.
        '''
        proc = None
        try:
            proc =  subprocess.Popen(self.cmdline,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE)
        except Exception as e:
            raise QemuError("error for: {}: {}".format(
                self.cmdline, e))

        return proc

