package DummyNode;
use strict;
use warnings;
use v5.20;
use Carp;
use NetworkTopologyNode;
use parent qw(NetworkTopologyNode);

sub __create {
    my ($self, $config) = @_;

    my $name = $config->{name};
    my $ip = $config->{ip};

    system("ip link add name $name type dummy") == 0 or do {
        croak "ip link create for dummy $name failed";
    };

    my $interface = NetworkInterface->new($name);
    unless (not defined $ip) {
        $interface->add_ip($config->{ip}) or do {
            carp "Can't add IP to $name";
        };
    }

    $self->{interface} = $interface;
}

sub DESTROY {
    my $self = shift;

    my $todel = $self->{interface}->name;

    system("ip link del $todel") or do {
        carp "Can't delete dummy device $todel";
    };
}
