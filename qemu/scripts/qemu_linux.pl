#!/usr/bin/perl
use POSIX ":sys_wait_h";
use IPC::Cmd qw(can_run run_forked);
use strict;
use warnings;
use v5.20;
use Carp;
use VMTools::VirtualMachine;
use Net::LinuxBridge;
use Net::VethNode;
use ProcessTools;
use VMTools::Vnc;
use IPC::Open3;
use IO::Select;

sub usage_and_exit {
    print<<"_EOF_";
$0 usage:
$0 [--use-vnc (yes | no )] [ --vnc-port <portno> ] [ --mem-gb <size> ] [ --imgloc <image-file-location> ] [ --isoloc <iso-file-location> ]  [ --vhostuser-sock <portname> ]
    --use-vnc ( yes | no )  Spawn VNC process?
    --memory-gb <size>      Size of memory in GB
    --imgloc    <path>      path of disk image mounted as c
    --isoloc    <path>      path of iso image mounted as d
    --vhostuser-sock <name> name of vhostuser port in /var/run/openvswitch
    --use-hugepage-backend (yes | no)   use the hugepage backend (give VM backing hugepage store?)
    --test-dev-mac                      MAC to give to vhostuser port on boot
    --veth-addr  (ip address)           address to give to veth device on bridge for routing
    --veth-name-root (string)           name for veths, will be <name-root>0 and <name-root>1
    --mgmt-attach-to-bridge             bridge to attach TAP interface for manatement to.
    --background (yes|no)  background process after spawning VNC/qemu.
_EOF_
    exit 0;
}

my %args = (
    vnc_port => 5,                 # VNC port to listen on/connect to (if --use-vnc)
    memory_gb => 4,                # GB of memory for VM to use.
    use_vnc => 0,                  # fork off a VNC client once the process has started?
    background => 0,               # background? 
    imgloc => undef,               # location of harddisk image file.
    isoloc => undef,               # location of ISO file to insert into CD drive.
    vhostuser_sock => undef,       # name of vhostuser file in /var/run/openvswitch (socket)
    veth_addr=>undef,              # address to assign to a veth interface.
    veth_name_root=>"veth",         # root name for veth device(s)
    use_hugepage_backend => 0,     # use hugepages object for memory backend?
    test_dev_mac => undef,
    mgmt_attach_to_bridge=>undef,
    );   

while((my $var = shift @ARGV)) {
    if(not $var =~ m/^\-\-.*/) {
        croak "Bad argument: $var";
    }
    $var = substr($var, 2);
    $var =~ tr/\-/_/;
    if ($var eq "help") {
        usage_and_exit();
    }
    if (not exists($args{$var})) {
        croak "Bad key: $var";
    } else {
        $args{$var} = shift @ARGV;
        if ($args{$var} =~ /[Nn][Oo].*/) {
            $args{$var} = 0;
        } elsif($args{$var} eq "yes") {
            $args{$var} = 1;
        }
    }
}


my $bridge = undef;
my $veth = undef;
if (defined $args{mgmt_attach_to_bridge}) {
    $bridge = Net::LinuxBridge->new(name=>$args{mgmt_attach_to_bridge});
    $args{mgmt_attach_to_bridge} = $bridge;
}

if (defined $args{veth_addr}) {
    $veth = Net::VethNode->new; 
    $veth->create(
        config=> {
            ips=>[undef, $args{veth_addr}],
            name=>$args{veth_name_root}
        });                    
    $bridge->add_interface(interface=>
        Net::NetworkInterface->new(name=>($veth->names())->[0] ) );
} elsif (defined $args{veth_name_root}) {
    croak "Veth name root defined w/o veth-addr";
}

my $qemu = VMTools::VirtualMachine->new(%args);
$qemu->fork_vm() or croak "Can't fork qemu VM";
if ($args{use_vnc}) {
    say "Wating for VM to get going to start VNC...";
    sleep 2;
    Vnc::launch_vnc_at(x_server=>$args{vnc_port}) or croak "Can't launch VNC";
}


if ($args{background}) {
    my $pid = fork;
    if ($pid != 0) {
        say "Backgrounding.";
        exit 0;
    } 
    open STDIN, "</dev/null";
    open STDOUT, ">/dev/null";
    open STDERR, ">&STDOUT";
}


if (defined $bridge) {
    $bridge->up_all;
}

ProcessTools::loop_waitpid();
