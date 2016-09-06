import unittest
import os
import time
import signal
from . import qemu
from proctools.ps import PS
from proctools.ps import PSLine

VM_IMAGE='vmtools/test-vm.img'
def compare_simple_cmdline_object(testo, obj1, obj2):
    '''
    Compare command line objects which may have a different ordering in their
    comma separated values for example:
    -object one,two
    -object two,one
    should compare equal.
    '''
    testo.assertEqual(len(obj1), len(obj2))
    testo.assertEqual(obj1[0], obj2[0])

    parms1 = sorted(obj1[1].split(','))
    parms2 = sorted(obj2[1].split(','))
    testo.assertEqual(parms1, parms2)

class TestCommandLineObjects(unittest.TestCase):
    def test_device(self):
        self.assertEqual(
            ('-device vhost-user,id=net0,chardev=chr0'.split(' ')),
            qemu.Device(driver='vhost-user',
                        id='net0',
                        chardev='chr0').cmdline())
    def test_drive(self):
        self.assertEqual(
            ('-drive file={}'.format(VM_IMAGE).split(' ')),
            qemu.Drive(filename=VM_IMAGE).cmdline())
    def test_network_port_nic(self):
        self.assertEqual(
                ('-net nic,model=virtio,macaddr=00:00:00:00:00:01').split(' '),
            qemu.NetworkPortNic(
                mac='00:00:00:00:00:01',
                model='virtio').cmdline())
        self.assertEqual(
            ('-net nic,model=virtio').split(' '),
            qemu.NetworkPortNic(
                model='virtio').cmdline())
    def test_hugepage_memory_back(self):
        compare_simple_cmdline_object(self,
        '-object memory-backend-file,id=mem,size=4096,mem-path=/dev/hugepages,share=on'.split(' '),
        qemu.HugepageMemoryBack(
            size=4096,
            path='/dev/hugepages',
            share=True,
            id='mem').cmdline())
    def test_vhost_user_netdev(self):
        '''
        This is difficult because there are three separate devices created, and
        we have (currently) an optional argument, the number of queues which can
        be used in mulitqueue testing.

        We want to make sure that a netdev with basic parameters works, as well
        as one with optional multiqueue parameters.

        So:
        Create a template dictionary where the keys are the qemu cmdline-string
        names, and the values are templates.

        For each option type:
          create a command line string from the testee object.
          Create a dictionary of command option type to csv-type parameters e.g.
          'device': '-device one,two=3,three=2'
          and so on
          for each qemu option type created:
            create a formatted template strintg
            pass the formatted template string, and the corresponding generated
            string, to the compare_simple_cmdline_object function.


        '''

        option_types = ['multiqueue', '']

        option_values = {
                'multiqueue':{
                    'vhostuser_kwargs':{'queues':2},
                    'chardev_kwargs':{},
                    'device_kwargs':{'mq':'on', 'vectors':6},
                    'netdev':'-netdev type=vhost-user,id=mynet1,chardev=char0,queues=2,vhostforce',
                    'device':'-device virtio-net-pci,mac=00:00:00:00:00:01,netdev=mynet1,mq=on,vectors=6',
                    'chardev':'-chardev socket,id=char0,path=/var/run/vhostuser0',
                },
                '':{
                    'vhostuser_kwargs':{},
                    'chardev_kwargs':{},
                    'chardev_liargs':[],
                    'device_kwargs':{},
                    'netdev':'-netdev type=vhost-user,id=mynet1,chardev=char0',
                    'device':'-device virtio-net-pci,mac=00:00:00:00:00:01,netdev=mynet1',
                    'chardev':'-chardev socket,id=char0,path=/var/run/vhostuser0',
                },
        }

        def qemu_object_for(option_type):
            '''
            qemu_object_for option_type -> string
            option_type -- string representing extra/optional options passed.

            Return -- qemu VhostUserNetdev object
            '''
            return qemu.VhostUserNetdev(
                    id='mynet1',
                    chardev=qemu.Chardev(
                        id='char0',
                        backend='socket',
                        path='/var/run/vhostuser0',
                        **option_values[option_type]['chardev_kwargs']),
                    device=qemu.Device(
                        driver='virtio-net-pci',
                        id=None,
                        mac='00:00:00:00:00:01',
                        netdev='mynet1',
                        **option_values[option_type]['device_kwargs']),
                    **option_values[option_type]['vhostuser_kwargs']
                    ).cmdline()


        def split_on_cmdline_obj(qemu_objects):
            '''
            qemu_objects -- string of qemu command line objects, e.g.
            '-device cats=dogs -netdev dogs=cats'

            Return -- dictionary of strings to strings

            {'device':'-device cats=dogs', 'netdev':'-netdev dogs=cats'}
            '''

            splits = []
            qemu_objects = qemu_objects.strip()
            for i in range(0,len(qemu_objects)):
                c = qemu_objects[i]
                if c == '-' and \
                    ( i-1 < 0 or \
                    qemu_objects[i-1] == ' ' or \
                    qemu_objects[i-1] == '\t' ):
                    splits.append('')

                splits[-1] += c

            d = {}
            for split in splits:
                assert split.startswith('-')

                d[split[1:split.index(' ')]] = split.strip()


            return d


        def get_shouldbe_string_for(option_type, qemu_option):
            '''

            option_type -- type of option, e.g. 'multiqueue'
            qemu_option -- the qemu option, e.g., 'device'

            Return -- string formatted for selected options.
            '''
            return option_values[option_type][qemu_option]

        for option_type in option_types:
            qemu_obj = qemu_object_for(option_type)
            qemu_cmdline_objs = split_on_cmdline_obj(' '.join(qemu_obj))
            for qemu_option,cmdline_value in qemu_cmdline_objs.items():
                template = get_shouldbe_string_for(option_type, qemu_option)
                compare_simple_cmdline_object(self, 
                        template.split(' '),
                        cmdline_value.split(' '))

