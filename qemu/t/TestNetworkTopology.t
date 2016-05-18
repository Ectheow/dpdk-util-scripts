use strict;
use warnings;
use v5.20;
use Carp;
use Net::NetworkTopologyVisitor;
use Net::NetworkTopologyNode;
use Net::NetworkInterface;
use Net::VethNode;
use Test::More;

my $veth_name = "myveth";
my $veth_json=<<EOF;
{
"veth":{
    "name":"$veth_name",
    "ips":["192.168.10.2/24", "192.168.10.3/24"]
}
}
EOF

my $visitor = Net::NetworkTopologyVisitor->new();
ok($visitor, "Visitor is not undefined");

my $vethHook = Net::VethNode->new();
ok($vethHook, "vethHOok is not null");
ok($visitor->add_hook(type=>"veth", instance=>$vethHook), "add a hook is OK");
ok($visitor->parse_json(json=>\$veth_json), "Parse JSOn returned 1");

ok(((-d "/sys/class/net/$veth_name". "0") and (-d "/sys/class/net/$veth_name". "1")),
    "Veth nodes both exist");
my $netif0 = Net::NetworkInterface->new(name=>$veth_name."0");
ok($netif0, "netif0 exists");
my $netif1 = Net::NetworkInterface->new(name=>$veth_name."1");
ok($netif1, "Netif1 exists");

is_deeply($netif0->get_ips(), ["192.168.10.2/24"], "IPs are correct");
is_deeply($netif1->get_ips(), ["192.168.10.3/24"], "IPs are correct");

done_testing();
