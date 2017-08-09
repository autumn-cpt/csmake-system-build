# <copyright>
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
from Csmake.CsmakeModule import CsmakeModule
import subprocess
import re

class SystemBuildMsdosPartitions(CsmakeModule):
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
                           (use '<ex>E' for an extended partition
                            msdos tables only allow 4 primary/extended
                            partitions)
                           (start with '<ex>:<logical>L' for a partition
                            within the extended partition
                           (the logical partition numbering for logical
                            partitions will start at 5 on the system regardless
                            of the numbers used for 'order')
                   size - Size of the partition in G or M
                          Sizes are suggestions with size being within
                          1% of the size of the disk and optimazations
                   type - number or hex number (e.g., 0x84)
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
       Requires: parted and sfdisk
    """

    REQUIRED_OPTIONS = ['system', 'disk-name']

    PART_FSTYPES = {
        'ext2' : 'ext2',
        'linux' : 'ext2',
        'fat16' : 'fat16',
        'fat32' : 'fat32',
        'HFS' : 'HFS',
        'NTFS' : 'NTFS',
        'linux-swap' : 'linux-swap',
        'reiserfs' : 'reiserfs',
        'ufs' : 'ufs' }

    def _getEnvKey(self, system):
        return "__SystemBuild_%s__" % system

    def _getRequestedPercentage(self, size):
        requestedSize = self.systemInstance._getSizeInBytes(size)
        result = int(round(requestedSize*100.0/self.disksize))
        if result == 0:
            result = 1
            self.log.warning("The requested partition was too small (%s), the partition has been rounded up to the next available size", size)
        return result

    #Structure of the partition is name, order, size, type, flag(boot)
    def _createNextPartition(
        self, device, number, parttype, partition, start, end):
        fstype='ext2'
        callsfdisk = False
        if partition[3] in self.PART_FSTYPES:
            fstype = self.PART_FSTYPES[partition[3]]
        else:
            callsfdisk = True
        subprocess.check_call(
            ['sudo', 'parted', '-s', '-a', 'optimal', device, '--',
              'mkpart', parttype, fstype, "%d%%" % start, "%d%%" % end],
            stdout=self.log.out(),
            stderr=self.log.err() )
        if len(partition) > 4:
            for flag in partition[4:]:
                subprocess.check_call(
                    ['sudo', 'parted', '-s', device, '--',
                     'set', "%d" % number, flag, 'on'],
                    stdout = self.log.out(),
                    stderr = self.log.err())
        if callsfdisk:
            result = subprocess.call(
                ['sudo', 'sfdisk', '--part-type', device, "%d" % number, partition[3]],
                stdout = self.log.out(),
                stderr = self.log.err() )
            if result != 0:
                self.log.warning("Did not successfully set the requested partition type")

    def _createPrimaryPartition(self, device, number, partition):
        requestedPercent = self._getRequestedPercentage(partition[2])
        start = self.startPercent
        end = start + requestedPercent
        if end > 100:
            self.log.warning("Primary partition was truncated, %d%% beyond the end of the disk", 100-end)
            end = 100
        self._createNextPartition(
            device, number, 'primary', partition, start, end)
        self.startPercent = end

    def _createExtendedPartition(self, device, number, partition):
        requestedPercent = self._getRequestedPercentage(partition[2])
        start = self.startPercent
        end = start + requestedPercent
        if end > 100:
            self.log.warning("Extended partition was truncated, %d%% beyond the end of the disk", 100-end)
            end = 100
        self._createNextPartition(
            device, number, 'extended', partition, start, end)
        self.extensionStart = start
        self.extensionEnd = end

    def _createLogicalPartition(self, device, number, partition):
        if self.extensionStart == -1:
            self.log.error("Creating a logical partition without an extended partition")
            raise SystemError("Logical partitions require extended partitions")
        requestedPercent = self._getRequestedPercentage(partition[2])
        start = self.extensionStart
        end = start + requestedPercent
        if end > self.extensionEnd:
            self.log.warning("Logical partition was truncated, %d%% beyond the extended partition", self.extensionEnd - end)
            end = self.extensionEnd
        self._createNextPartition(
            device, number, 'logical', partition, start, end)
        self.extensionStart = end

    def _createPartitionEntry(self, part, number, device, diskFstabId, partFstabId=None):
        if partFstabId is None:
            if '=' not in diskFstabId:
                partFstabId = "%sp%d" % (diskFstabId, number)
            #TODO: What if the disk has an identifier, but nothing for the
            #      partition - then what???
        self.partEntry[part[0]] = {
            'number' : number,
            'size' : part[2],
            'device' : "%sp%d" % (device, number),
            'fstab-id' : partFstabId }

    def system_build(self, options):
        return self.build(options)
    def build(self, options):
        system = options['system']
        diskname = options['disk-name']
        key = self._getEnvKey(system)
        if key not in self.env.env:
            self.log.error("System '%s' is not defined", system)
            self.log.failed()
            return None
        systemEntry = self.env.env[key]
        if 'disks' not in systemEntry or diskname not in systemEntry['disks']:
            self.log.error("Disk '%s' is not defined for system '%s'", diskname, system)
            self.log.failed()
            return None
        diskEntry = systemEntry['disks'][diskname]
        if 'partitions' in diskEntry:
            self.log.error("Parititions have already been defined for disk '%s'", diskname)
            self.log.failed()
            return None
        diskEntry['partitions'] = {}
        self.partEntry = diskEntry['partitions']
        partitions=[]
        subprocess.check_call(
            ['sudo', 'parted', '-s', diskEntry['device'], '--', 'mklabel', 'msdos'],
            stdout=self.log.out(),
            stderr=self.log.err())

        #Get the sizes ready for creating partitions
        self.systemInstance = systemEntry['system']
        #parted on 14.04 is stupid...starting at 0 causes it to make a 1M
        #  partition...so
        self.startPercent = 1
        self.disksize = diskEntry['size']
        self.extensionStart = -1
        self.extensionEnd= -1

        for key, value in options.iteritems():
            if key.startswith('part_'):
                name = key[5:]
                partition = [name]
                partition.extend(value.split(','))
                partition = [ x.strip() for x in partition if len(x.strip()) > 0 ]
                partitions.append( partition )
        self.log.devdebug("Processing partitions: %s", partitions)
        partitions.sort(key=lambda x: x[1])
        #NOTE: assuming and assigning part numbers based on p/e/l volume
        #      creation ordering in parted.
        #Consider that the partition number assumption could be checked
        #  by showing that the parition number did not exist, and then
        #  after creating the partition, it does exist.
        primary = 1
        extended = ""
        logical = 5
        for part in partitions:
            try:
                if part[1][-1] == 'L':
                    if len(part[1]) < 4 or part[1][1] != ':':
                        self.log.error("The format of 'part_%s' option is incorrect", part[0])
                        self.log.error("   got: %s", part[1])
                        self.log.error("   format required: <ex>:<part>L")
                        self.log.error("      e.g.: 2:5L  where 2 is an extended partition")
                        self.log.failed()
                        return None
                    self._createLogicalPartition(
                        diskEntry['device'],
                        logical,
                        part )
                    self._createPartitionEntry(
                        part,
                        logical,
                        diskEntry['device'],
                        diskEntry['fstab-id'])
                    logical += 1

                elif part[1][-1] == 'E':
                    if primary > 4:
                        self.log.error("msdos (MBR) partition tables may only have 4 primary and extended partitions")
                        self.log.error("   However, part_%s defines a 5th partition", part[0])
                        self.log.failed()
                        return None
                    if len(part[1]) < 2:
                        self.log.error("The format of 'part_%s' option is incorrect", part[0])
                        self.log.error("    got: %s", part[1])
                        self.log.error("    format required: <ex>E")
                        self.log.error("       e.g.: 3E")
                        self.log.failed()
                        return None
                    if self.extensionStart != -1:
                        self.log.error("The disk can only have one extended partition")
                        self.log.error("   part_%s specified a second extended partition", part[0] )
                        self.log.failed()
                        return None
                    self._createExtendedPartition(
                        diskEntry['device'],
                        primary,
                        part )
                    self._createPartitionEntry(
                        part,
                        primary,
                        diskEntry['device'],
                        diskEntry['fstab-id'])
                    extension = str(primary)
                    primary += 1

                else:
                    if primary > 4:
                        self.log.error("msdos (MBR) partition tables may only have 4 primary and extended sections")
                        self.log.error("   However, part_%s defines a 5th partition", part[0])
                        self.log.failed()
                        return None
                    self._createPrimaryPartition(
                        diskEntry['device'],
                        primary,
                        part )
                    self._createPartitionEntry(
                        part,
                        primary,
                        diskEntry['device'],
                        diskEntry['fstab-id'])
                    primary += 1
            except ValueError as v:
                self.log.exception('Partition "%s" creation failed', part)
                self.log.failed()
                return None
            except subprocess.CalledProcessError as cpe:
                self.log.exception('Partition "%s" shell call failed', part)
                self.log.failed()
                return None
        result = subprocess.call(
            ['sudo', 'partprobe', diskEntry['device']],
            stdout=self.log.out(),
            stderr=self.log.err())
        if result != 0:
            self.log.warning("Part probe failed")
        result = subprocess.call(
            ['sudo', 'udevadm', 'settle'],
            stdout=self.log.out(),
            stderr=self.log.err())
        if result != 0:
            self.log.warning("settle failed")

        self.log.passed()
        return self.partEntry
