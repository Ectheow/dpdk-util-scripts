package Net::VethNode;
use strict;
use warnings;
use v5.20;
use Carp;
use Net::NetworkTopologyNode;
use List::MoreUtils qw(pairwise);
use parent qw(Net::NetworkTopologyNode);

sub __create {
    my $self = shift;
    my $config = shift;

    my $root_name = $config->{name};
    my $ips = $config->{ips};

    system("ip link add name " . $root_name . "0 type veth peer name " . $root_name . "1") == 0 or do {
        croak "IP link add with root name $root_name failed";
    };

    $self->{names} = [$root_name . "0", $root_name . "1"];
    unless (not defined $ips) {
        pairwise {
            system("ip address add $b dev $a") or do {
                carp "Can't add IP $b to $a";
            };
        } @{$self->{names}}, @{$ips};
    }
}

sub DESTROY {
    my $self = shift;

    my $todel = $self->{names}->[0];
    if (not defined $todel) {
        carp "undefined name for veth device.";
        return;
    }
    system("ip link del $todel") == 0 or do {
        carp "couldn't delete veth device $todel";
    };
}

1;
