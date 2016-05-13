package VirtualMachine;
use strict;
use warnings;
use v5.20;
use Carp;
use ProcessTools;
require Exporter;

our @ISA=qw(Exporter);

my $KVM_CMD = "kvm";

sub new {
    my $class = shift; 
    my %args = (
            vnc_port => 5,                 # VNC port to listen on/connect to (if --use-vnc)
            memory_gb => 4,                # GB of memory for VM to use.
            use_vnc => 0,                  # fork off a VNC client once the process has started?
            imgloc => undef,               # location of harddisk image file.
            isoloc => undef,               # location of ISO file to insert into CD drive.
            vhostuser_sock => undef,       # name of vhostuser file in /var/run/openvswitch (socket)
            use_hugepage_backend => 0,     # use hugepages object for memory backend?
            @_,
            );   

    my $data = { args=>\%args};

    return bless $data, $class;
}

sub create_qemu_command {
    my %args = (
        vnc_port=>undef,
        imgloc=>undef,
        memory_gb=>undef,
        use_hugepage_backend=>undef,
        vhost_user_sock=>undef,
        @_,
    );

    croak "I need an img/iso location" if not (defined $args{imgloc} or defined $args{isoloc});
    croak "I need a memory argument" if not defined $args{memory_gb};

    my $mem_mb = $args{memory_gb} * 1024;
    my $mem_gb = $args{memory_gb} . "G";

    #croak "Can't run $KVM_CMD" if not can_run($KVM_CMD);
    my $cmdline = "sudo $KVM_CMD "
    . "-boot order=cd "
    . "-cpu host "
    . "-vnc :$args{vnc_port} "
    . "-m " . $mem_mb ." "
    . "-name  'hlinux qemu' ";
    $cmdline .= "-cdrom $args{isoloc} " if defined $args{isoloc};
    $cmdline .= "-drive file=$args{imgloc} " if defined $args{imgloc};

    $cmdline .=
    "-chardev socket,id=char1,path=/var/run/openvswitch/$args{vhostuser_sock} "
    . "-netdev type=vhost-user,id=mynet1,chardev=char1,vhostforce "
    . "-device virtio-net-pci,mac=00:00:00:00:00:01,netdev=mynet1 " if $args{vhostuser_sock};

    $cmdline .=
    "-object memory-backend-file,id=mem,size=" . $mem_gb . ",mem-path=/dev/hugepages,share=on " 
    . "-numa node,memdev=mem -mem-prealloc " if $args{use_hugepage_backend};

    $cmdline .=
    "-netdev tap,id=mynet2 "
    . "-device virtio-net-pci,netdev=mynet2 ";

    $cmdline =~ tr/\n/ /;
    return $cmdline;
}

sub fork_vm {
    my $self = shift;
    my %args = ( @_);

    my $cmd = create_qemu_command(%{$self->{args}});
    say "Launching: $cmd";
    return ProcessTools::process_exec($cmd);
}

1;

