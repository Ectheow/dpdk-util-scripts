package LinuxBridge;
use warnings;
use Carp;
use Scalar::Util qw(blessed);
use strict;
use NetworkInterface;
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
        bridge_interface=>(NetworkInterface->new(name=>$args{name})),
    };
    return bless $data, $class;
}

sub up_all {

}

sub interface_list {
    return $_[0]->{interfaces};
}

sub add_interface {
    my ($self, %args) = (shift, @_);
    croak "Undefined interface" if not exists $args{interface};
    croak "Need an object" if not $args{interface}->isa("NetworkInterface");
    push @{$self->{interfaces}}, $args{interface};
    croak "Can't add interface ". $args{interface}->name() if not do {
        system("brctl addif " . $self->{name} . " " . $args{interface}->name()) == 0;
    };
    return 1;
}

sub del_interface {

}

sub DESTROY {
    my $self = (@_);

    my $bridgeif = $self->{bridge_interface}->name();
    system("brctl delbr $bridgeif") or croak "Can't delete $bridgeif bridge";
}

1;
