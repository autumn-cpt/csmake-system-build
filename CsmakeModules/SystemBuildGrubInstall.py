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
import os.path
import stat

class SystemBuildGrubInstall(CsmakeModule):
    """Purpose: Install grub on the given system
                system must be mounted.
       Library: csmake-system-build
       Phases:
           build, system_build
       Options:
           system - The SystemBuild system to make bootable
    """

    REQUIRED_OPTIONS = ['system']

    def _getEnvKey(self, system):
        return "__SystemBuild_%s__" % system

    def system_build(self, options):
        return self.build(options)

    def _sudo_change_file_perms(self, filepath, new_perms_mask):
        ''' Use sudo to change file permissions.  Returns old permissions
        mask.  We expect that the filepath is *inside* of a chrooted directory.
        Note that the new_perms_mask is a string.
        '''
        assert(str == type(new_perms_mask))
        old_stat = os.stat(filepath)
        old_perms_mask = oct(old_stat[stat.ST_MODE])[-3:]
        subprocess.check_call(["sudo", "chmod", new_perms_mask, filepath],
                                 stdout=self.log.out(),
                                 stderr=self.log.err())
        # If subprocess.check_call fails it will throw a CalledProcessError. We
        # choose to simply let that error propogate upwards.
        return old_perms_mask

    def _edit_default_grub(self, system_partition):
        ''' Edit grub default file. Find line starting with
            "GRUB_CMDLINE_LINUX" and append to it.
        '''
        try:
            grubpath = 'etc/default/grub'
            fpath = os.path.join(system_partition, grubpath)
            self.log.debug("About to change file perms on {0}".format(fpath))
            old_perms = self._sudo_change_file_perms(fpath, '0666')
            if old_perms is None:
                raise Exception("Could not change perms on {0}".format(fpath))

            self.log.debug("About to edit {0} to add serial TTY".format(fpath))
            key = "GRUB_CMDLINE_LINUX="
            lines = []
            with open (fpath, 'r+') as f:
                for line in f:
                    if line.startswith(key):
                        # Find the existing values between doublequotes. If there
                        # are no doublequotes oldstr will simply become an empty
                        # string.
                        q1 = line.find('"')
                        q2 = line.rfind('"')
                        oldstr = line[q1 + 1:q2]
                        # add new console settings to existing values
                        newstr = '"{0} console=tty0 console=ttyS0,38400n8"\n'.format(oldstr)
                        # line now has old and new values
                        line = key + newstr
                    lines.append(line)
                # entirely rewrite file with new lines
                f.seek(0)
                f.writelines(lines)

        except Exception:
            self.log.exception("Got an exception in _edit_default_grub()")
            # Do nothing - if we can't read or write the default grub file
            # the worst that will happen is Grub will install itself using an
            # unmodified default file.

        finally:
            if old_perms is not None:
                try:
                    self.log.debug("About to change file perms back to {0}".format(old_perms))
                    self._sudo_change_file_perms(fpath, old_perms)
                except Exception:
                    self.log.exception("Got an exception in _edit_default_grub() finally block")
                    # If we got an exception in this finally block there's something
                    # very wrong. Let's fail and let a human figure it out.
                    self.log.failed()
                    raise


    def build(self, options):
        # Find all mounted system partitions

        taggedEnvKey = self._getEnvKey(options['system'])
        if taggedEnvKey not in self.env.env:
            self.log.error("System '%s' undefined", options['system'])
            self.log.failed()
            return None
        systemEntry = self.env.env[taggedEnvKey]
        if 'filesystem' not in systemEntry:
            self.log.error("System '%s' has no filesystem", options['system'])
            self.log.failed()
            return None
        fsEntry = systemEntry['filesystem']
        if 'mountInstance' not in systemEntry:
            self.log.error("System '%s' is not mounted", options['system'])
            self.log.failed()
            return None
        mountInstance = systemEntry['mountInstance']
        systemPartition = None
        systemDevice = None
        if '/boot' in fsEntry:
            mountpt, device, fstype, fstabid = fsEntry['/boot']
            for name, value in systemEntry['disks'].iteritems():
                if device.startswith(value['device']):
                    if not value['real']:
                        self.log.error("/boot is not on a real disk (%s) - this is not supported", value['device'])
                        self.log.failed()
                        return None
                    systemDevice = value['device']
                    break
            if systemDevice is None:
                self.log.error("/boot is defined as its own filesystem on '%s', but no actual disk was found", device)
                self.log.failed()
                return None

        if '/' not in fsEntry:
            self.log.error("There is no defined root filesystem")
            self.log.failed()
            return None

        mountpt, device, fstype, fstabid = fsEntry['/']
        if systemDevice is None:
            for name, value in systemEntry['disks'].iteritems():
                if device.startswith(value['device']):
                    if not value['real']:
                        self.log.error("The filesystem for system '%s' does not have a real device to target for booting", options['system'])
                        self.log.failed()
                        return None
                    systemDevice = value['device']
        if systemDevice is None:
            self.log.error("The filesystem for system '%s' does not have a real device to target for booting", options['system'])
            self.log.failed()
            return None

        systemPartition = mountInstance._systemMountLocation()
        self.log.devdebug("systemPartition is: {0}".format(systemPartition))

        # Edit <systemPartition>/etc/default/grub to add a serial TTY console.
        self._edit_default_grub(systemPartition)

        # N.B.: 'update-grub' is simply a convenience wrapper around the command "grub-mkconfig -o /boot/grub/grub.cfg"
        result = subprocess.call(
            ["sudo", "chroot", systemPartition, 'update-grub'],
            stdout=self.log.out(),
            stderr=self.log.err())
        if result != 0:
            self.log.error("update-grub failed (%d)", result)
            self.log.failed()
            return None

        # TODO: Currently this only works for ms-dos partition tables
        #      Also, assumes only MBR grub install
        #      Change it to work with GPT and UEFI as well
        result = subprocess.call(
            ["sudo", "chroot", systemPartition,
                "grub-install", "-v", "--no-floppy", "--recheck",
                    "--modules", "biosdisk part_msdos",
                    systemDevice ],
            stdout=self.log.out(),
            stderr=self.log.err())
        if result != 0:
            self.log.error("grub-install failed (%d)", result)
            self.log.failed()
            return None
        self.log.passed()
        return True
