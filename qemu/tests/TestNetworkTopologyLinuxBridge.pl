use strict;
use warnings;
use v5.20;
use Carp;
use NetworkTopologyVisitor;

my $bridge_json=<<EOF;
{
    "dummy":{"name":"dummy0"}
    "dummy":{"name":"dummy1"}
    "dummy":{"name":"dummy2"}
    "dummy":{"name":"dummy3"}
    "linux-bridge":{
        "name":"$bridgename",
        "interfaces":[
            "dummy0",
            "dummy1",
            "dummy2" ]
    }
}
EOF
