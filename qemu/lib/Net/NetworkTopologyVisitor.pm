package Net::NetworkTopologyVisitor;
use strict;
use warnings;
use JSON;
use v5.20;
use Carp;

sub new
{
    my $class = shift;
    my $self = {hooks=>{}};

    return bless $self, $class;    
}

sub add_hook
{
    my $self = shift;
    my %args = (
        type => undef,
        instance => undef,
        @_,
    );

    croak "I need a NetworkTopologyNode" if not  $args{instance}->isa("Net::NetworkTopologyNode");

    $self->{hooks}{$args{type}} = $args{instance};
    return 1;
}


sub parse_json
{
    my $self = shift;
    my %args = (
        json=>undef,
        @_,
    );

    do {
        carp "Given null json";
        return undef;
    } if (not defined $args{json});

    my $fh = IO::File->new($args{json}, "<") or croak "Can't open JSON";
    my $hash =  decode_json do {
        local $/=undef;
        <$fh>;
    };

    foreach my $node (@{$hash->{nodes}}) {
        my $handler = $node->{handler};
        if (not exists $self->{hooks}{$handler}) {
            carp "no handler for type $node";
            next;
        }
        $self->{hooks}{$handler}->create(config=>$node); 
    }

    return 1;
}

1;
