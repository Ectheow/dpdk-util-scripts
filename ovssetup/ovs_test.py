import unittest
import ovssetup.ovs
import time
import logging
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
        time.sleep(3)

    def test_ovs_cmd(self):
        show = ovssetup.ovs.run_command("vsctl", ["show"])
        self.assertTrue(len(show.stdout.read()) > 0)
        flows = ovssetup.ovs.run_command("ofctl", ["show", "br1"])
        self.assertTrue(len(flows.stdout.read()) > 0)

    def tearDown(self):
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
        ovssetup.ovs.stop()

@unittest.skip("skip OVS add/remove")
class TestOVSAddRemove(unittest.TestCase):
    def test_ovs_add_bridge(self):
        self.assertEquals(ovs.list_bridges(),
            [])
        bridge = ovs.Bridge('br0')
        bridge.add_port('dpdk0',
            ['set', 'Interface', 'type=dpdk'])
        self.assertEquals(
            bridge.ports(),
            ['dpdk0'])
        bridges = ovs.list_bridges()
        self.assertEquals(bridges, ['br0'])

    def test_ovs_add_flows(self):
        bridge = ovs.Bridge('br0')


if __name__ == '__main__':
    logging.basicConfig(filename='ovs_test.log', level=logging.DEBUG)
    unittest.main()
