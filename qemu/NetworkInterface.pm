package Testing::NetworkInterface;
use Testing::NetworkUtils qw(address_comare_noroute);
use strict;
use warnings;
use Moose;
use JSON;
use v5.20;
use Data::Dumper;
use Carp;

our $LINK_DOWN = 0;
our $LINK_UP = 0x01;
our $LINK_NO_CARRIER = 0x02;
our $LINK_POINT_TO_POINT = 0x04;

sub set_iface_name($$) {
    my ($self, $iface_name) = @_;
    if (system("ip --oneline link show dev $iface_name >/dev/null") != 0) {
        carp "Bad link name: $iface_name";
        return undef;
    }

    $self->{iface_name} = $iface_name;
    return $self->{iface_name};
}

sub name($) {
    my $self = shift;
    return $self->{iface_name};
}

sub get_iface_name($) {
    my $self = shift;
    return $self->{iface_name};
}
# add_ip: self, string: add a new IP address to interface
sub add_ip($$) {
    die "Not implemented";
}

# get_ips: self: return a list of IPs on interface
sub get_ips($) {
    my $self = shift;
    my $addrs = [];
    my $iface_name = qr($self->{iface_name});

    open(my $fh, "-|", "ip --oneline address show dev $self->{iface_name}") 
        or do { 
            carp "Couldn't do an ip address show $!"; 
            return -1
        };

    while(my $line = <$fh>) {
        if ($line =~ /^\d+:\s+$iface_name\s+inet\s([\d\.\/]+).*$/) {
            push @{$addrs}, ($1);
        }
    }

    return $addrs;
}

# clear_ips: self, list: clear all IPs matching the ones
# in the list from the interface.
sub clear_ips($$) {
    my ($self, $ips) = @_;
    my $extant_ips = $self->get_ips();
    my $count = 0;
    foreach my $ip (@{$ips}) {
        my @found_ips = grep( (Testing::NetworkUtils::address_compare_noroute($ip, $_)), @{$extant_ips});
        if(not scalar @found_ips) {
            carp "You gave me an IP that didn't exist for $self->{iface_name}: $ip";
            next;
        }
        my $found_ip = shift @found_ips;
        system("ip address del $found_ip dev $self->{iface_name}");
        $count += 1;
    }
    return $count;
}

sub set_linkstate($$) {
    my ($self, $linkstate) = @_;
    my $ret;
    if ($linkstate == $LINK_UP) {
        if (system("ip link set up dev $self->{iface_name}") != 0) { 
            carp "Couldn't do an ip link set up on $self->{iface_name}";
        }
    } elsif($linkstate == $LINK_DOWN) {
        if (system("ip link set down dev $self->{iface_name}") != 0) { 
            carp "Couldn't do an ip link set down on $self->{iface_name}";
        }
    } else {
        carp "You're trying to make me set a bogus link state: $linkstate";
    }
    return $self->get_linkstate;
}

sub get_linkstate {
    my ($self) = @_;
    my $line = `ip --oneline link show dev $self->{iface_name}`;
    my $flags=$LINK_DOWN;
    if ($line =~ $self->_make_link_regex) {
        foreach my $flag (split ",", $1) {
            if ($flag eq "UP") {
                $flags |= $LINK_UP;
            } elsif($flag eq "NO-CARRIER") {
                $flags |= $LINK_NO_CARRIER;
            } elsif($flag eq "POINTTOPOINT") {
                $flags |= $LINK_POINT_TO_POINT;
            }
        }
    } else {
        carp "Something is wrong with the line regex: $line";
    }
    return $flags;
}

sub _make_link_regex($) {
    my ($self) = @_;
    my $iface_name = quotemeta($self->{iface_name});
    return qr(^\d+:\s+$iface_name:\s+
                <([\w,\-_]+)>
                \s*mtu\s*([\d]+).*
                link\/(?:ether|local|loopback|none)\s*
                (?:
                   ((?:[a-fA-F\d][a-fA-F\d]:?){6})\s*
                   brd\s*((?:[a-fA-F\d][a-fA-F\d]:?){6})
                )?)x;
}

sub get_mac($) {
    my $self = shift;

    if ($self->get_linkstate() & $LINK_POINT_TO_POINT) {
        return undef;
    } 
    my $line = `ip --oneline link show dev $self->{iface_name}`;

    if($line =~ $self->_make_link_regex) {
        return $3;
    } else {
        carp "ip link didn't match. line: $line";
        return undef;
    }
}

sub set_mac {
    my ($self, $mac) = @_;
    if (not Testing::NetworkUtils::is_valid_mac($mac)) {
        carp "You gave me a bad mac!";
        return undef;
    }
    if(system("ip link set dev $self->{iface_name} address $mac") != 0) {return undef};
    return 1;
}



no Moose;
__PACKAGE__->meta->make_immutable;
1;
