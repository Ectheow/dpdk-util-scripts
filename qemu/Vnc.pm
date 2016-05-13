package Vnc;
use strict;
use warnings;
use v5.20;
use Carp;
use IPC::Cmd qw(can_run run_forked);
use ProcessTools;
my $VNC_CMD = "vncviewer";

sub create_vnc_command {
    my %args = (
        x_server=>undef,
        @_,
    );
    croak "Undefined vnc_port" if not defined $args{x_server};
    my $vnc = undef;
    if (can_run($VNC_CMD)) {
        $vnc = "$VNC_CMD localhost::590$args{x_server}";
        $vnc =~ tr/\n/ /;
    }
    return $vnc;
}

sub launch_vnc_at {
    my %args = (
         x_server=>undef,
         @_,
    );
    my $cmd = create_vnc_command(%args)
        or croak "Can't create a vnc command from your garbage";
    return ProcessTools::process_exec($cmd);
}
1;