#        def compare_against_template(template, options, creation_func):
#            '''
#            compare_templates : templates, options, creation_func -> nothing
#
#            templates -- string
#            options -- dictionary
#            creation_func -- function taking a dictionary
#
#            for each option in the options dictionary create from the template
#            string a shouldbe command line string  for each option string.
#
#            Return: list of generated shouldbe strings
#
#            '''
#        shouldbes = []
#
#        #
#        # There are three different types of command line objects, and here are
#        # the 'templates' for these.
#        templates = {
#                'netdev': '-netdev type=vhost-user,id=mynet1,chardev=char0,vhostforce{multiqueue}'
#                'device': '-device virtio-net-pci,mac=00:00:00:00:00:01,netdev=mynet1{multiqueue}'
#                'chardev': '-chardev socket,id=char0,path=/var/run/vhostuser0'
#        }
#
#        #
#        # The permutations of options. Only multiqueue right now, or probably
#        # really ever.
#        extra_options = {
#            'multiqueue':{
#                'netdev':['', ',queues=2'],
#                'device':['', ',vectors=6'],
#                'chardev':['', ''],
#                'object':[{}, {'multiqueue':2}],
#            },
#        }
#
#        shouldbe_all = []
#        #
#        # For each type of option, or 'permutation', create a two-dimensional
#        # list like so:
#        # ( ('-netdev', ...), ('-device', ...), ('-chardev', ...)
#        # where for each permutation we format it with the various possible
#        # values.
#        for permutation,qemu_devices in extra_options.items():
#            shouldbe = []
#            qemu_parameters=[]
#            for qemu_device,options in qemu_devices.items():
#                for actual_option in options:
#                    if qemu_device is not 'object':
#                        template_str = templates[qemu_device]
#                        template_str.format(permutation=actual_option)
#                        shouldbe.append(templates[qemu_device].format(*{permutation:actual_option})
#                    else:
#                        qemu_parameter = {permutation:actual_option}
#
#            assert len(qemu_parameters) == len(shouldbe)
#
#            for i in range(0,len(shouldbe)):
#                result_from_qemu = qemu.VhostUserNetdev(
#                    id='mynet1',
#                    chardev=qemu.Chardev(
#                        id='char0',
#                        backend='socket',
#                        path='/var/run/vhostuser0'),
#                    device=qemu.Device(
#                        driver='virtio-net-pci',
#                        id=None,
#                        mac='00:00:00:00:00:01',
#                        netdev='mynet1')
#                        **qemu_parameters[i])).cmdline()
#                result_from_format = shouldbe[i]
#
#                compare_simple_cmdline_object(
#                        result_from_qemu,
#                        result_from_format)
#
#        for device,optional_permutations in extra_options.items():
#            for permutation in optional_permutations:
#                shouldbe = templates[device]
#                result_from_qemu = qemu.VhostUserNetdev(
#                    id='mynet1',
#                    chardev=qemu.Chardev(
#                        id='char0',
#                        backend='socket',
#                        path='/var/run/vhostuser0'),
#                    device=qemu.Device(
#                        driver='virtio-net-pci',
#                        id=None,
#                        mac='00:00:00:00:00:01',
#                        netdev='mynet1',
#                        *permutation)).cmdline()
#                self.assertEqual(result_from_qemu, shouldbe)
#
#        shouldbes = (
#                ('-netdev type=vhost-user,id=mynet1,chardev=char0,vhostforce').split(' '),
#                ('-device virtio-net-pci,mac=00:00:00:00:00:01,netdev=mynet1').split(' '),
#                ('-chardev socket,id=char0,path=/var/run/vhostuser0').split(' ')),
#
#
#
#        shouldbe=(
#                ('-netdev type=vhost-user,id=mynet1,chardev=char0,vhostforce').split(' '),
#                ('-device virtio-net-pci,mac=00:00:00:00:00:01,netdev=mynet1').split(' '),
#                ('-chardev socket,id=char0,path=/var/run/vhostuser0').split(' '))
#        result_from_qemu = qemu.VhostUserNetdev(
#            id='mynet1',
#            chardev=qemu.Chardev(
#                id='char0',
#                backend='socket',
#                path='/var/run/vhostuser0'),
#            device=qemu.Device(
#                driver='virtio-net-pci',
#                id=None,
#                mac='00:00:00:00:00:01',
#                netdev='mynet1')).cmdline()
#        for run in shouldbe:
#            first = run[0]
#            self.assertIn(first, result_from_qemu)
#            idx = result_from_qemu.index(first)
#
#            compare_simple_cmdline_object(run[1], result_from_qemu[idx+1])

    def test_vnc(self):
        shouldbe = ['-vnc', ':5']
        are = qemu.VNC().cmdline()
        self.assertEqual(shouldbe, are)

    def test_bridge(self):
        shouldbe = [
                ['-net', 'bridge'],
                ['-net', 'bridge,br=br0'],
                ['-net', 'bridge,br=br0,helper=/path/to/helper']]

        are = [
                qemu.Bridge().cmdline(),
                qemu.Bridge(bridge='br0').cmdline(),
                qemu.Bridge(bridge='br0', helper='/path/to/helper').cmdline()]

        self.assertEqual(shouldbe, are)



