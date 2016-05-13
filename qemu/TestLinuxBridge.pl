use warnings;
use strict;
use v5.20;
use LinuxBridge;
use Test::More;
use Carp;

my $brname = "br-test";
my $br = LinuxBridge->new(name=>"br-test") or croak "Can't create bridge";

ok ( (-d "/sys/class/net/$brname/"), "Bridge has been created in sysfs");
my @dummies = qw[
dummy0
dummy1
dummy2
];
foreach my $dummy (@dummies) {
    my $dummy_iface = NetworkInterface->new(name=>$dummy);
    croak "Can't create a dummy interface" if not (system("ip link add name $dummy type dummy") == 0);
    ok ($br->add_interface(interface=>$dummy_iface), "Bridge can add interface");
}

is_deeply ([(map  { $_->name(); } @{$br->interface_list})] , \@dummies, "Bridge has correct interface list");

done_testing;

END {
    foreach my $dummy (@dummies) {
        system("ip link del $dummy");
    }
}
