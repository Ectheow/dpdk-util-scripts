#!/usr/bin/perl
use POSIX ":sys_wait_h";
use IPC::Cmd qw(can_run run_forked);
use strict;
use warnings;
use v5.20;
use Carp;
use IPC::Open3;
use IO::Select;

my %pids=();
my $VNC_CMD = "vncviewer";
my $KVM_CMD = "kvm";

sub child_exited {
    my $pid=0;
    my @deceased = ();
    do {
        $pid = waitpid(-1, WNOHANG);
        push @deceased, $pid;
    } while $pid > 0; 

    foreach $pid (@deceased) {
        next if $pid <= 0;
        say "Child: $pid cmdline: $pids{$pid} exited.";
        delete $pids{$pid};
    }
}

$SIG{CHLD} = \&child_exited;

my %args = (
    vnc_port => 5,
    memory_gb => 4,
    use_vnc => 0,
    background => 0,
    imgloc => undef,
    isoloc => undef,
    vhostuser_sock => undef,
    use_hugepage_backend => 0);

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


my $vnc = create_vnc_command(%args);
croak "Undefined vnc command" if not defined $vnc and $args{use_vnc} eq "yes";
my $qemu = create_qemu_command(%args);
croak "Undefined qemu command" if not defined $qemu;


my $qemu_pid = process_exec($qemu) or croak "Can't start qemu: $qemu";
my $vnc_pid = undef;

if ($args{use_vnc}) {
    say "Wating for VM to get going to start VNC...";
    sleep 2;
    process_exec($vnc) or croak "Can't start VNC";
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



#my $s = IO::Select->new();
#my @ready=();
#$s->add($q_stdout, $q_stderr, $vnc_stdout, $vnc_stderr);

for (; ; ) {
    sleep 1;
    if (scalar keys %pids == 0) {
        say "All children exited\n";
        exit 0;
    }
}

sub process_exec {
    my $cmdline = shift;
    my ($write, $read, $err);
    my $pid = open3(\*STDIN, ">&STDOUT", ">&STDERR", $cmdline) or do {
        die "Couldn't fork for child\n";
    };

    say "Forked child process $cmdline ($pid)";
    $pids{$pid} = $cmdline;
    return 1;
}

sub create_qemu_command {
    my %args = (
        vnc_port=>undef,
        imgloc=>undef,
        memory_gb=>undef,
        use_hugepage_backend=>undef,
        vhost_user_port=>undef,
        @_,
    );

    die "I need an img/iso location" if not (defined $args{imgloc} or defined $args{isoloc});

    my $mem_mb = $args{memory_gb} * 1024;
    my $mem_gb = $args{memory_gb} . "G";

    croak "Can't run $KVM_CMD" if not can_run($KVM_CMD);
    my $cmdline = "sudo $KVM_CMD "
    . "-boot order=cd "
    . "-cpu host "
    . "-vnc :$args{vnc_port} "
    . "-m " . $mem_mb ." "
    . "-name  'hlinux qemu' ";
    $cmdline .= "-cdrom $args{isoloc} " if defined $args{isoloc};
    $cmdline .= "-drive file=$args{imgloc} " if defined $args{imgloc};

    $cmdline .=
    "-chardev socket,id=char1,path=/var/run/openvswitch/$args{vhostuser_port} "
    . "-netdev type=vhost-user,id=mynet1,chardev=char1,vhostforce "
    . "-device virtio-net-pci,mac=00:00:00:00:00:01,netdev=mynet1 " if $args{vhostuser_port};

    $cmdline .=
    "-object memory-backend-file,id=mem,size=" . $mem_gb . ",mem-path=/dev/hugepages,share=on " 
    . "-numa node,memdev=mem -mem-prealloc " if $args{use_hugepage_backend};

    $cmdline .=
    "-netdev tap,id=mynet2 "
    . "-device virtio-net-pci,netdev=mynet2 ";

    $cmdline =~ tr/\n/ /;
    return $cmdline;
}

sub create_vnc_command {
    my %args = (
        vnc_port=>undef,
        @_,
    );
    croak "Undefined vnc_port" if not defined $args{vnc_port};
    my $vnc = undef;
    if (can_run($VNC_CMD)) {
        $vnc = "$VNC_CMD localhost::590$args{vnc_port}";
        $vnc =~ tr/\n/ /;
    }
    return $vnc;
}

sub usage_and_exit {
    print<<"_EOF_";
$0 usage:
$0 [--use-vnc (yes | no )] [ --vnc-port <portno> ] [ --mem-gb <size> ] [ --imgloc <image-file-location> ] [ --isoloc <iso-file-location> ]  [ --vhostuser-sock <portname> ]
_EOF_
    exit 0;
}

