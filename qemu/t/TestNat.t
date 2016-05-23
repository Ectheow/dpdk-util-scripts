use strict;
use warnings;
use v5.20;
use Carp;
use Net::DummyNode;
use Net::NetworkTopologyVisitor;
use Net::NetworkTopologyNode;
use Net::NatNode;
use Test::More;

my $json=<<EOF;
{
    "nodes":[{"handler":"dummy", "name":"dummy0"},
     {"handler":"dummy", "name":"dummy1"},
     {"handler":"nat",
        "input_iface":"dummy0",
        "output_iface":"dummy1" }]
}
EOF


my $visitor = Net::NetworkTopologyVisitor->new;
ok ($visitor, "Visitor is defined");

my $dummyHook = Net::DummyNode->new();
$visitor->add_hook(type=>"dummy", instance=>$dummyHook);
my $nat_hook = Net::NatNode->new();
$visitor->add_hook(type=>"nat", instance=>$nat_hook);

ok($visitor->parse_json(json=>\$json), "Parse JSON worked");
ok( (-d "/sys/class/net/dummy0"), "dummy0 exists");
ok( (-d "/sys/class/net/dummy1"), "dummy1 exists");

my $file = do {
    open (my $fh, "<", "/proc/sys/net/ipv4/ip_forward") or croak "can't open proc file";
    local $/=undef;
    <$fh>;
};

chomp $file;
ok($file eq "1", "ip forward turned on in proc: $file");

done_testing();
