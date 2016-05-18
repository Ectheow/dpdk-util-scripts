package Net::NetworkUtils;
use warnings;
use strict;
use Getopt::Long;

sub test_pci_parse {
    
    sub test_against($$) {
        my ($hash, $string) = @_;

        my $rethash = parse_pci_string $string;

        die "Bad PCI domain " . $hash->{domain} unless $hash->{domain} eq $rethash->{domain};
        die "Bad PCI bus" unless $hash->{bus} eq $rethash->{bus};
        die "Bad PCI slot" unless $hash->{slot} eq $rethash->{slot};
        die "Bad PCI function" unless $hash->{function} eq $rethash->{function};
    }


    test_against({domain=>"0000", bus=>"00", slot=>"08", function=>"0"}, "0000:00:08.0");
    test_against({slot=>"08"}, "08");
    test_against({slot=>"08", function=>"01"}, "08.01");


    die "Loose comparision didn't work" unless loose_compare_pci_strings("08", "0000:00:08.0");
    die "Loose comparison didn't work" if loose_compare_pci_strings("07", "0000:00:08.0");
}

# parse_pci_string: string -> hash
# parses a PCI string, returning a hash of the components
# domain, bus, slot, function, if defined.
sub parse_pci_string($) {
    # algorithm for parsing string:
    # Count the number of colons.
    # There could be two, one or none.
    # If two: Pop off from the string [0, colon). This is domain. Remove colon.
    # If one: pop off from the string [0, colon). This is bus. Remove colon.
    # If none: 
    # Count the number of dots. There could be one or none.
    # If one: pop off from [0 to dot). This is slot. Remove dot.
    #         If there is any string left, pop it off as function.
    # If none: 
    #         Pop off remainder of string, this is slot.
    
    # sub iter_string: hash, string -> nothing
    # Takes a hash containing the domain, bus, slot, func 
    # values, and a string, and does one iteration of parsing.
    my ($string) = @_;
    my $hash = {};
    my $idx_count = ($string =~ tr/://);
    my $hashkey;

    while ( (my $idx_count = ($string =~ tr/://)) != 0) {
        if (not ($idx_count == 2 or $idx_count ==1)) {
            die "Bad PCI string: $string";
        }
        if ($idx_count == 2) {
            $hashkey = "domain";
        } elsif ($idx_count == 1) {
            $hashkey = "bus";
        } 
        $hash->{$hashkey} = substr($string, 0, index($string, ':')); 
        $string = substr($string, index($string, ':') +1);
    }

    if ($string !~ /^[\d]+(\.[\d]+)?$/) {
        die "Bad PCI string: $string";
    }

    $idx_count = ($string =~ tr/.//);

    if($idx_count == 1) {
        $hash->{slot} = substr($string, 0, index($string, '.'));
        $hash->{function} = substr($string, index($string, '.')+1);
        return $hash;
    }

    if (not ($string =~ /^\d+/)) {
        die "Bad PCI string: $string";
    }

    $hash->{slot} = $string;
    return $hash;
}


# perform a loose comparison of PCI strings.
# Basically, if on one side a key is missing we count it as
# a match.
sub loose_compare_pci_strings($$) {
    my ($string1, $string2) = @_;
    my ($hash1, $hash2) = (parse_pci_string($string1), parse_pci_string($string2));
   
    while(my ($key, $value) = each(%{$hash1})) {
        next if(exists $hash2->{$key} and $hash2->{$key} eq $value);
        return 0;
    }

    return 1;
}


sub make_iface_parms
{
    my $hash = {};
    my $valid_keys = [ "pci", "addr", "driver", "timeout", "dryrun" ];
    while( (my $parm_name = shift) ) {
        if (not grep({$_ eq $parm_name} @{$valid_keys})) {
            die "Invalid parm name: $parm_name";
        }

        my $parm_value = shift;
        next if not $parm_value;
        $hash->{$parm_name} = $parm_value;
    }
    die "I _NEED_ an addr, betch" if not exists $hash->{addr};
    die "I _NEED_ a driver" if not exists $hash->{driver};
    return $hash;
}

sub ifacep_driver_matches($$) {
    my ($hash, $str) = @_;

    if (not exists($hash->{driver})) {
        return 1;
    }
    return $hash->{driver} eq $str;
}

sub ifacep_pci_matches($$) {
    my ($hash, $str) = @_;

    if (not exists($hash->{pci})) {
        return 1;
    }

    return loose_compare_pci_strings($hash->{pci}, $str);
}

sub ifacep_addr_matches($$) {
    my ($hash, $str) = @_;
    
    return 0 if not exists($hash->{addr}) or not $str;
    return address_compare_noroute($hash->{addr}, $str);
}

sub ifacep_get_timeout($) {
    return 1 if (not(exists($_[0]->{timeout})));
    return $_[0]->{timeout};
}

sub ifacep_dryrun($) {
    return 1 if exists($_[0]->{dryrun});
    return 0;
}

sub ifacep_get_addr($) {
    return $_[0]->{addr};
}
#
# iface_set_up: iface string. Ups interface.
sub iface_set_up {
    my $iface = shift;
    system("ip link set dev $iface up");
}

# iface_set_down: Iface string. Downs interface.
sub iface_set_down {
    my $iface = shift;
    system("ip link set dev $iface down");
}


# does_iface_match : iface string, driver name, bus string -> true or false
# Given a interface string, a driver name, and a PCI bus string,
# return true or false if the interface specified has these attributes. 
sub iface_matches($$) {
    my ($iface_name, $ifaceparms) = @_;
    my $drv_str = "";
    my $bus_str = "";
    open(my $ethtool, "-|", "ethtool -i $iface_name") or die "Can't open ethtool -i for $iface_name";
    return if eof($ethtool);
    $drv_str = (split /:\s/, <$ethtool>)[1];
    chomp $drv_str;
    <$ethtool>;
    <$ethtool>;
    $bus_str = (split /:\s/, <$ethtool>)[1];
    chomp $bus_str;

    if(ifacep_pci_matches($ifaceparms, $bus_str) 
       and ifacep_driver_matches($ifaceparms, $drv_str)) {
        return 1;
    }

    return 0;
}

# iface_haslink: iface string -> true or false
# Determines if the interface has a link.
sub iface_haslink {
    my ($iface_name, $timeout) = @_;
    iface_set_up $iface_name;
    sleep $timeout;
    open(my $ethtool, "-|", "ethtool $iface_name") 
        or die "Can't open ethtool for $iface_name";
    while(my $line = <$ethtool>) {
        next if $line !~ /Link detected/;
        if ($line =~ /no/) {
            iface_set_down $iface_name;
            return 0;
        } else {
            return 1;
        }
    }  
}

sub iface_get_ip {
    my $iface_name = shift;
    open(my $ip_addr, "-|", "ip --oneline address show dev $iface_name") 
        or die "Can't call IP addr\n";
    return if eof($ip_addr);
    if(<$ip_addr> =~ /\d+:\s+[\w\d\-]+\s*inet\s+([\d\.\/]+)/) {
        return $1;
    } else {
        return undef;
    }
}
sub is_valid_ip($) {
    my ($ip) = @_;
    return $ip =~ /^(?:\d\d\d\.){4}(?:\/\d+)$/;
}

sub is_valid_mac($) {
    my $mac = shift;
    return $mac =~ /^(?:\d\d:?){6}$/;
}
sub iface_set_ip {
    my ($iface, $address) = @_;
    return (system("ip address add $address dev $iface") == 0);
}

sub iface_list {
    my $ifaces = [];
    open(my $handle, "-|", "ip --oneline link") or die "Can't call IP link\n";
    while(my $line = <$handle>) {
        $line =~ /^\s*([\d]+):\s+([\w\d\-_]+)(@[\w\d\-_]+)?:\s*<[\w\-_,]+>.*$/;
        my ($iface_num, $iface_name) = ($1, $2);
        push @{$ifaces}, $iface_name;
        if(not $iface_name) {
            die "Something is wrong with my string parsing! Couldn't find iface\n";
        }
    }
    return $ifaces;
}
# iterate_iface: function -> nothing
# Iteretes all ifaces and calles function on them, passing
# the iface name.

sub iterate_ifaces($) {
    my $function = shift;
    foreach my $iface (@{iface_list()}) {
        $function->($iface);
    }
}

sub address_strip_cidr {
    my ($addr) = @_;

    return $addr =~ s/\/.*$//rg;
}
# addresses_compare_noroute: address, address -> true or false
# Compares addresses without the subnet postfix.
sub address_compare_noroute($$) {
    my ($addr1, $addr2) = @_;
    my $strip_route = sub {
        my $arg = shift;
        if((my $idx = index($arg, "/")) > 0) {
            return substr($arg, 0, $idx);
        } else {
            return $arg;
        }
    };
     
    return ($strip_route->($addr1) eq $strip_route->($addr2));

}
# find_iface: driver, PCI bus, address -> true or false
# iterates all interfaces, and finds one that has the same
# driver and PCI bus and also has a link. Assign an IP 
# to this interface, and set it up. Remove all IPs that are
# the same as the one we're given. Returns true if all
# these things happen, false if not.
sub find_iface($) {
    my ($find_parms) = @_;
    my $isdone = 0;

    my $parse_iface = sub {

        my $iface = shift;
        my $addr = iface_get_ip($iface);

        print "iterating iface: $iface\n";
        if(ifacep_addr_matches($find_parms, $addr) and (not ifacep_dryrun($find_parms))) {
            #delete an IP that's the same as the one we're trying to find.
            system("ip address del $addr dev $iface");
            iface_set_down($iface);
        } elsif(ifacep_addr_matches($find_parms, $addr)) {
            print "Found an inteface with a matching addr on $iface but dryrun is set\n";
        }

        return if $isdone;

        if (iface_haslink($iface, ifacep_get_timeout($find_parms)) and iface_matches($iface, $find_parms)) {
            if (not ifacep_dryrun($find_parms)) {
                iface_set_ip($iface, ifacep_get_addr($find_parms)) 
                    or die "Can't add IP address ". ifacep_get_addr($find_parms) . " to $iface";
                iface_set_up($iface);
                system("ip neigh flush all");
            } else {
                print "Found interface $iface but dryrun is set\n";
            }
            $isdone = 1;
        }
    };

    iterate_ifaces($parse_iface);

    return $isdone;
}


1;