class TestSimpleLaunch(unittest.TestCase):
    def test_simple_launch(self):
        vm = qemu.Qemu(qemu.BasicParameters(name='namo', bootorder='cd'),
                       qemu.Drive(filename=VM_IMAGE))
        proc = vm.launch()
        self.assertTrue(proc is not None)
        self.assertTrue(proc.poll() is None)
        proc.kill()
    def test_hugepage_launch(self):
        hugepages_file = '/sys/devices/system/node/node0/hugepages/hugepages-{}kB/free_hugepages'.format(1<<20)
        def get_nr_hugepages():
            nr_hugepages = 0
            with open(hugepages_file) as nr_hp_f:
                nr_hugepages = int(nr_hp_f.read().strip())
            return nr_hugepages


        if not os.path.exists(hugepages_file):
            self.skipTest("skipping, no hugepages on system")
            return
        nr_hugepages = get_nr_hugepages()

        if not nr_hugepages:
            self.skipTest('skipping, no extra hugepages available')
            return

        vm = qemu.Qemu(qemu.BasicParameters(name='hugepagesvm', bootorder='cd', memory=nr_hugepages<<10),
                       qemu.Drive(filename=VM_IMAGE),
                       qemu.HugepageMemoryBack(id='hugepages0',
                                               size=str(nr_hugepages) + 'G',
                                               path='/dev/hugepages',
                                               share=True),
                       qemu.Numa(memdev='hugepages0',
                                 cpus=0),
                       numa_node=0,
                       extra_args=['-mem-prealloc'])
        vm.cmdline.append('-mem-prealloc')
        proc = vm.launch()
        self.assertTrue(proc.poll() is None)
        self.assertTrue(proc.returncode is None)
        time.sleep(3)

        print(vm.cmdline)
        nr_hugepages = get_nr_hugepages()
        if nr_hugepages != 0:
            for line in iter(proc.stderr.readline, ''):
                print(line)
                if (line == '\n'):
                    break
        self.assertEqual(nr_hugepages, 0)
        os.kill(proc.pid, signal.SIGINT)



if __name__ == '__main__':
    unittest.main()

