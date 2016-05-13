package ProcessTools;
use POSIX ":sys_wait_h";
use IPC::Cmd qw(can_run run_forked);
use strict;
use warnings;
use v5.20;
use Carp;
use IPC::Open3;

our %Pids = ();

sub child_exited {
    my $pid=0;
    my @deceased = ();
    do {
        $pid = waitpid(-1, WNOHANG);
        push @deceased, $pid;
    } while $pid > 0; 

    foreach $pid (@deceased) {
        next if $pid <= 0;
        say "Child: $pid cmdline: $Pids{$pid} exited.";
        delete $Pids{$pid};
    }
}

BEGIN {
    $SIG{CHLD} = \&child_exited;
}


sub process_exec {
    my $cmdline = shift;
    my ($write, $read, $err);
    my $pid = open3(\*STDIN, ">&STDOUT", ">&STDERR", $cmdline) or do {
        die "Couldn't fork for child\n";
    };

    say "Forked child process $cmdline ($pid)";
    $Pids{$pid} = $cmdline;
    return 1;
}


sub loop_waitpid {
    for (; ; ) {
        sleep 1;
        if (scalar keys %Pids == 0) {
            say "All children exited\n";
            exit 0;
        }
    }

}
1;
