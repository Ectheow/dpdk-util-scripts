package Net::NatNode;
use strict;
use warnings;
use v5.20;
use Carp;
use Net::NetworkTopologyNode;
use parent 'Net::NetworkTopologyNode';

sub __create {
    my ($self, $config_hash) = @_;

    my ($input_iface, $output_iface) = ($config_hash->{input_iface},
                                        $config_hash->{output_iface});

    if (not defined $input_iface) {
        croak "Undefined input interface for NAT";
    }
    if (not defined $output_iface) {
        croak "Undefined output interface for NAT";
    }

    open my $proc_fh, ">", "/proc/sys/net/ipv4/ip_forward" or do {
        croak "IP forward initialization failed";
    };

    say $proc_fh "1";
    close $proc_fh;

    system("/sbin/iptables -t nat -A POSTROUTING -o $output_iface -j MASQUERADE") == 0 or do {
        croak "Can't setup POSTROUTING nat hook";
    };

    system("/sbin/iptables -A FORWARD -i $output_iface -o $input_iface -m state --state RELATED,ESTABLISHED -j ACCEPT") == 0 or do {
        croak "can't setup FORWARD state nat hook";
    };

    system("/sbin/iptables -A FORWARD -i $input_iface -o $output_iface -j ACCEPT") == 0 or do {
        croak "Can't do final FORWARD accept hook";
    };

}

sub DESTROY {
    system("/sbin/iptables -F");
    system("/sbin/iptables -t nat -F");
    open my $proc_fh, ">", "/proc/sys/net/ipv4/ip_forward" or do {
        carp "Can't open proc fs";
        return;
    };
    say $proc_fh "0";
};

1;
