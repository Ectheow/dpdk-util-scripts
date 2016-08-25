import unittest
import os
import time
from . import qemu
from proctools.ps import PS
from proctools.ps import PSLine

VM_IMAGE='vmtools/test-vm.img'
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
        self.assertEqual(
        '-object memory-backend-file,id=mem,size=4096,mem-path=/dev/hugepages,share=on'.split(' '),
        qemu.HugepageMemoryBack(
            size=4096,
            path='/dev/hugepages',
            share=True,
            id='mem').cmdline())
    def test_vhost_user_netdev(self):
        shouldbe=(
                ('-netdev type=vhost-user,id=mynet1,chardev=char0,vhostforce').split(' '),
                ('-device virtio-net-pci,mac=00:00:00:00:00:01,netdev=mynet1').split(' '),
                ('-chardev socket,id=char0,path=/var/run/vhostuser0').split(' '))
        result_from_qemu = qemu.VhostUserNetdev(
            id='mynet1',
            chardev=qemu.Chardev(
                id='char0',
                backend='socket',
                path='/var/run/vhostuser0'),
            device=qemu.Device(
                driver='virtio-net-pci',
                id=None,
                mac='00:00:00:00:00:01',
                netdev='mynet1')).cmdline()
        for run in shouldbe:
            first = run[0]
            self.assertIn(first, result_from_qemu)
            idx = result_from_qemu.index(first)

            params_shouldbe = sorted(run[1].split(','))
            params_are = sorted(result_from_qemu[idx+1].split(','))

            self.assertEqual(params_shouldbe, params_are)
        
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
                                 cpus=1))
        vm.cmdline.append('-mem-prealloc')
        proc = vm.launch()
        self.assertTrue(proc.poll() is None)
        self.assertTrue(proc.returncode is None)
        time.sleep(3)

        print(vm.cmdline)
        nr_hugepages = get_nr_hugepages()
        for line in iter(proc.stderr.readline, ''):
            print(line)        
        self.assertEqual(nr_hugepages, 0)



if __name__ == '__main__':
    unittest.main()

