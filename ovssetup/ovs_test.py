import unittest
import ovssetup.ovs
import time
import logging
import os
from . import ps

class TestOVSStartStop(unittest.TestCase):
    def test_ovs_exists(self):
        self.assertTrue(ovssetup.ovs.installed()[0])

    def test_start_ovs(self):
        ovssetup.ovs.start()
        for lenshouldbe in (1, 0):
            pslist = [ i for i in iter(ps.PS(process_name='ovs-vswitchd', threads=False))]
            self.assertEqual(len(pslist), lenshouldbe)

            pslist = [ i for i in iter(ps.PS(process_name='ovsdb-server', threads=False))]
            self.assertEqual(len(pslist), lenshouldbe)

            if lenshouldbe != 0:
                ovssetup.ovs.stop()


#@unittest.skip("skip OVS call")
class TestOVSCall(unittest.TestCase):
    def setUp(self):
        ovssetup.ovs.start()
        os.system("ovs-vsctl --may-exist add-br br1")
        time.sleep(3)

    def test_ovs_cmd(self):
        show = ovssetup.ovs.run_command("vsctl", ["show"])
        self.assertTrue(len(show.stdout.read()) > 0)
        flows = ovssetup.ovs.run_command("ofctl", ["show", "br1"])
        self.assertTrue(len(flows.stdout.read()) > 0)

    def tearDown(self):
        os.system("ovs-vsctl --if-exists del-br br1")
        ovssetup.ovs.stop()


class TestOVSBridge(unittest.TestCase):
    def setUp(self):
        ovssetup.ovs.start()
        ovssetup.ovs.run_command('vsctl', ['--if-exists', 'del-br', 'br1'])
        ovssetup.ovs.run_command('vsctl', ['add-br', 'br1'])
        time.sleep(3)

    def test_list(self):
        brs = ovssetup.ovs.list_bridges()
        self.assertIn(ovssetup.ovs.Bridge('br1'), brs)

    def test_ports(self):
        pass

    def tearDown(self):
        ovssetup.ovs.run_command('vsctl', ['--if-exists', 'del-br', 'br1'])
        ovssetup.ovs.stop()

#@unittest.skip("skip OVS add/remove")
class TestOVSAddRemove(unittest.TestCase):
    def setUp(self):
        ovssetup.ovs.start()
        time.sleep(3)
        ovssetup.ovs.run_command('vsctl', ['--if-exists', 'del-br', 'br0'])

    def test_ovs_add_bridge(self):
        self.assertEquals(ovssetup.ovs.list_bridges(),
            [])
        ovssetup.ovs.run_command('vsctl', ['add-br', 'br0'], 
                                          ['set', 'Bridge', 'br0', 'datapath_type=netdev'])
        bridge = ovssetup.ovs.Bridge('br0')
        bridge.add_port('dpdk0',
            ['set', 'Interface', 'dpdk0', 'type=dpdk'])
        self.assertEquals(
            bridge.ports(),
            ['dpdk0'])
        bridges = ovssetup.ovs.list_bridges()
        self.assertEquals(bridges, 
                          [ovssetup.ovs.Bridge('br0')])

    def test_ovs_add_flows(self):
        bridge = ovssetup.ovs.Bridge('br0')

    def tearDown(self):
        ovssetup.ovs.stop()
        ovssetup.ovs.run_command('vsctl', ['--if-exists', 'del-br', 'br0'])



class TestOVSFlows(unittest.TestCase):
    def setUp(self):
        ovssetup.ovs.start()
        ovssetup.ovs.run_command('vsctl', ['--if-exists', 'del-br', 'br0'],
                                          ['add-br', 'br0'])

    def test_simple_flows(self):
        br = ovssetup.ovs.Bridge('br0')
        for i in range(0, 2):
            os.system("ip link add type veth")
        br.add_port('veth0')
        br.add_port('veth2')
        flow_ports = br.get_flow_ports()
        self.assertEqual(2, len(flow_ports))
        names = []
        for flow_port in flow_ports:
            names.append(flow_port[1])
            self.assertEqual(3, len(flow_port))

        self.assertEqual(sorted(names), ['veth0', 'veth2'])



    def tearDown(self):
        os.system('ip link del veth0')
        os.system('ip link del veth2')
        ovssetup.ovs.run_command('vsctl', ['--if-exists', 'del-br', 'br0'])
        ovssetup.ovs.stop()

if __name__ == '__main__':
    if os.geteuid() != 0:
        print("you must be root")
        raise SystemExit(1)
    logging.basicConfig(filename='ovs_test.log', level=logging.DEBUG)
    unittest.main()
