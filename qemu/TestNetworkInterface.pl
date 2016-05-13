use warnings;
use strict;
use v5.20;
use Carp;
use NetworkInterface;
use Test::Simple;

my @veth_names = qw(myveth0 myveth1);
my @ips = qw(10.0.1.2/24 10.1.1.3/23);
sub start {
    system("ip link add name $veth_names[0] type veth peer name $veth_names[1]") == 0 or do {
        croak "Can't add an ip link";
    };
}

start();
my $netif0 = NetworkInterface->new(name=>$veth_names[0]);
my $netif1 = NetworkInterface->new(name=>$veth_names[1]);

foreach my $ip (@ips) {
    $netif0->add_ip($ip);
}
print `ip addr`;
ok($netif0->get_ips() ~~ @ips, "Add ips OK");

$netif0->set_linkstate($NetworkInterface::LINK_UP);
ok($netif0->get_linkstate() == $NetworkInterface::LINK_UP, "Check linkstate after upping");

foreach my $ip (@ips) {
    ok(system("ping -w 1 -c 3 $ip") == 0, "Can ping IP addr");
}

$netif0->set_linkstate($NetworkInterface::LINK_DOWN);
ok($netif0->get_linkstate() == $NetworkInterface::LINK_DOWN, "Check linkstate after downing");

done_testing();
END {
    system("ip link del $veth_names[0]") == 0 or do {
        croak "Can't delete ip link for $veth_names[0]";
    };
}
