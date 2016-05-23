package Net::NetworkTopologyNode;
use strict;
use warnings;
use v5.20;
use Carp;

sub new {
    my $class = shift;

    return bless {}, $class;
}

sub create {
    my $self = shift;

    my %args = (
        config=> undef,
        @_,
    );

    croak "Undefined configuration" if not defined $args{config};

    return $self->__create($args{config});

}

sub __create {
    croak "Not implemented __create";
}

1;
