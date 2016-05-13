#!/usr/bin/perl
use POSIX ":sys_wait_h";
use IPC::Cmd qw(can_run run_forked);
use strict;
use warnings;
use v5.20;
use Carp;
use VirtualMachine;
use ProcessTools;
use Vnc;
use IPC::Open3;
use IO::Select;

sub usage_and_exit {
    print<<"_EOF_";
$0 usage:
$0 [--use-vnc (yes | no )] [ --vnc-port <portno> ] [ --mem-gb <size> ] [ --imgloc <image-file-location> ] [ --isoloc <iso-file-location> ]  [ --vhostuser-sock <portname> ]
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
    bridge_to_attach_tap => undef, # name of bridge to create (if it doesn't exist) and attach a TAP to.
    veth_addr=>undef,              # address to assign to a veth interface.
    use_hugepage_backend => 0,     # use hugepages object for memory backend?
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


my $qemu = VirtualMachine->new(%args);
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


ProcessTools::loop_waitpid();
