use warnings;
use strict;

while(<>) {
    s/([\s*])Network/${1}Net::Network/g;
    s/([\s*])LinuxBridge/${1}Net::LinuxBridge/g;
    print;
}
