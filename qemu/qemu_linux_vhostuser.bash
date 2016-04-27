#!/bin/bash

sudo kvm \
    -boot order=cd \
    -cpu host \
    -vnc :5 \
    -m 4096 \
    -name 'hlinux qemu' \
    -cdrom hlinux-iso.iso \
    -drive file=hlinux.img \
    -chardev socket,id=char1,path=/var/run/openvswitch/vhost-user-1 \
    -netdev type=vhost-user,id=mynet1,chardev=char1,vhostforce \
    -device virtio-net-pci,mac=00:00:00:00:00:01,netdev=mynet1 \
    -object memory-backend-file,id=mem,size=4G,mem-path=/dev/hugepages,share=on \
    -numa node,memdev=mem -mem-prealloc \
    -netdev tap,id=mynet2 \
    -device virtio-net-pci,netdev=mynet2

