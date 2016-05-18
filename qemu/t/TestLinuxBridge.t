use warnings;
use strict;
use v5.20;
use Dir::Self;
use File::Spec;
useNet::Net::LinuxBridge;
useNet::Net::NetworkInterface;
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
my $br =Net::Net::LinuxBridge->new(name=>"br-test") or croak "Can't create bridge";

ok ( (-d "/sys/class/net/$brname/"), "Bridge has been created in sysfs");
my @dummies = qw[
dummy0
dummy1
dummy2
];
foreach my $dummy (@dummies) {
    my $dummy_iface =Net::Net::NetworkInterface->new(name=>$dummy);
    croak "Can't create a dummy interface" if not (system("ip link add name $dummy type dummy") == 0);
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
done_testing;

END {
    foreach my $dummy (@dummies) {
        system("ip link del $dummy");
    }
}
