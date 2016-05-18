package Net::NetworkInterface;
use NetworkUtils qw(address_comare_noroute);
use strict;
use warnings;
use JSON;
use v5.20;
use Data::Dumper;
use Carp;
require Exporter;
use constant {
    IFF_UP => 0x1,
    IFF_BROADCAST => 0x2,
    IFF_DEBUG => 0x4,
    IFF_LOOPBACK => 0x8,
    IFF_POINTOPOINT => 0x10,
    IFF_NOTRAILERS => 0x20,	
    IFF_RUNNING => 0x40,		
    IFF_NOARP => 0x80,		
    IFF_PROMISC => 0x100,	
    IFF_ALLMULTI => 0x200,	
    IFF_MASTER => 0x400,		
    IFF_SLAVE => 0x800,		
    IFF_MULTICAST => 0x1000,	
    IFF_PORTSEL => 0x2000,	
    IFF_AUTOMEDIA => 0x4000,	
    IFF_DYNAMIC => 0x8000,
};

our @ISA=qw(Exporter);
our @EXPORT = qw(
IFF_UP
IFF_BROADCAST
IFF_LOOPBACK
IFF_NOARP
IFF_MASTER
IFF_PROMISC
);

my $LINK_POINT_TO_POINT="POINT-TO-POINT";

sub new {
    my $class = shift;
    my %args =(
        name=>undef,
        @_,
    );

    my $data = {iface_name=>$args{name}};

    if (not (-d "/sys/class/net/$args{name}/")) {
        carp "Interface doesn't exist";
        return undef;
    }

    return bless $data, $class;
}

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
    return $_[0]->{iface_name};
}

sub get_iface_name($) {
    my $self = shift;
    return $self->{iface_name};
}
# add_ip: self, string: add a new IP address to interface
sub add_ip($$) {
    my ($self, $ip) = @_;

    system("ip addr add $ip dev $self->{iface_name}") == 0 or do {
        croak "Can't add IP address $ip to $self->{iface_name}";
    };
    return 1;
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
        my @found_ips = grep( (NetworkUtils::address_compare_noroute($ip, $_)), @{$extant_ips});
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

sub up {
    my $self = shift;

    my $flags = $self->get_linkstate;

    if ($flags & IFF_UP) {
        return 1;
    } else {
        $self->set_linkstate($flags | IFF_UP);
        return 1; 
    }

}

sub down {
    my $self = shift;

    my $flags = $self->get_linkstate;

    if (!($flags & IFF_UP)) {
        return 1;
    } else {
        $self->set_linkstate($flags ^ IFF_UP);
        return 1;
    }
}
sub set_linkstate($$) {
    my ($self, $flags_to_set) = @_;
    open FLAGS, ">", "/sys/class/net/$self->{iface_name}/flags" or croak "Can't open flags for writing";
    #printf "0x%x\n", $flags_to_set;
    printf FLAGS "0x%x\n", $flags_to_set; 
    close FLAGS;
    return $self->get_linkstate;
}

sub get_linkstate {
    my ($self) = @_;
    my $flags = do {
        local $/=undef;
        open my $flags_file, "<", "/sys/class/net/". $self->{iface_name}. "/flags";
        <$flags_file>;
    };
    chomp $flags;
    return hex $flags;
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
    if (not NetworkUtils::is_valid_mac($mac)) {
        carp "You gave me a bad mac!";
        return undef;
    }
    if(system("ip link set dev $self->{iface_name} address $mac") != 0) {return undef};
    return 1;
}


1;
