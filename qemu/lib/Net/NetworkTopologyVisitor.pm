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

    foreach my $key (keys %{$hash}) {
       do {
           carp "no handler for type $key";
           next; 
       } if (not exists $self->{hooks}{$key});
    
       $self->{hooks}{$key}->create(config=>$hash->{$key}); 
    }
    return 1;
}

1;
