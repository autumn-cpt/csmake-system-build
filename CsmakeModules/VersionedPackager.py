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
from CsmakeModules.Packager import Packager
import os.path
import os

class VersionedPackager(Packager):
    """Purpose: Create a "tarball" archive with the given version format string
       Library: csmake-system-build
       Phases: package - Will build the package
               clean, package_clean - will delete the package
       Options:
           maps - installmap based sections that define how files should
                  be mapped into the package.
           result - Directory to put the results
                    Make this its own subdirectory under %(RESULTS)s
                    or clean will wack the %(RESULTS)s directory.
           format - (OPTIONAL) bzip2 or gzip
           extension - (OPTIONAL) specify a special extension
                    Default is either tar.gz or tar.bz2
           package-version - (OPTIONAL) When unspecified, the package version
                              is left off (unlike Packager which will drop
                              a trailing dash.
           version - (OPTIONAL) Specifies a version format string
                     Defaults back to Packager's (which is just default)
           no-root-dir - (OPTIONAL) When 'True' avoid putting the archive
                                  in a top level directory
                     Default is 'False', and the top level directory
                     is the name of the tarball (sans extension)
           *** See Packager documentation for further information ***
               csmake --list-type=Packager
    """

    REQUIRED_OPTIONS = ['maps', 'result']

    #TODO: Refactor Packager to be able to drop the package version
    #      and add version formatting

    def _calculateFileNameAndVersioning(self):
        hasPackageVersion = 'package-version' in self.options
        hasExtension = 'extension' in self.options
        if 'format' in self.options:
            self.format = self.options['format']
        else:
            self.format = 'gzip'
        if self.format == 'gzip':
            self.filetype = 'gz'
            if hasExtension:
                ext = self.options['extension']
            else:
                ext = 'tar.gz'
        elif self.format == 'bzip2':
            self.filetype = 'bz'
            if hasExtension:
                ext = self.options['extension']
            else:
                ext = 'tar.bz2'
        else:
            self.log.warning("'format' '%s' is not understood defaulting to gzip")
            self.format = 'gzip'
            self.filetype = 'gz'
            if hasExtension:
                ext = self.options['extension']
            else:
                ext = 'tar.gz'
        if not hasPackageVersion:
            self.options['package-version'] =''
        Packager._calculateFileNameAndVersioning(self)
        if 'version' in self.options:
            self.version = self.metadata._parseVersionFormatString(
                               self.options['version'] )
        if not hasPackageVersion:
            self.fullVersion = self.version
        else:
            self.fullVersion = '%s-%s' % (
                self.version,
                self.packageVersion )
        self.fullPackageName = "%s-%s" % (
            self.packageName,
            self.fullVersion )
        self.archiveFileName = '%s.%s' % (
            self.fullPackageName,
            ext )
        self.fullPathToArchive = os.path.join(
            self.resultdir,
            self.archiveFileName )

    def _map_path_root(self, value, pathmaps, pathkeymaps):
        noRootDir = False
        if 'no-root-dir' in self.options:
            noRootDir = self.options['no-root-dir'] == "True"
        if noRootDir:
            self.archiveRoot = '.'
        else:
            self.archiveRoot = self.fullPackageName
        pathkeymaps['root'] = [self.archiveRoot]
        pathmaps[value] = [self.archiveRoot]

