package Net::LinuxBridge;
use warnings;
use Carp;
use Scalar::Util qw(blessed);
use strict;
use Net::NetworkInterface;

use v5.20;
=head
wrapper around the linux bridge
=cut

sub new {
    my ($class, %args) = (shift, @_);

    croak "I need a bridge name" if not defined $args{name};
    croak "Can't create bridge" if not (system("brctl addbr $args{name}") == 0);
    
    my $data = {
        name=>$args{name}, 
        interfaces=>[],
        bridge_interface=>(Net::NetworkInterface->new(name=>$args{name})),
    };
    return bless $data, $class;
}

sub up_all {
    my $self = shift;

    $self->{bridge_interface}->up;
    foreach my $iface (@{$self->{interfaces}}) {
        $iface->up;
    }
}

sub name {
    return $_[0]->{name};
}

sub interface_list {
    return $_[0]->{interfaces};
}

sub add_interface {
    my ($self, %args) = (shift, @_);
    croak "Undefined interface" if not exists $args{interface};
    croak "Need a Net::NetworkInterface object" if not $args{interface}->isa("Net::NetworkInterface");
    push @{$self->{interfaces}}, $args{interface};
    croak "Can't add interface ". $args{interface}->name() if not do {
        system("brctl addif " . $self->{name} . " " . $args{interface}->name()) == 0;
    };
    return 1;
}

sub del_interface {
    my ($self, $iface) = @_; 


    my ($index) = grep { $self->{interfaces}->[$_]->name eq $iface } 0..$#{$self->{interfaces}};

    if (defined $index) {
        splice(@{$self->{interfaces}}, $index, 1);
        system("brctl delif $self->{name} $iface");
    } else {
        carp "Attempt to delete $iface which has no index";
    }

    return defined $index;
}

sub DESTROY {
    my $self = shift;

    my $bridgeif = $self->{name};
    for my $interface (@{$self->{interfaces}}) {
        $self->del_interface($interface->name);
        $interface->down;
    }

    $self->{bridge_interface}->down;

    system("brctl delbr $bridgeif") == 0 or croak "Can't delete $bridgeif bridge";
}

1;
