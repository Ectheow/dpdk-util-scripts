use warnings;
use strict;
use v5.20;
use Net::LinuxBridge;
use Net::NetworkInterface;
use Net::NetworkUtils;
use Test::More;
use Carp;

sub get_names_in_bridge {
    my $brname = shift;

    my $ifaces = [];
    opendir(DIR, "/sys/class/net/$brname/brif/") or croak "Can't open dir for $brname";

    while((my $dirent = readdir DIR)) {
        push @{$ifaces}, $dirent if not $dirent =~ /^\..*/;
    }

    return $ifaces;
}
my $brname = "br-test";
my $br = Net::LinuxBridge->new(name=>"br-test") or croak "Can't create bridge";

ok ( (-d "/sys/class/net/$brname/"), "Bridge has been created in sysfs");
my @dummies = qw[
dummy0
dummy1
dummy2
];
foreach my $dummy (@dummies) {
    croak "Can't create a dummy interface" if not (system("ip link add name $dummy type dummy") == 0);
    my $dummy_iface = Net::NetworkInterface->new(name=>$dummy);
    ok($dummy_iface, "Dummy iface exists");
    ok ($br->add_interface(interface=>$dummy_iface), "Bridge can add interface");
}
ok ($br->name eq $brname, "bridgename is correct");

is_deeply ([(map  { $_->name(); } @{$br->interface_list})] , \@dummies, "Bridge has correct interface list");

foreach my $dummy (@dummies) {
    ok($br->del_interface($dummy) == 1, "del interface succeeded");
}

is_deeply ( [map { $_->name; } @{$br->interface_list}], [], "Bridge interface list is empty");
is_deeply ( get_names_in_bridge($brname), [], "sysfs bridge list is empty");

system("brctl show $brname");

END {
    foreach my $dummy (@dummies) {
        system("ip link del $dummy");
    }
    done_testing();
}
