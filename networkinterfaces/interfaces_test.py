import unittest
import random
import interfaces
import subprocess
import re
from .interfaces import iplink, ipaddr

class TestIPLink(unittest.TestCase):
    def test_list_ifaces(self):
        iplink_reg = re.compile(r'\d+:\s*([\w\-\d]+):')
        def get_output_from_ip():
            links = []
            output = subprocess.check_output('ip link').split('\n')
            for i in output:
                m = re.match(iplink_reg, i)
                if m:
                    links.append(m.group(1))
            return links
        
        self.assertEqual(sorted(get_output_from_ip()),
                         sorted(interfaces.ifnames()))


    @classmethod
    def _get_vethpair_names(cls):
        randstr = hex(random.randrange(100, 200))[2:]
        return  ('testveth{}0'.format(randstr), 
                'testveth{}1'.format(randstr))

    @classmethod
    def _add_veth(cls, pair):
        return iplink('add', 
                    'name', 
                    pair[0],
                    'type', 
                    'veth', 
                    'peer',
                    'name', 
                    pair[1])

    def test_add_veth(self):
        pair = TestIPLink._get_vethpair_names() 

        for v in pair:
            self.assertNotIn(v, interfaces.ifnames())

        self.assertTrue(TestIPLink._add_veth(pair) is not None)
        for v in pair:
            self.assertIn(v, interfaces.ifnames())

        self.assertTrue(iplink('del', pair[0]))
        
        for v in pair:
            self.assertNotIn(v, interfaces.ifnames())

        with self.assertRaises(interfaces.IPRoute2Error):
            iplink('cats')
        with self.assertRaises(interfaces.IPRoute2Error):
            iplink('del', 'bogus')

    def test_get_addr(self):
        regex = re.compile(r'\d+:\s+([^\s])+\s+inet6?\s+([^\s])+\s+')
        def get_name_address_pairs():
            ifaces = []
            output = subprocess.check_output(
                    ['ip', '--oneline', 'address']).split('\n')

            for ln in output:
                m = re.match(regex, ln)
                if m:
                    ifaces.append(m.group(1), m.group(2))
            return ifaces

    def test_set_addr(self):
        pair = TestIPLink._get_vethpair_names()
        TestIPLink._add_veth(pair)
        self.assertEquals(ipaddr('inet', 'show', dev=pair[0]), [])
        self.assertEquals(ipaddr('inet', 'show', dev=pair[1]), [])
        self.assertEquals(ipaddr('inet', 'add', '192.168.10.10/24',
            dev=pair[0]), [''])
        self.assertEquals(len(ipaddr('inet', 'show', dev=pair[0])), 1)
        iplink('del',pair[0])
        
        

class TestNetworkInterface(unittest.TestCase):
    def test_initialize(self):
        pass

    def test_set_up(self):
        pass

    def test_set_down(self):
        pass

    def test_set_ip(self):
        pass

    def test_set_mac(self):
        pass


if __name__ == '__main__':
    unittest.main()
