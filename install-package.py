#!/usr/bin/python
import apt.debfile
import traceback
import argparse
import operator
import sys
import subprocess
import paramiko
import signal
import os
import re
import time
import shutil


'''
This is a helper program for git-bisect regression testing. It should:
    * Stop the qemu process that's running
    * Install debs it gets pointed to over the ones currently installed.
    * Restart the qemu process
    * SSH Into the qemu process VM
    * Start the testp3,4,5md program.
'''

EXIT_FAILURE=255

def status(message):
    print("STATUS %s" % message)
def success(message):
    print("OK %s" % message)
def done(message):
    print("DONE %s" % message)
def fatal_error(message, long_message, exception=None):
    print("ERROR: %s\n%s", message, long_message)
    raise SystemExit(1)

GIT_BISECT_GOOD=0
GIT_BISECT_BAD=1
GIT_BISECT_ABORT=255
QEMU_PROCESS_NAME='qemu-system-x86_64'

client = None
config = {
        "imgloc":"/home/me/hlx-gold-small",
        "scripts":"/home/me/scripts/scripts",
        "memory":"4",
        "vhostuser":"vhostuser",
        "vhostuser_path":"/var/run/openvswitch",
        "cores":"4",
        "core_list":"4,5,6,7",
        "veth_addr":"192.168.122.1/24",
        "veth_name":"myveth",
        "bridge_name":"mgmt-br",
        "with_dpdk":"/usr",
        "internal_git_patch":"patch-internal-dpdk.patch",
        "external_git_patch":"patch-artifacts.patch",
        "internal_dpdk":True,
        "extra_cflags":"-Ofast -march=native",
        "pmd_cpu_mask":"4", #60006
        "ovs_ctl":"/bin/sh /usr/local/share/openvswitch/scripts/ovs-ctl",
        "ovsdb_server_arguments":"--remote=punix:/usr/local/var/run/openvswitch/db.sock \
            --remote=db:Open_vSwitch,Open_vSwitch,manager_options \
            --pidfile \
            --detach \
            /etc/openvswitch/conf.db",
        "ovs_vswitchd_arguments":"--dpdk -c 0x1 -n 2 --socket-mem 4096 \
            -- \
            unix:/usr/local/var/run/openvswitch/db.sock \
            --pidfile \
            --detach"
}

PACKAGES=[
        'openvswitch-common',
        'openvswitch-switch']

VM_IP="192.168.122.115"
VM_PASS="iforgot"
VM_USER="me"
QEMU_CMD="qemu-system-x86_64"
QEMU_SCRIPT_CMD="qemu_linux.pl"
VM_START="perl %(scripts)s/qemu_linux.pl \
    --imgloc %(imgloc)s \
    --memory-gb %(memory)s \
    --veth-addr %(veth_addr)s \
    --veth-name-root %(veth_name)s \
    --mgmt-attach-to-bridge %(bridge_name)s \
    --vhostuser-sock %(vhostuser)s0,00:00:00:00:00:01 \
    --vhostuser-sock %(vhostuser)s1,00:00:00:00:00:02 \
    --use-hugepage-backend yes \
    --cores 4 \
    --numa-node 0 \
    --core-list %(core_list)s \
    --vhostuser-path %(vhostuser_path)s \
    --background yes" % config
TESTPMD_CMD="sudo /home/me/testpmd-daemon"
UP_LINKS="ip l set up dev %(veth_name)s0 && ip l set up dev %(veth_name)s1" % config
BRIDGE="br0"

class JustAccept(paramiko.MissingHostKeyPolicy):
    def missing_host_key(self, client, hostname, key):
        return

