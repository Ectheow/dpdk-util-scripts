#!/bin/bash
VETH_ROOT_DEFAULT="veth"
BRIDGENAME_DEFAULT="br0"

source ./logging.bash

function stupid_check {
        if [ -z $veth_addr ]; then
                error "Need a veth address"
	fi
}

function add_veth_link {
	local ovs_bridge=$1
	local veth_addr=$2
        local veth_ovs_side=$3"0"
        local veth_user_side=$3"1"

        
	if ip link show dev $veth_ovs_side &>/dev/null; then
		ip link del $veth_ovs_side || error "Couldn't delete link $veth_ovs_side"
	fi

	ip link add $veth_user_side type veth peer name $veth_ovs_side type veth || error "Couldn't add a new veth link $veth_ovs_side"
	ip address add $veth_addr dev $veth_user_side

        ovs-vsctl --if-exists del-port $ovs_bridge $veth_ovs_side
	ovs-vsctl add-port $ovs_bridge $veth_ovs_side

        ip link set up dev $veth_ovs_side
	ip link set up dev $veth_user_side
}

function usage {
echo "Usage: "
echo "$0 --ipaddr ADDR [ --bridgename BRIDGENAME ] [ --veth_root ROOT_NAME ]"
cat <<_EOF_
    --ipaddr <ADDR> 
        Assign ADDR to the user end of the veth interface created.
    --bridgename <BRIDGENAME>
        Use BRIDGENAME as the ovs bridge to add a port to.
    --veth_root <ROOT_NAME>
        Use ROOT_NAME as a name root for veth interfaces - if you pass in
        'veth' you get veth0 and veth1.
    This script creates a veth interface, attaches one side to an ovs bridge,
    and the other is assigned an IP. If a veth interface already exists with
    the name (default veth, unless you pass --veth_root), it is deleted.
_EOF_
}

veth_addr=""
bridgename=$BRIDGENAME_DEFAULT
veth_name_root=$VETH_ROOT_DEFAULT
while [ $# != 0 ]; do
        case "$1" in
                --ipaddr)
			shift
			veth_addr=$1
                        info "Using ip $veth_addr"
			shift
			;;
		--bridgename)
			shift
			bridgename=$1
                        info "Using bridge $bridgename"
			shift
			;;
		--veth_root)
			shift
			veth_name_root=$1
			info "using veth interface name root $veth_name_root"
			shift
                        ;;
                --usage|--help)
                        usage
                        exit 0
			;;
		*)
			;;
	esac
done

stupid_check
add_veth_link $bridgename $veth_addr $veth_name_root
