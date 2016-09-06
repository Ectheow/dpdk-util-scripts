#!/usr/bin/python
import vmtools.qemu
import sys
import os
import argparse
import time
import operator
import paramiko
from proctools.ps import PS

class IgnoreMissingHostKeyPolicy(paramiko.MissingHostKeyPolicy):
    pass

def fatal_error(string):
    sys.stderr.write("ERROR: {}\n".format(string))
    sys.exit(1)


def status(string):
    print("STATUS: {}".format(string))

def start_testpmd(username,
                 ip,
                 password,
                 testpmd):
    '''
    SSH to the IP, and start testpmd.
    '''
    NBYTES = 1024
    client = paramiko.client.SSHClient()

    client.load_system_host_keys()
    client.set_missing_host_key_policy(
            IgnoreMissingHostKeyPolicy())
    client.connect(ip,
            username=username,
            password=password)
    transport = client.get_transport()
    sess = transport.open_channel(kind='session')
    sess.exec_command(testpmd)

    time.sleep(3)
    if sess.exit_status_ready():
        status("testpmd exited ")
        status(" cmd: {}".format(
            testpmd))
        status(" code: {}".format(
            sess.recv_exit_status()))
        for reader in ( (sess.recv_stderr_ready, sess.recv_stderr),
                        (lambda: True, sess.recv)):
            if reader[0]():
                data = reader[1](NBYTES)
                while data is not None and data != '':
                    sys.stdout.write(data)
                    data = reader[1](NBYTES)

            else:
                status("Can't get output for testpmd")
    return client, sess


def taskset_vm_appropriately(process, cpulist):
    '''
    taskset the VM threads. The VM will have lots of threads, and by default
    even if you give it lots of CPUs all the threads end up on the same CPU
    limiting VM performance.

   This script will take care of this issue, by:
    * getting a list of threads and thread IDs belonging to your qemu process.
    * finding the thread with the highest % CPU
    * moving that thread to the CPU in cpulist that has the minimum number of
      threads.

    process -- subprocess.Popen object
    cpulist -- CSV list of CPUs. Like numactl but right now no relative CPUS.

    returns -- nothing

    '''
    def parse_cpulist_to_hex(cpulist):
        mask = 0
        masklist = []

        for cpu in cpulist.strip().split(','):
            if cpu.find('-') != -1:
                start, stop = cpu.split('-')
                for i in range(start, stop+1):
                    mask |= 1<<int(cpu)
                    masklist.append(int(cpu))
            else:
                masklist.append(int(cpu))
                mask |= 1<<int(cpu)

        return mask, masklist



    def get_lowest_used_cpu(threadids, cpulist):
        cpu_usage = {}
        for cpu in cpulist:
            cpu_usage[cpu] = sum(
                                 map(lambda t: 1,
                                 filter(lambda t: int(t.psr) == cpu, threadids)))

        least_used = sorted(cpu_usage.items(),
                            key=operator.itemgetter(1))[0]
        status('least used: {}'.format(least_used))

        return least_used[0]


    mask, masklist = parse_cpulist_to_hex(cpulist)
    threadids = list(iter(PS(process_name=process.pid,
                   fields=['time', 'tid', 'psr'],
                   threads=True)))

    highest_cpu_usage = sorted(threadids, key=lambda p: p.time)[-1]
    lowest_used_cpu = get_lowest_used_cpu(threadids, masklist)

    highest_cpu_usage.set_psr_mask(1<<lowest_used_cpu)




def make_vhostuser_netdev(arg_string, num_queues=0):
    '''
    make_vnc_port : arg_string -> qemu.VhostUserNetdev object

    arg_string -- string passed in on the command line. This  will be in the
    format of <path>,qeueues.

    Returns: a qemu.VhostUserNetdev object

    The id of the objects created will be derived from the filename of the
    socket itself, which should be unique.
    '''

    splits = arg_string.split(',')
    assert len(splits) <= 2

    socket_id = splits[0]

    device_kwargs = {}
    vhostuser_kwargs ={}
    if num_queues != 0:
        device_kwargs['vectors'] = num_queues*2+2
        device_kwargs['mq'] = 'on'
        vhostuser_kwargs['queues'] = num_queues

    chrdev = vmtools.qemu.Chardev(
                    id='char{}'.format(socket_id),
                    backend='socket',
                    path='/var/run/openvswitch/{}'.format(socket_id))
    device = vmtools.qemu.Device(
                    driver='virtio-net-pci',
                    id='mynetdevdevice{}'.format(socket_id),
                    netdev='netdev{}'.format(socket_id),
                    **device_kwargs)

    return vmtools.qemu.VhostUserNetdev(
            id='netdev{}'.format(socket_id),
            chardev=chrdev,
            device=device,
            **vhostuser_kwargs)



