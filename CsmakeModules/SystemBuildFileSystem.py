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

class SystemBuildFileSystem(CsmakeModule):
    """Purpose: Set up the filesystem for the given system
       Library: csmake-system-build
       Phases: build, system_build - create the file and definition
       Options:
           system - Name of the system to add the disk to
           <mount point> - The mount point to create, e.g. /boot or /root
                 a '/' mount point is required
                 Each mount point requires:
                    a disk, partition or logical vol using the names provided
                       by the appropriate SystemBuild section
                    a filesystem, e.g., ext2, ext4, btrfs
                       This will be the -t parameter to mkfs.
       Example:
           [SystemBuildFileSystem@myfilesystem]
           system = mysystem
           / = mylvm_lv, btrfs
           /boot = my_disk.my_boot_partition, ext2
           /home = mylvm_home, ext4

       Environment:
           __SystemBuild_<system>__ is referenced - it is an error
              to not have the referenced system defined
              'disks' and their 'partitions' will be referenced from here.
              A 'filesystem' entry is added to the system entry.
              The filesystem's structure is
                 [ ( '<mountpoint>', '<device>', '<type>') ... ]
    """

    REQUIRED_OPTIONS = ['system', '/']

    def _getEnvKey(self, system):
        return "__SystemBuild_%s__" % system

    def system_build(self, options):
        return self.build(options)
    def build(self, options):
        system = options['system']
        key = self._getEnvKey(system)
        if key not in self.env.env:
            self.log.error("System '%s' is not defined", system)
            self.log.failed()
            return None
        systemEntry = self.env.env[key]
        if 'filesystem' in systemEntry:
            self.log.error("System '%s' already has a filesystem defined", system)
            self.log.failed()
            return None
        fsEntry = {}
        systemEntry['filesystem'] = fsEntry
        mountpts = [ x for x in options.keys() if x[0] == '/']
        mountpts.sort(key=lambda x: len(x.split('/')))
        for mountpt in mountpts:
            try:
                csmakedevice, fstype = options[mountpt].split(',',1)
            except ValueError as e:
                self.log.error(
                    "Filesystem spec was invalid (%s): '%s=%s'",
                    str(e),
                    mountpt,
                    options[mountpt])
                self.log.failed()
                return None

            csmakedevice = csmakedevice.strip()
            diskname = None
            partname = None
            if '.' in csmakedevice:
                diskname, partname = csmakedevice.split('.', 1)
            else:
                diskname = csmakedevice
            fstype = fstype.strip()
            if diskname not in systemEntry['disks']:
                self.log.error(
                    "Device '%s' for mount point '%s' undefined",
                    diskname,
                    mountpt )
                self.log.failed()
                return None
            diskEntry = systemEntry['disks'][diskname]
            device = diskEntry['device']
            fslabel = diskname
            fstabTarget = diskEntry
            if partname is not None:
                partEntry = diskEntry['partitions']
                if partname not in partEntry:
                    self.log.error(
                        "Partition '%s' for disk '%s' undefined",
                        partname,
                        diskname )
                    self.log.failed()
                    return None
                device = partEntry[partname]['device']
                fslabel = partname
                fstabTarget = partEntry[partname]
            subprocess.check_call(
                ['sudo', 'mkfs', '-t', fstype, device],
                stdout = self.log.out(),
                stderr = self.log.err() )

            #Only try labeling if we haven't already provided an fstab id
            #TODO: Consider attempting to get the UUID
            #TODO: Add fstab parms
            #TODO: Add swap...
            if '=' not in fstabTarget['fstab-id']:
                labeler = "_labelFileSystem_%s" % fstype
                if hasattr(self, labeler):
                    try:
                        if getattr(self, labeler)(fslabel, device):
                            fstabTarget['fstab-id'] = "LABEL=%s" % fslabel
                        else:
                            self.log.warning("Failed to label filesystem - the booted image may not be able to find: %s", mountpt)
                    except:
                        self.log.exception("Failed to label filesystem - the booted image may not be able to find: %s", mountpt)
            fsEntry[mountpt] = (mountpt, device, fstype, fstabTarget['fstab-id'])
        subprocess.call(['sync'])
        self.log.passed()
        return fsEntry

    #To add more supported file systems, subclass and add more _labelFileSystem
    def _labelFileSystem_ext2(self, fslabel, device):
        return self._labelFileSystem_ext(fslabel, device)
    def _labelFileSystem_ext3(self, fslabel, device):
        return self._labelFileSystem_ext(fslabel, device)
    def _labelFileSystem_ext4(self, fslabel, device):
        return self._labelFileSystem_ext(fslabel, device)

    def _labelFileSystem_ext(self, fslabel, device):
        subprocess.check_call(
            ['sudo', 'e2label', device, fslabel],
            stdout=self.log.out(),
            stderr=self.log.err() )
        return True

    def _labelFileSystem_btrfs(self, fslabel, device):
        subprocess.check_call(
            ['sudo', 'btrfs', 'filesystem', 'label', device, fslabel],
            stdout=self.log.out(),
            stderr=self.log.err() )
        return True

    def _labelFileSystem_vfat(self, fslabel, device):
        subprocess.check_call(
            ['sudo', 'mlabel', '-csn', '-i', device, "::%s" % fslabel],
            stdout=self.log.out(),
            stderr=self.log.err() )
        return True
    def _labelFileSystem_fat(self, fslabel, device):
        return self._labelFileSystem_vfat(fslabel, device)

    def _labelFileSystem_NTFS(self, fslabel, device):
        subprocess.check_call(
            ['sudo', 'ntfslabel', device, fslabel],
            stdout=self.log.out(),
            stderr=self.log.err())
        return True

    def _labelFileSystem_jfs(self, fslabel, device):
        subprocess.check_call(
            ['sudo', 'jfs_tune', '-L', fslabel, device],
            stdout=self.log.out(),
            stderr=self.log.err())
        return True

    def _labelFileSystem_xfs(self, fslabel, device):
        subprocess.check_call(
            ['sudo', 'xfs_admin', '-L', fslabel, device],
            stdout=self.log.out(),
            stderr=self.log.err())
        return True