def stop_vm(args):
    global client
    '''
    Stop the virtual machine. Try to first gracefully shutdown
    by SSHing into it. If that doesn't work kill all qemu processes.
    '''
    if client is None:
        start_client()

    if client is not None:
        print("Shutting down client")
        client.exec_command("sudo shutdown -P")
        time.sleep(2)

    out = subprocess.check_output(["ps", "--no-headers", "-e", "-o", "cmd:80,pid"])
    for signal_send in (signal.SIGINT, signal.SIGKILL):
        for line in out.split('\n'):
            if line.find(QEMU_CMD) != -1 or line.find(QEMU_SCRIPT_CMD) != -1:
                pid = int(re.split(r"\s+", line)[-1])
                print("Killing %d\n" % pid)
                os.kill(pid, signal_send)
    cmds = [
            'ip l del mgmt-br',
            'ip l del myveth0']
    for cmd in cmds:
        try:
            subprocess.call(cmd, shell=True)
        except Exception as e:
            pass
    client = None

def start_vm(args):
    '''
    Start the virtual machine.
    '''
    status("Start VM")
    try:
        subprocess.check_output(VM_START, shell=True, stderr=subprocess.STDOUT)
        subprocess.check_output(UP_LINKS, shell=True, stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as e:
        print("Failed call:\n%s\n" % e.cmd)
        print("Output:\n%s\n" % e.output)
        raise e
    else:
        success("Start VM")

def yield_lines_from_process(cmd, shell=False):
    output = subprocess.check_output(cmd, shell=shell)
    for line in output.split('\n'):
        yield line

def get_ps_list(fields, taskname=None):
    li = ['ps', '--no-headers', '-L']

    if taskname is not None:
        li.extend(['-C', taskname])
    else:
        li.append('-e')

    li.append('-o')
    li.append(','.join(fields))
    return li


def taskset_vm(args):
    matches = []
    status("Taskset VM")
    

    matches = [PSLine(i) for i in
            filter(lambda line: True if len(line) > 0 else False,
                PS(process_name=QEMU_PROCESS_NAME, 
                    fields=['comm', 'tid', 'psr', 'time']))]

    matches.sort()
    matching_process=matches[-1]
    cores = {}

    for match in matches:
        if not cores.has_key(match.psr):
            cores[match.psr] = 0
        cores[match.psr] += 1

    sorted_cores = sorted(cores.items(), key=operator.itemgetter(1))
    most_used_core = sorted_cores[-1][0]

    if matching_process.pid != most_used_core:
        core = most_used_core+1
        status("Move tid %d to psr %d, hex mask %s"%
            (matching_process.pid, core, hex(1<<core)))
        subprocess.check_call(
            "taskset -p %s %d" %
                (hex(1<<core),
                matching_process.pid),
             shell=True)
    else:
        status("No need to move processor, it's already there")

    success("Taskset VM")



def start_client():
    global client
    try:
        client = paramiko.SSHClient()
        client.load_system_host_keys()
        client.set_missing_host_key_policy(JustAccept())
        client.connect(hostname=VM_IP,
                       username=VM_USER,
                       password=VM_PASS)
    except paramiko.SSHException as e:
        print("Caught SSHException starting client: %r" % e)
        client = None
        return None
    except Exception as e:
        print("Caught Unknown exception: %r" % e)
        traceback.print_exc(file=sys.stdout)
        client = None
        return None

def start_testpmd(args):
    global client
    '''
    Start testpmd on the virtual machine.
    Try to SSH in, exit if that doesn't work.
    '''
    status("Start testpmd")
    for i in range(1, 10):
        time.sleep(5)
        if client is None:
            status("Starting client...")
            start_client()
        else:
            break

    if client is None:
        raise RuntimeError("Unable to start testpmd, no SSH connection")

    client.exec_command(TESTPMD_CMD)
    success("Start testpmd")

def stop_ovs(args):
    '''
    stop openvswitch daemons
    '''
    status("Stop OVS")
    cmd = "%(ovs_ctl)s stop" % config
    try:
        subprocess.check_output(cmd, shell=True)
    except subprocess.CalledProcessError as e:
        print("Unable to stop OVS w/ %s" % cmd)
        print("output %s" % e.output)
    else:
        success("Stop OVS")
    output = subprocess.check_output(["ps", "-e", "-o", "cmd,pid", "--no-headers"])
    for line in output.split('\n'):
        if line.find('ovsdb-server') != -1 or line.find('ovs-vswitchd') != -1:
            status("Kill process %s" % line)
            pid = int(re.split(r'\s+', line)[-1])
            os.kill(pid, signal.SIGINT)


def build_ovs(args):
    '''
    build openvswitch
    '''
    if args.no_build_ovs:
        status("Skip Build OVS")
        return
    git_cmds = [
            "git clean -xdf",
            "git checkout -f"]
    patch_cmds = []
    if config['internal_dpdk']:
        patch_cmds.extend([
            "patch -p1 < ../%(internal_git_patch)s" % config,
            "QUILT_PATCHES=debian/patches quilt push -a"])
    else:
        patch_cmds.extend([
            "patch -p1 < ../%(external_git_patch)s" % config])

    make_cmds = [
            "./boot.sh",
            "CFLAGS=\"%(extra_cflags)s\" ./configure --with-dpdk=%(with_dpdk)s" % config,
            "make -j",
            "make install"]

    cmds = []
    for li in (git_cmds, patch_cmds, make_cmds):
        cmds.extend(li)

    status("Building OVS")
    try:
        for cmd in cmds:
            subprocess.check_output(cmd, shell=True)
            success(cmd)
    except subprocess.CalledProcessError as e:
        print("failed to build OVS with command %s" % cmd)
        print("output:\n%s\n" % e.output)
        raise e
    else:
        success("Build OVS")

def clean_ovs(args):
    '''
    clean openvswitch
    '''
    status("Clean OVS")
    git_cmds = [
            "git clean -xdf",
            "git checkout -f"]

    patch_cmds = []
    if config['internal_dpdk']:
        patch_cmds.extend([
            "QUILT_PATCHES=debian/patches quilt pop -a",
            "patch -p1 -R < ../%(internal_git_patch)s" % config])
    else:
        patch_cmds.extend([
            "patch -p1 -R < ../%(external_git_patch)s" % config])

    make_cmds = [
            "make uninstall",
            "make clean"]

    cmds = []
    for li in (make_cmds, patch_cmds, git_cmds):
        cmds.extend(li)
    for cmd in cmds:
        try:
            subprocess.check_output(cmd, shell=True)
        except subprocess.CalledProcessError as e:
            print("failed to clean OVS with command %s" % cmd)
            print("output:\n%s\n" % e.output)
            pass
        else:
            success("Clean OVS")
    if os.path.exists('/usr/local/var/run/openvswitch'):
        shutil.rmtree('/usr/local/var/run/openvswitch')

def setup_ovs_flows(args):
    status("Add flows")
    cmds = ["ovs-ofctl del-flows %s" % BRIDGE]
    ports = [ ('2', '4'), ('1', '3')]
    for port_pair in ports:
        for pair in [(0, 1), (1, 0)]:
            cmds.append("ovs-ofctl add-flow %s in_port=%s,action:output_port=%s" % (BRIDGE, port_pair[pair[0]], port_pair[pair[1]]))
    try:
        for cmd in cmds:
            subprocess.check_output(cmd, shell=True)
    except subprocess.CalledProcessError as e:
        print("Failed to add flow %s" % cmd)
    else:
        success("Add flows")

def start_ovs(args):
    '''
    start openvswitch daemons
    '''
    status("Start OVS")
    cmds = [
        "ovsdb-server %(ovsdb_server_arguments)s" % config,
        "ovs-vsctl set Open_vSwitch . other_config:pmd-cpu-mask=%(pmd_cpu_mask)s" % config,
        "ovs-vswitchd %(ovs_vswitchd_arguments)s" % config,
        "ovs-vsctl --no-wait init"]
    try:
        for cmd in cmds:
            subprocess.check_output(cmd, shell=True)
    except subprocess.CalledProcessError as e:
        print("failed to start OVS command %s" % cmd)
        print("output:\n%s\n" % cmd.output)
    else:
        success("Start OVS")


def get_input(args):
    while True:
        user_input = raw_input("[Gg]ood/[Bb]ad/[Ss]kip/[Aa]bort? > ")
        if user_input == 'g' or user_input == 'G':
            return GIT_BISECT_GOOD
        elif user_input == 'b' or user_input == 'B':
            return GIT_BISECT_BAD
        elif user_input == 's' or user_input == 'S':
            return GIT_BISECT_SKIP
        elif user_input == 'a' or user_input == 'A':
            return GIT_BISECT_ABORT


def install_pkgs(args):
    installed = set()
    os.chdir(args.directory)
    files = filter(
            lambda fname:
                re.match(r'.*\.deb', fname),
            os.listdir('.'))
    for pkg in PACKAGES:
        print 'package %s '% pkg
        regex = r'%s_%s_(amd64|all)\.deb' % (
            pkg, re.escape(args.version))
        matches = filter(lambda fname:
            re.match(regex, fname), files)
        if len(matches) == 0:
            raise RuntimeError("No files matching %s found" % pkg)
        else:
            pkg_obj = apt.debfile.DebPackage(filename=matches[0])
            if not pkg_obj.check():
                raise RuntimeError("Package: %s (%s)is not installable."
                    % (pkg, matches[0]))
            else:
                print("Install: %s" % matches[0])
                pkg_obj.install()
                installed.add(pkg)
    if not installed == set(PACKAGES):
        raise RuntimeError("Not all packages were found and installed!")

def main(args):
    parser = argparse.ArgumentParser(description = 'Installer argument parser.')

    parser.add_argument('--directory',
        type=str,
        help='Directory to chdir to and install pkgs from')

    parser.add_argument('--version',
        type=str,
        help='Debian version of packages to install')

    parser.add_argument("--no-build-ovs",
        dest='no_build_ovs',
        action='store_true',
        help='Don\'t build OVS')

    parser.add_argument('--dpdk',
        type=str,
        default=config['with_dpdk'])

    parser.add_argument('--no-start-ovs',
        dest='no_start_ovs',
        action='store_true',
        help='Don\'t start OVS (or stop it)')

    parser.add_argument('--extra-cflags',
        type=str,
        default=None)

    parser.add_argument('--no-start-vm',
        dest='no_start_vm',
        action='store_true',
        default=False,
        help='Don\'t stop or start VM')

    parsed_args = parser.parse_args(args)
    if parsed_args.dpdk !=  config['with_dpdk']:
        config['with_dpdk'] = parsed_args.dpdk
        config['internal_dpdk'] = False
    if parsed_args.extra_cflags:
        config['extra_cflags'] = parsed_args.extra_cflags

    if not parsed_args.no_start_vm:
        stop_vm(parsed_args)
    if not parsed_args.no_start_ovs:
        stop_ovs(parsed_args)
    if not parsed_args.no_build_ovs:
        clean_ovs(parsed_args)
        build_ovs(parsed_args)
    if not parsed_args.no_start_ovs:
        start_ovs(parsed_args)

    setup_ovs_flows(parsed_args)

    if not parsed_args.no_start_vm:
        start_vm(parsed_args)
        start_testpmd(parsed_args)

    status("Sleep after VM start/testpmd start")
    time.sleep(60)
    done("Sleep after VM start")
    taskset_vm(parsed_args)
    code = get_input(parsed_args)

    if not parsed_args.no_start_ovs:
        stop_ovs(parsed_args)
    if not parsed_args.no_build_ovs:
        clean_ovs(parsed_args)
    sys.exit(code)

if __name__ == '__main__':
    os.environ['PERL5LIB'] = "/home/me/scripts/lib"
    main(sys.argv[1:])
