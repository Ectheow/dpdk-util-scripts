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

sub process_core_list {
    my ($args, $toset) = @_;

    my @list = split ",", $toset;

    $args->{core_list} = [@list];
}

sub add_vhostuser_sock {
    my ($args, $toset) = @_;

    my @list = split ",", $toset;

    scalar @list >= 2 or croak "Need a comma-split pair: $toset";
    push @{$args->{vhostuser_sock}}, {
		name => $list[0], 
		mac => $list[1],
		queues => ($#list >= 2 ? $list[2] : undef),
	        vectors => ($#list >= 3 ? $list[3] : undef),
	};

    return 1;
}

sub usage_and_exit {
    print<<"_EOF_";
$0 usage:
$0 [--use-vnc (yes | no )] [ --vnc-port <portno> ] [ --mem-gb <size> ] [ --imgloc <image-file-location> ] [ --isoloc <iso-file-location> ]  [ --vhostuser-sock <portname> ]
    --use-vnc ( yes | no )  Spawn VNC process?
    --memory-gb <size>      Size of memory in GB
    --imgloc    <path>      path of disk image mounted as c
    --isoloc    <path>      path of iso image mounted as d
    --vhostuser-sock <name>,<mac>,<n-queues>,<n-vectors> name of vhostuser port in /var/run/openvswitch
    --use-hugepage-backend (yes | no)   use the hugepage backend (give VM backing hugepage store?)
    --veth-addr  (ip address)           address to give to veth device on bridge for routing
    --veth-name-root (string)           name for veths, will be <name-root>0 and <name-root>1
    --mgmt-attach-to-bridge             bridge to attach TAP interface for manatement to.
    --background (yes|no)  background process after spawning VNC/qemu.
    --cores <number>                    Number of cores to allocate
    --numa-node <number>		Numa node to bind memory to
    --core-list <cores>			Core list
_EOF_
    exit 0;
}

my %args_spec = (
    vnc_port => {default=>5, handler=>undef, value=>undef},                 # VNC port to listen on/connect to (if --use-vnc)
    memory_gb => {default=>4, handler=>undef},                # GB of memory for VM to use.
    use_vnc => {deafult=>0, handler=>undef},                  # fork off a VNC client once the process has started?
    background => {default=>0, handler=>undef},               # background? 
    imgloc => {default=>undef, handler=>undef},               # location of harddisk image file.
    isoloc => {default=>undef, handler=>undef},               # location of ISO file to insert into CD drive.
    vhostuser_sock => {default=>undef, handler=>\&add_vhostuser_sock},       # name of vhostuser file in /var/run/openvswitch (socket)
    veth_addr=> {default=>undef, handler=>undef},              # address to assign to a veth interface.
    veth_name_root=> {default=>undef, handler=>undef},         # root name for veth device(s)
    use_hugepage_backend => {default=>undef, hanlder=>undef},     # use hugepages object for memory backend?
    test_dev_mac => {default=>undef, handler=>undef},
    mgmt_attach_to_bridge=>{default=>undef, handler=>undef},
    cores => {default=>undef, handler=>undef},
    numa_node => {
        default=>-1, 
        handler=>undef}, 
    core_list => {
        default=>[],
        handler=>\&process_core_list},
);   

my %args = ();

foreach my $k (keys %args_spec) {
	$args{$k} = $args_spec{$k}->{default};
}

while((my $var = shift @ARGV)) {
    if(not $var =~ m/^\-\-.*/) {
        croak "Bad argument: $var";
    }
    $var = substr($var, 2);
    $var =~ tr/\-/_/;
    if ($var eq "help") {
        usage_and_exit();
    }
    if (not exists($args_spec{$var})) {
        croak "Bad key: $var";
    } else {
        if (defined($args_spec{$var}->{handler})) {
            $args_spec{$var}->{handler}->(\%args, shift(@ARGV));
        } else {
            $args{$var} = shift @ARGV;
        }
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
