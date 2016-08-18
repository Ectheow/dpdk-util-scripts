import subprocess
import ovs
import os
import logging
import re

OVS_PREFIX_PATHS={
        'packaged':'/usr',
        'source':'/usr/local'}

OVS_BINARIES={
        "ovsdb-server":"sbin/",
        "ovs-vswitchd":"sbin/",
        "ovs-vsctl":"bin/",
        "ovs-appctl":"bin/",
        "ovs-ofctl":"bin/",
        'ovs-ctl':'share/openvswitch/scripts/'}


OVS_STOP_START_METHODS = {
    "system-scripts":{
        '/bin/systemctl': {
            'stop':['stop', 'openvswitch-switch'],
            'start':['start', 'openvswitch-switch']
            },
        '/etc/init.d/openvswitch-switch': {
            'stop':['stop'],
            'start':['start'],
        },
    },
    "ovs-commands":{
        'ovs-ctl':{
            'stop':['stop'],
            'start':['start'],

        },
#        'ovs-appctl':{
#            'stop':[[]],
#            'start':[[]],
#        },
    }
}
class OVSCommandError(Exception):
    pass


def __iterate_methods(action):
    succeeded = False

    for command_type, commands in OVS_STOP_START_METHODS.items():

        for command_path, command_specs in  commands.items():
            path_list = []
            command_paths = []

            if command_type == 'ovs-commands':
                for _, prefix in OVS_PREFIX_PATHS.items():
                    command_paths.append(os.path.sep.join([prefix,
                                             OVS_BINARIES[command_path],
                                             command_path]))
            else:
                command_paths.append(command_path)

            for possible_command_path in command_paths:
                if not os.path.exists(possible_command_path):
                    continue
                path_list.append(possible_command_path)
                path_list.extend(command_specs[action])
                proc = subprocess.Popen(path_list,
                                        stdout=subprocess.PIPE,
                                        stderr=subprocess.PIPE)

                stdout, stderr = proc.communicate()
                retcode = proc.wait()
                if retcode != 0:
                    logging.info('{} failed: {}'.format(
                        ' '.join(path_list), stderr))
                else:
                    logging.debug('{} succeeded.'.format(' '.join(path_list)))
                    succeeded = True


        if succeeded:
            break



def start():
    '''
    start openvswitch, in the same way the distro does.
    Tries various methods, init scripts, systemctl, etc.
    '''
    __iterate_methods('start')

def stop():
    '''
    stop openvswitch, in the same way that the distro
    does, or else by force.
    '''
    __iterate_methods('stop')

def installed():
    '''
    Simplistic test for if the vswitchd and server exist.
    '''
    for prefix_type in OVS_PREFIX_PATHS:

        all_found=True
        for binary in OVS_BINARIES:
            path = os.path.sep.join([OVS_PREFIX_PATHS[prefix_type],
                                     OVS_BINARIES[binary],
                                     binary])
            all_found &= os.path.exists(path)

        if all_found:
            return all_found, prefix_type

    return False, None

def _argv_command_list(suffix, *arguments):
    '''
    generate an argv list for an OVS command.
    _argv_command_string('vsctl', ['add-port', 'br0', 'tap0'], ['set', 'Interface', 'tap0', 'cats']) ==>

    ['/sbin/ovs-vsctl', 'add-port', 'br0', 'tap0', '--', 'set', 'Interface', 'tap0', 'cats']
    '''
    _, installtype = installed()
    argvlist = []
    path = os.path.sep.join([OVS_PREFIX_PATHS[installtype],
                             OVS_BINARIES['ovs-'+suffix],
                             'ovs-'+suffix])
    if not os.path.exists(path):
        raise RuntimeError("path: {} doesn't exist".format(path))

    argvlist.append(path)
    for arglist in arguments:
        for arg in arglist:
            argvlist.append(arg)
        argvlist.append('--')

    return argvlist



def run_command(suffix, *arguments):
    '''
    run an ovs command, returning a subprocess.Popen object.

    the arguments should be lists that will be separated by --.
    e.g.
    run_command('vsctl', ['add-port', 'br0', 'dpdk0'], ['set', 'interface', 'dpdk0', 'type=dpdk'])
    results in:
    ovs-vsctl add-port br0 dpdk0 -- set interface dpdk0 type=dpdk

    '''
    argvlist = _argv_command_list(suffix, *arguments) 
    pr = subprocess.Popen(argvlist,
                          stderr=subprocess.PIPE,
                          stdout=subprocess.PIPE,
                          universal_newlines=True)

    return pr

def run_command_get_out(suffix, *arguments):
    proc = run_command(suffix, *arguments)
    stdout = proc.stdout.read()
    stderr = proc.stderr.read()
    if proc.wait() != 0:
        raise OVSCommandError("can't run {}: {}".format(
            _argv_command_list(suffix, *arguments), stderr))

    return stdout

def list_bridges():
    bridges = []
    proc = run_command('vsctl', ['list-br'])
    for i in iter(proc.stdout.readline, ''):
        bridges.append(Bridge(i.strip()))

    if proc.wait() != 0:
        raise OVSCommandError("can't list system bridges: {}"
            .format(proc.stderr.read()))

    return bridges

class Bridge:
    '''
    Representation of an OVS bridge. Should be a simple labor-saving device to
    allow the user to easily manipulate the bridge.
    '''

    def __init__(self, name):
        self.name = name

    def ports(self):
        return map(lambda s: s.strip(),
                filter(lambda s: True if len(s) else False, 
                       run_command_get_out('vsctl', ['list-ports', self.name]).split('\n')))

    def add_port(self, name, *args):
        return run_command_get_out('vsctl', ['add-port', self.name, name], *args)

    def del_port(self, name):
        return run_command_get_out('vsctl', ['del-port', self.name, name], *args)

    def del_flows(self):
        return run_command_get_out('ofctl', ['del-flows', self.name])

    def get_flows(self):
        pass

    def get_flow_ports(self):
        '''
        returns list of ports like so:
        number, port name, address, link state
        so you get a list of tuples -
        [
         (1, 'tap0', '00:00:00:00:00', 'LINK_UP'),
         (2, 'tap1', '00:00:00:00:00', 'LINK_DOWN'),
         ]
        '''
        output = run_command_get_out('ofctl', ['show', self.name])
        lines = output.split('\n')
        name_pat = re.compile(r'^\s+(\d+)\(([\w\d\-\_]+)\):\s*addr:([\d\w\:]+)')
        flows = []
        for line in lines:
            m = re.match(name_pat, line)
            if m is not None:
                flows.append((int(m.group(1)), m.group(2), m.group(3)))
        return flows
        

    def add_flow(self, string):
        '''
        add a new flow to the bridge. the flow can be a
        list or string.

        b.add_flow(['in_port=1', 'actions:output_port=2'])
        b.add_flow('in_port=1,actions:output_port=2')
        '''
        pass

    def __cmp__(self, other):
        assert isinstance(other, Bridge)
        return cmp(self.name, other.name)

