#!/usr/bin/python
import sys
import ovssetup.ovs
import os
import time

'''
setup-simple-bridge.py -- script to create a simple test OVS bridge.

   +---------------+
   |     VM        |
   |               |
   +--|--------|---+
      |        |
      |        |
   +--|--------|----------+
   | vhostuser vhostuser  |
   |  |        |          |
   | flow     flow        |
   |  |        |          |
   | dpdk     dpdk        |
   +--|--------|----------+
    NIC0      NIC1

I try to set up the dpdk ports, the vhosutuser ports, and the flow connecting
the two in this script. I assume that you already have two NICs bound or
otherwise available for DPDK. The bridge must not already exist.
Usage:
    ./setup-simple-bridge.py [bridgename]
'''




def main(args):
    bridge_name, cpumask = args
    ovssetup.ovs.stop()
    time.sleep(1)
    ovssetup.ovs.start()
    if ovssetup.ovs.Bridge(bridge_name) in ovssetup.ovs.list_bridges():
        print("Bridge {} already exists.".format(
            bridge_name))
        raise SystemExit(1)
    ovssetup.ovs.run_command('vsctl', ['add-br',
                                       bridge_name],
                                      ['set',
                                       'Bridge',
                                       bridge_name,
                                       'datapath_type=netdev'])
    time.sleep(1)
    br = ovssetup.ovs.Bridge(bridge_name)
    br.del_flows()
    for porttype in (('dpdk{}', 'dpdk'),
                     ('vhostuser{}', 'dpdkvhostuser')):
        for i in range(0, 2):
            nm = porttype[0].format(i)
            br.add_port(
                nm,
                ['set', 'Interface', nm, 'type={}'.format(porttype[1])])

    ports = br.get_flow_ports()
    vhostuserports = filter(lambda p: p[1].find('vhostuser') != -1, ports)
    dpdkports =      filter(lambda p: p[1].find('dpdk') != -1, ports)
    assert len(dpdkports) == len(vhostuserports) and len(dpdkports) == 2

    portpairs = zip(dpdkports, vhostuserports)
    assert len(portpairs) == 2


    # see the docstring for add_flow for the potentially confusing
    # indexing.
    for portpair in portpairs:
        for order in ((0, 1), (1, 0)):
            br.add_flow("in_port={},actions:output_port={}".format(
                        portpair[order[0]][0],
                        portpair[order[1]][0]))
    if cpumask is not None:
        ovssetup.ovs.run_command('vsctl', ['set', 
                                           'Open_vSwitch', 
                                           '.', 
                                           'other_config:pmd-cpu-mask={}'.format(cpumask)])



if __name__ == '__main__':
    args = sys.argv[1:]
    if not len(args):
        args = ['br0', None]
    elif len(args) == 1:
        args.append(None)
    elif len(args) > 2:
        print("bad command line. I just need the name of a single bridge.\n"
              "Is that too hard?")
        raise SystemExit(1)

    if not os.geteuid() == 0:
        print("You need to be root.")
        raise SystemExit(1)
    main(args)