def main(args):
    VIRTIO_MODEL='virtio'
    HUGEPAGE_PATH='/dev/hugepages'
    client, sess = None, None
    parser = argparse.ArgumentParser(description='Process VM parameters')
    parser.add_argument('--name',
                        default='VM',
                        help='Name of the VM')
    parser.add_argument('--memory',
                        default=4096,
                        help='Memory for the VM. in MB.')
    parser.add_argument('--img',
                        default=None,
                        help='FS location of image',
                        required=True)
    parser.add_argument('--vhost-socket',
                        default=[],
                        help='location of a vhost user socket',
                        action='append')
    parser.add_argument('--bridgename',
                        default=None,
                        help='Name of a bridge to add')
    parser.add_argument('--vnc',
                        default=':5',
                        help='VNC port to listen on')
    parser.add_argument('--multiqueue',
                        default='0',
                        help='multiqueue number default 0=off.')
    parser.add_argument('--cpu-bind',
                        default=None,
                        help='mask  of CPUs to run on')
    parser.add_argument('--numa-node',
                        default=None,
                        help='numa node to run on')
    parser.add_argument('--testpmd',
                       default=None,
                       help='testpmd command to run')
    parser.add_argument('--username',
                        default=None,
                        help='username for VM login')
    parser.add_argument('--password',
                        default=None,
                        help='password for VM login')
    parser.add_argument('--vm-ncpus',
                        default=3,
                        help='number of CPUS for the VM')
    parser.add_argument('--ip',
                        default=None,
                        help='VM IP')


    pargs=parser.parse_args(args)

    cmd_objs = [
            vmtools.qemu.BasicParameters(
                name=pargs.name,
                memory=pargs.memory),
            vmtools.qemu.SMP(ncpus=pargs.vm_ncpus),
            vmtools.qemu.Drive(filename=pargs.img),
            vmtools.qemu.NetworkPortNic(
                model=VIRTIO_MODEL),
            vmtools.qemu.HugepageMemoryBack(
                id='hugepage0',
                size=int(pargs.memory)<<20,
                path=HUGEPAGE_PATH,
                share=True),
            vmtools.qemu.Numa(
                    memdev='hugepage0'),
            vmtools.qemu.VNC(display=pargs.vnc)]


    number_queues = int(pargs.multiqueue)
    for sock in pargs.vhost_socket:
        cmd_objs.append(make_vhostuser_netdev(sock, num_queues=number_queues))

    if pargs.bridgename is not None:
        br = vmtools.qemu.Bridge(bridge='br1')
        cmd_objs.append(br)

    vm = vmtools.qemu.Qemu(*cmd_objs,
            numa_node=pargs.numa_node,
            cpu_bind=pargs.cpu_bind)
    proc = vm.launch()
    time.sleep(1)
    if isinstance(proc.returncode, int) and proc.returncode != 0:
        sys.stderr.write(proc.stderr.read())
        fatal_error("qemu exited prematurely")

    status("sleeping...")
    time.sleep(10)
    status('done sleeping')
    if proc.returncode is not None:
        fatal_error("VM exited prematurely...")

    
    if pargs.ip is not None:
        client, sess = start_testpmd(
                username=pargs.username,
                ip=pargs.ip,
                password=pargs.password,
                testpmd=pargs.testpmd)

    time.sleep(15)
    taskset_vm_appropriately(proc, pargs.cpu_bind)

    proc.wait()

    if proc.returncode != 0:
        sys.stderr.write(proc.stderr.read())
        fatal_error("qemu gave a non-zero exit code: {}".format(
            proc.returncode))


if __name__ == '__main__':
    main(sys.argv[1:])
