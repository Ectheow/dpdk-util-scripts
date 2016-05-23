package Net::DummyNode;
use strict;
use warnings;
use v5.20;
use Carp;
use Net::NetworkTopologyNode;
use Net::NetworkInterface;
use parent qw(Net::NetworkTopologyNode);

sub __create {
    my ($self, $config) = @_;

    my $name = $config->{name};
    my $ip = $config->{ip};

    system("ip link add name $name type dummy") == 0 or do {
        croak "ip link create for dummy $name failed";
    };

    my $interface = Net::NetworkInterface->new(name=>$name);
    unless (not defined $ip) {
        $interface->add_ip($config->{ip}) or do {
            carp "Can't add IP to $name";
        };
    }

    $self->{interface} = $interface;
}

sub DESTROY {
    my $self = shift;

    my $todel = $self->{interface}->name();

    system("ip link del $todel") == 0 or do {
        carp "Can't delete dummy device $todel";
    };
}
1;
