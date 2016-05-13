use strict;
use warnings;
use v5.20;
use Carp;



sub add_linux_bridge {
    my %args = (
        bridgename => undef,
        @_);
}

sub add_veth_to_linux_bridge {
    my %args = (
        vethname => undef,
        bridgename => undef,
        ip=>undef,
        );

}

sub add_tap_to_linux_bridge {
    my %args = (
        tapname => undef,
        bridgename => undef);

}

sub start_dns_masq {
    my %args = (
        iface_to_listen_on=>undef,
        hw_addr_hash=>{},
    );

}

