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
def _build_cmdline(dashparam, *words, **values):
    '''
    Build a common pattern for qemu command lines, which usually go something
    like:

    -param type,param=value,parm=value,param=value.

    *words = regular words like 'type' to be joined by commas.
    **values = key value pairs that will be joined by = and commas.
    '''
    li = [dashparam]
    paramstr = ','.join(words)
    kvs = []
    for k,v in values.items():
        if k and v:
            kvs.append(str(k) + '=' + str(v))
    if paramstr is not '':
        paramstr += ','

    paramstr += ','.join(kvs)

    li.append(paramstr)

    return li


class QemuCommandLineObj:
    def cmdline(self):
        raise RuntimeError("QemuCommandLineObj not implemented")

class BasicParameters(QemuCommandLineObj):
    '''
    Kind of a tack-on class, for commonly used initial command  line arguments
    for your vm.
    '''
    def __init__(self, name='', memory=512, bootorder='cd', cpu='host'):
        '''
        name -- string -name in the command line.
        memory -- integer or string, passed directly as -m argument.
        bootorder -- string, passed as -boot argument.
        cpu -- string, passed to -cpu.
        '''
        self.name = name
        self.memory=memory
        self.bootorder=bootorder
        self.cpu = cpu

    def cmdline(self):
        li = ['-name', self.name,
                '-m', str(self.memory),
                '-boot', self.bootorder]
        if self.cpu:
            li.extend(['-cpu', self.cpu])
        return li

class Device(QemuCommandLineObj):
    def __init__(self, driver, id, **kwargs):
        self.driver = driver
        self.props = kwargs
        self.id = id

    def cmdline(self):
        return _build_cmdline('-device',
                              self.driver,
                              id=self.id,
                              **self.props)

class Drive(QemuCommandLineObj):
    def __init__(self, filename):
        self.filename = filename
    def cmdline(self):
        return _build_cmdline('-drive',
                              file=self.filename)



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
        return _build_cmdline(
                '-net',
                'nic',
                model=self.model,
                macaddr=self.mac)


class HugepageMemoryBack(QemuCommandLineObj):
    '''
    Creates a hugepage memory backend,
    given a path and size.
    '''
    def __init__(self, id, size, path, share):
        self.size = size
        self.path = path
        self.share = 'on' if share else 'off'
        self.id = id

    def cmdline(self):
        return _build_cmdline('-object',
                   'memory-backend-file',
                   **{"id":self.id,
                      "mem-path":self.path,
                      "share":self.share,
                      "size":self.size})


class Chardev(QemuCommandLineObj):
    '''
    -chardev object for qemu command line.
    '''
    def __init__(self, id, backend,  **kwargs):
        self.id = id
        self.backend = backend
        self.options = kwargs

    def cmdline(self):
        self.options['id'] = self.id
        return _build_cmdline('-chardev',
                             self.backend,
                              **self.options)
#        opts =  self.backend + ',id=' + self.id
#        for k, v in self.options.items():
#            opts += ',{}={}'.format(k, v)
#
#        return ['-chardev', opts]

class SMP(QemuCommandLineObj):
    def __init__(self, ncpus=1):
        self.ncpus = ncpus
    def cmdline(self):
        return ['-smp', self.ncpus]

class Bridge(QemuCommandLineObj):
    '''
    Simple bridge object for qemu command line
    '''
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

    A vhostuser socket is comprised not just of a -netdev but also a character
    device and a -device. These will be included in the cmdline() method, so
    don't add them manually.
    '''
    def __init__(self, id, chardev, device, queues=0):
        assert isinstance(chardev, Chardev)
        assert isinstance(device, Device)
        self.chardev = chardev
        self.device = device
        self.queues = queues
        self.id = id

    def cmdline(self):
        args = []
        args.extend(self.chardev.cmdline())
        args.extend(self.device.cmdline())
        kwargs = {'type':'vhost-user',
                  'id':self.id,
                  'chardev':self.chardev.id}
        liargs = []
        if self.queues is not 0:
            kwargs['queues'] = self.queues
            liargs.append('vhostforce')

        args.extend(_build_cmdline('-netdev', *liargs, **kwargs))
        return args


class VNC(QemuCommandLineObj):
    def __init__(self, display=':5'):
        self.display = display
    def cmdline(self):
        return ['-vnc', self.display]

class QemuError(Exception):
    pass

class Qemu:
    '''
    A class wrapping a qemu command line VM instantiation, and potentially later
    allowing users to mount the VM image locally, chroot in and update, install
    packages, &c.

    notable members:
    cmdline -- command line list to be passed to subprocess.Popen. You may
    alter at your own peril.

    '''
    executables = ['/usr/bin/kvm', '/bin/kvm']
    numactl = '/usr/bin/numactl'
    def __init__(self,
                 basic_params,
                 *extra_objects,
                 **kwargs):
        '''
        basic_params -- a BasicParameters object with basic parameters.
        *extra_objects -- extra QemuCommandLine objects which will have their
            cmdline methods called, which are expected to be lists, which will
            be added to the command-line invocation.
        **kwargs -- keyword arguments,
            numa_node -- integer, which numa node to execute on. This will
                result in numactl --membind being called, 'in front of' kvm.
            extra_args -- list, extra arguments to append at the last of the
                command line.
        '''
        executable = None
        self.cmdline = []

        if 'numa_node' in kwargs or \
            'cpu_bind' in kwargs:

            if not os.path.exists(Qemu.numactl):
                raise QemuError('no numactl executable. is numastat installed?')

            self.cmdline.append(Qemu.numactl)
            self.cmdline.append('-a')
            if 'numa_node' in kwargs and \
                kwargs['numa_node'] is not None:
                self.cmdline.append(
                    '--membind={}'.format(kwargs['numa_node']))

            if 'cpu_bind' in kwargs and \
                kwargs['cpu_bind'] is not None:
                self.cmdline.append(
                    '--physcpubind={}'.format(
                        kwargs['cpu_bind'])),


            self.cmdline.append('--')


        for _executable in Qemu.executables:
            if os.path.exists(_executable):
                executable = _executable

        if executable is None:
            raise QemuError("No kvm executable. is qemu installed?")

        self.cmdline.append(executable)
        self.cmdline.extend(basic_params.cmdline())
        for e_o in extra_objects:
            self.cmdline.extend(e_o.cmdline())
        if 'extra_args' in kwargs:
            self.cmdline.extend(kwargs['extra_args'])


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

