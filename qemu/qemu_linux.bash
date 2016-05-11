#!/bin/bash

sudo kvm \
    -boot order=cd \
    -cpu host \
    -m 2048 \
    -name 'hlinux qemu' \
    -cdrom hlinux-iso.iso \
    -drive file=hlinux.img \
    -net nic,model=virtio \
    -net bridge,br=br0

