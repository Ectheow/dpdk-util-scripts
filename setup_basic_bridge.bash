#!/usr/bin/bash
#set -x

GRUBFILE="/etc/default/grub"
DPDK_IFACES="/etc/dpdk/interfaces"
OPENVSWITCH_CONFIG="/etc/default/openvswitch-switch"
MODULE_DEFAULT="uio_pci_generic"
BRIDGENAME_DEFAULT="br0"
NRDPDK_PORTS_DEFAULT=2
COREMASK_DEFAULT="0x3"
HUGEPAGES_LINE="default_hugepagesz=1GB hugepagesz=1G hugepages=5"

source ./logging.bash

function has_grub_hugepage_entry {
	if awk 'BEGIN {code=1;} /^GRUB_CMDLINE_LINUX=\".*hugepages=.*\"$/ { code=0; } END { exit(code) }' $GRUBFILE; then
		return 0
	else
		return 1
	fi
}

function install_packages {
	apt-cache show openvswitch-switch-dpdk &>/dev/null
	if [ $? ]; then
		apt-get install --force-yes --assume-yes -q openvswitch-switch-dpdk || error "Couldn't install openvswitch-switch-dpdk"
	else
		error "No suck package in cache openvswitch-switch-dpdk"
	fi
}

function setup_bridge {
	local bridge=$1
	local nifaces=$2

	ovs-vsctl --if-exists del-br $bridge
	ovs-vsctl add-br $bridge -- set bridge $bridge datapath_type=netdev || error "Couldn't setup netdev bridge"

	for ((i=0;i<nifaces;i++)); do
		ovs-vsctl --if-exists del-port $bridge dpdk$i
		ovs-vsctl add-port $bridge dpdk$i -- set interface dpdk$i type=dpdk || error "Couldn't add DPDK port to bridge. (serious)"
	done
}

function update_grub {
	echo ">>>You need to reboot your system. Rerun script after.<<<"
	exit 0
	update-grub
}

function edit_grub_cmdline {
	if has_grub_hugepage_entry; then
		info "There is already a hugepage entry in $GRUBFILE"
		return 0
	elif grep 'GRUB_CMDLINE_LINUX=' $GRUBFILE &>/dev/null; then
		sed -i 's/GRUB_CMDLINE_LINUX="\(.*\)"/GRUB_CMDLINE_LINUX="\1 '$HUGEPAGES_LINE'"/' \
		$GRUBFILE
		update_grub
	else 
		echo 'GRUB_CMDLINE_LINUX=default_hugepagesz=1GB hugepagesz=1GB hugepages=5' >> /etc/default/grub
		update_grub
	fi
}

function stupid_check {
	if [  $nr_dpdk_ports -eq 0  -o	${#pci_devs[@]} -eq 0  ]; then
		error "Bad command line arguments."
	fi
}

function edit_dpdk_config {
	local pci_dev=$1
	for pci_dev in ${pci_devs[@]}; do
		local line="pci $pci_dev uio_pci_generic"
		if grep "$line" $DPDK_IFACES &>/dev/null; then
			info "DPDK already has this interface. Skipping..."
		else
			echo $line >> $DPDK_IFACES
		fi	
	done
}

function check_for_module {
	modprobe $bind_module
	if [ ! $? -eq 0 ]; then
		error "Can't modprobe $bind_module"
	fi
	info "Using module $bind_module"
}

function edit_ovs_config {
        local dpdk_line="export DPDK_OPTS=\"--dpdk -c $coremask -n $nr_dpdk_ports\"" 

        if grep "$dpdk_line" $OPENVSWITCH_CONFIG &>/dev/null; then
		info "openvswitch-switch already has DPDK_OPTS, skipping..."
	else
		echo $dpdk_line>> $OPENVSWITCH_CONFIG
	fi
}

pci_devs=( )
nr_dpdk_ports=$NRDPDK_PORTS_DEFAULT
bridgename=$BRIDGENAME_DEFAULT
bind_module=$MODULE_DEFAULT
coremask=$COREMASK_DEFAULT

function usage {
echo "$0 usage:"
echo "$0 --pci-devs DEVS [ --nr-dpdk-ports PORTS ] [ --bridgename BRIDGENAME ] [ --dpdk-coremask COREMASK ]"
cat <<_EOF_
    --pci-devs <DEVS>
        Whitespace separated list of pci device addresses to add to the dpdk interfaces file
        $DPDK_IFACES. 
    --nr-dpdk-ports <PORTS>
        Number of ports to pass in the DPDK_OPTS variable in $OPENVSWITCH_CONFIG
    --bridgename <BRIDGENAME>
        Name of bridge to create that has the dpdk ports
    --dpdk-coremask <COREMASK>
        coremask to pass to DPDK in DPDK_OPTS in $OPENVSWITCH_CONFIG
This program edits the following configuration files:
    $GRUBFILE : Adds (if necessary) hugepages entry
    $OPENVSWITCH_CONFIG : Adds a line to cause openvswitch to pass dpdk options to ovs-vswitchd
    $DPDK_IFACES : Adds PCI interfaces to bind to a pci passthrough device.
_EOF_
}
while [ $# -gt 0 ]; do
	case "$1" in
	--pci-devs)
		# device IDs 
		shift
		while echo $1 | egrep '^[^\-]+' &>/dev/null; do
			pci_devs=(${pci_devs[@]} $1)
			info "cmdline: added PCI device $1"
			shift
		done
		;;
	--nr-dpdk-ports)
		shift
		nr_dpdk_ports=$1
		info "cmdline: Set nr DPDK ports to $1"
		shift
		;;
        --dpdk-coremask)
                shift
                coremask=$1
                info "cmdline: Set coremask to $1"
                shift
                ;;
	--bridgename)
		shift
		bridgename=$1
		info "cmdline: set bridgename to $1"
		shift
		;;
        --usage|--help)
		shift
		usage
		exit 0
		;;
	*)
		error "Unknown argument: $1"
		;;
	esac
done

stupid_check
check_for_module
install_packages
edit_grub_cmdline
edit_ovs_config
edit_dpdk_config ${pci_devs[@]}
update-alternatives --set ovs-vswitchd /usr/lib/openvswitch-switch-dpdk/ovs-vswitchd-dpdk
systemctl restart dpdk
systemctl restart openvswitch-switch
setup_bridge $bridgename ${#pci_devs[@]}
echo "Success! top should show an ovs-vswitchd process at 100% CPU usage"
exit 0
