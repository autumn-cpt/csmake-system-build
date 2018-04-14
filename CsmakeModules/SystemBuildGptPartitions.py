# <copyright>
# (c) Copyright 2018 Cardinal Peak Technologies
# (c) Copyright 2017 Hewlett Packard Enterprise Development LP
#
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation, either version 3 of the License, or (at your
# option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
# Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
# </copyright>
from CsmakeModules.SystemBuildMsdosPartitions import SystemBuildMsdosPartitions
import subprocess

class SystemBuildGptPartitions(SystemBuildMsdosPartitions):
    """Purpose: Set up partitions on a disk for a system build.
           NOTE: Partitions will be top to bottom, no gaps
                 A special module would be required to enable
                 adding partitions to the bottom of the disk space
       Library: csmake-system-build
       Phases: build, system_build - create the file and definition
       Options:
           system - Name of the system to add partitions to
           disk-name - Name of the disk to partition
           part_<partition> - Definition of partition
               The fields for the entries are:
                   <order>, <size>, <type>[, <flags>]
                   order - position on the disk
                   size - Size of the partition in G or M
                          Sizes are suggestions with size being within
                          1% of the size of the disk and optimazations
                   type - number or hex number or guid (e.g., 0x84)
                          or a defined type (e.g., Linux)
                          defined types are (per parted):
                              ext2 - a linux partition
                              linux - a linux partition
                              linux-swap - linux swap partition
                              fat16 - an old windows partition
                              fat32 - a vfat windows partition
                              HFS - an HFS parition
                              NTFS - an NTFS partition

                   flags - (optional) If the partition is bootable,
                          add "boot" to the end, for example.
                          0 to n flags may be specified.
                          flags are based on parted's flags:
                          boot - bootable partition
                          root - the root file system partition
                          swap - a swap partition
                          hidden - a hidden parittion
                          raid - a raidable partition
                          lvm - an lvm partition
                          lba - use logical block addressing
                          legacy_boot - a legacy boot parition (non-UEFI)
                          palo - ???
       Environment:
           __SystemBuild_<system>__ is referenced - it is an error
              to not have the referenced system defined
              a 'disks' entry is expected to exist with th referenced disk
              i.e., SystemBuildDisk section defining the disk has already
                    been executed.
              This will update the entry with the partition table of the disk
              as 'partitions', which will be a dictionary with the partition
              name as the key from part_<name> of:
                 number - the parittion number
                 size - the size of the partition
                 device - the full device (current device)
                 fstab-id - the fstab-id to use, e.g. LABEL="blah"
       Requires: parted and sgdisk
    """

    REQUIRED_OPTIONS = ['system', 'disk-name']

    PART_TYPE = "gpt"
    PART_PRIMARY_PARTITIONS = 128
    PART_LOGICAL_EXTENDED_ALLOWED = False

    def _editPartitionWithSfdisk(self, device, number, partition):
        result = subprocess.call(
            ['sudo', 'gfdisk', '--typecode=%d:%s' % (number, partition[3]), device],
            stdout = self.log.out(),
            stderr = self.log.err() )
        if result != 0:
            self.log.warning("Did not successfully set the requested partition type")
