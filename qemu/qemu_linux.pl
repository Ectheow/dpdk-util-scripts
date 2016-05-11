#!/usr/bin/perl
use POSIX ":sys_wait_h";
use strict;
use warnings;
use v5.20;
use IPC::Open3;
use IO::Select;

my $vnc_port = 5;
my $memory_gb =  4;
my $use_vnc = "no";
my $background = 0;
my $imgloc = undef;
my $isoloc = undef;

while ((my $var = shift @ARGV)) {
    if ($var eq "--mem-gb") {
        $memory_gb = shift @ARGV;
    } elsif($var eq "--use-vnc") {
        $use_vnc = shift @ARGV; 
    } elsif($var eq "--vnc-port") {
        $vnc_port = shift @ARGV;
    } elsif($var eq "--background") {
        $background = 1;
    } elsif($var eq "--imgloc") {
        $imgloc = shift @ARGV;
    } elsif($var eq "--isoloc") {
        $isoloc = shift @ARGV;
    } else {
        usage_and_exit();
    }
}

die "I need an img/iso location" if not (defined $imgloc or defined $isoloc);
my $mem_mb = $memory_gb * 1024;
my $mem_gb = $memory_gb . "G";
my $cmdline = "sudo kvm "
. "-boot order=cd "
. "-cpu host "
. "-vnc :$vnc_port "
. "-m " . $memory_gb * 1024 ." "
. "-name  'hlinux qemu' ";
$cmdline .= "-cdrom $isoloc " if defined $isoloc;
$cmdline .= "-drive file=$imgloc " if defined $imgloc;
$cmdline .=
"-chardev socket,id=char1,path=/var/run/openvswitch/vhost-user-1 "
. "-netdev type=vhost-user,id=mynet1,chardev=char1,vhostforce "
. "-device virtio-net-pci,mac=00:00:00:00:00:01,netdev=mynet1 "
. "-object memory-backend-file,id=mem,size=" . $mem_gb . ",mem-path=/dev/hugepages,share=on "
. "-numa node,memdev=mem -mem-prealloc "
. "-netdev tap,id=mynet2 "
. "-device virtio-net-pci,netdev=mynet2 ";

#my $cmdline =<<"_EOF_";
#sudo kvm
#-boot order=cd
#-cpu host
#-vnc :$vnc_port
#-m $mem_mb
#-name 'hlinux qemu'
#-cdrom hlinux-iso.iso
#-drive file=hlinux.img
#-chardev socket,id=char1,path=/var/run/openvswitch/vhost-user-1 
#-netdev type=vhost-user,id=mynet1,chardev=char1,vhostforce 
#-device virtio-net-pci,mac=00:00:00:00:00:01,netdev=mynet1 
#-object memory-backend-file,id=mem,size=$mem_gb,mem-path=/dev/hugepages,share=on 
#-numa node,memdev=mem -mem-prealloc 
#-netdev tap,id=mynet2 
#-device virtio-net-pci,netdev=mynet2
#_EOF_

my $vnc =<<"_EOF_";
vncviewer 'localhost::590$vnc_port'
_EOF_
$cmdline =~ tr/\n/ /;
$vnc =~ tr/\n/ /;

my %pids=();
my ($vnc_pid, $vnc_stdout, $vnc_stderr) = (undef, undef, undef);
my ($q_pid, $q_stdout, $q_stderr) = process_exec($cmdline);

@{$pids{$q_pid}} = ($q_stdout, $q_stderr);
if ($use_vnc =~ /[Yy](es)?/) {
    say "Wating for VM to get going to start VNC...";
    sleep 2;
    ($vnc_pid, $vnc_stdout, $vnc_stderr) = process_exec($vnc);
    @{$pids{$vnc_pid}} = ($vnc_stdout, $vnc_stderr);
}
if ($background) {
    my $pid = fork;
    if ($pid != 0) {
        say "Backgrounding.";
        exit 0;
    } 
    open STDIN, "</dev/null";
    open STDOUT, ">/dev/null";
    open STDERR, ">&STDOUT";
}

my $s = IO::Select->new();
my @ready=();
$s->add($q_stdout, $q_stderr, $vnc_stdout, $vnc_stderr);
for (; ; ) {
    my $pid = waitpid(-1, WNOHANG);

    @ready = $s->can_read(0);
    for my $fh (@ready) {
        if ($background) {
            # Throw away output if backgrounded.
            <$fh>;
        } else {
            print <$fh>;
        }
    }

    if ($pid > 0) {
        say "**A child ($pid) exited code $?**";
        if (scalar(@{$pids{$pid}}) > 0)  {
            $s->remove(@{$pids{$pid}});
            if (not scalar $s->handles) {
                say "All children exited";
                exit;
            }
        } else {
            say "But I'm not polling that!";
        }
    }
}

sub process_exec {
    my $cmdline = shift;
    my ($write, $read, $err);
    my $pid = open3($write, $read, $err, $cmdline) or do {
        die "Couldn't fork for child\n";
    };

    say "Forked child process $cmdline ($pid)";
    close $write;
    return ($pid, $read, $err);
}

sub usage_and_exit {
    print<<"_EOF_";
$0 usage:
$0 [--use-vnc (yes | no )] [ --vnc-port <portno> ] [ --mem-gb <size> ] [ --imgloc <image-file-location> ] [ --isoloc <iso-file-location> ]
_EOF_
    exit 0;
}

