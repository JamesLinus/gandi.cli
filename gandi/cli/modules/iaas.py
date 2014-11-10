""" VM commands module. """

import math
import socket
import time

from gandi.cli.core.base import GandiModule
from gandi.cli.core.utils import randomstring
from gandi.cli.modules.datacenter import Datacenter
from gandi.cli.modules.sshkey import SshkeyHelper


class Iaas(GandiModule, SshkeyHelper):

    """ Module to handle CLI commands.

    $ gandi vm console
    $ gandi vm create
    $ gandi vm delete
    $ gandi vm info
    $ gandi vm list
    $ gandi vm reboot
    $ gandi vm ssh
    $ gandi vm start
    $ gandi vm stop
    $ gandi vm update

    """

    @classmethod
    def list(cls, options=None):
        """List virtual machines."""
        if not options:
            options = {}

        return cls.call('hosting.vm.list', options)

    @classmethod
    def resource_list(cls):
        """ Get the possible list of resources (hostname, id). """
        items = cls.list()
        ret = [vm['hostname'] for vm in items]
        ret.extend([str(vm['id']) for vm in items])
        return ret

    @classmethod
    def info(cls, id):
        """Display information about a virtual machine."""
        return cls.call('hosting.vm.info', cls.usable_id(id))

    @classmethod
    def stop(cls, resources, background=False):
        """Stop a virtual machine."""
        if not isinstance(resources, (list, tuple)):
            resources = [resources]

        opers = []
        for item in resources:
            oper = cls.call('hosting.vm.stop', cls.usable_id(item))
            if isinstance(oper, list):
                opers.extend(oper)
            else:
                opers.append(oper)

        if background:
            return opers

        # interactive mode, run a progress bar
        cls.echo('Stopping your Virtual Machine %s.' % item)
        cls.display_progress(opers)

    @classmethod
    def start(cls, resources, background=False):
        """Start a virtual machine."""
        if not isinstance(resources, (list, tuple)):
            resources = [resources]

        opers = []
        for item in resources:
            oper = cls.call('hosting.vm.start', cls.usable_id(item))
            if isinstance(oper, list):
                opers.extend(oper)
            else:
                opers.append(oper)

        if background:
            return opers

        # interactive mode, run a progress bar
        cls.echo('Starting your Virtual Machine %s.' % item)
        cls.display_progress(opers)

    @classmethod
    def reboot(cls, resources, background=False):
        """Reboot a virtual machine."""
        if not isinstance(resources, (list, tuple)):
            resources = [resources]

        opers = []
        for item in resources:
            oper = cls.call('hosting.vm.reboot', cls.usable_id(item))
            if isinstance(oper, list):
                opers.extend(oper)
            else:
                opers.append(oper)

        if background:
            return opers

        # interactive mode, run a progress bar
        cls.echo('Rebooting your Virtual Machine %s.' % item)
        cls.display_progress(opers)

    @classmethod
    def delete(cls, resources, background=False):
        """Delete a virtual machine."""
        if not isinstance(resources, (list, tuple)):
            resources = [resources]

        opers = []
        for item in resources:
            oper = cls.call('hosting.vm.delete', cls.usable_id(item))
            if not oper:
                continue

            if isinstance(oper, list):
                opers.extend(oper)
            else:
                opers.append(oper)

        if background:
            return opers

        # interactive mode, run a progress bar
        cls.echo('Deleting your Virtual Machine %s.' % item)
        if opers:
            cls.display_progress(opers)

    @classmethod
    def required_max_memory(cls, id, memory):
        """
        Recommend a max_memory setting for this vm given memory. If the
        VM already has a nice setting, return None. The max_memory
        param cannot be fixed too high, because page table allocation
        would cost too much for small memory profile. Use a range as below.
        """
        best = int(max(2 ** math.ceil(math.log(memory, 2)), 2048))

        actual_vm = cls.info(id)

        if (actual_vm['state'] == 'running'
                and actual_vm['vm_max_memory'] != best):
            return best

    @classmethod
    def update(cls, id, memory, cores, console, password, background,
               max_memory):
        """Update a virtual machine."""
        if not background and not cls.intty():
            background = True

        vm_params = {}

        if memory:
            vm_params['memory'] = memory

        if cores:
            vm_params['cores'] = cores

        if console:
            vm_params['console'] = console

        if password:
            vm_params['password'] = password

        if max_memory:
            vm_params['vm_max_memory'] = max_memory

        result = cls.call('hosting.vm.update', cls.usable_id(id), vm_params)
        if background:
            return result

        # interactive mode, run a progress bar
        cls.echo('Updating your Virtual Machine %s.' % id)
        cls.display_progress(result)

    @classmethod
    def create(cls, datacenter, memory, cores, ip_version, bandwidth,
               login, password, hostname, image, run, background, sshkey,
               size, script):
        """Create a new virtual machine."""
        if not background and not cls.intty():
            background = True

        datacenter_id_ = int(Datacenter.usable_id(datacenter))

        if not hostname:
            hostname = randomstring()
            disk_name = 'sys_%s' % hostname[4:]
        else:
            disk_name = 'sys_%s' % hostname.replace('.', '')

        vm_params = {
            'hostname': hostname,
            'datacenter_id': datacenter_id_,
            'memory': memory,
            'cores': cores,
            'ip_version': ip_version,
            'bandwidth': bandwidth,
        }

        if login:
            vm_params['login'] = login

        if run:
            vm_params['run'] = run

        if password:
            vm_params['password'] = password

        vm_params.update(cls.convert_sshkey(sshkey))

        # XXX: name of disk is limited to 15 chars in ext2fs, ext3fs
        # but api allow 255, so we limit to 15 for now
        disk_params = {'datacenter_id': vm_params['datacenter_id'],
                       'name': disk_name[:15]}

        if size:
            disk_params['size'] = size

        sys_disk_id_ = int(Image.usable_id(image, datacenter_id_))

        result = cls.call('hosting.vm.create_from', vm_params, disk_params,
                          sys_disk_id_)

        ip_summary = 'ip v4+v6'
        if ip_version == 6:
            ip_summary = 'ip v6'
        cls.echo('* Configuration used: %d cores, %dMb memory, %s, '
                 'image %s, hostname: %s' % (cores, memory, ip_summary, image,
                                             hostname))
        if background:
            return result

        # interactive mode, run a progress bar
        cls.echo('Creating your Virtual Machine %s.' % hostname)
        cls.display_progress(result)
        cls.echo('Your Virtual Machine %s has been created.' % hostname)

        if 'ssh_key' not in vm_params and 'keys' not in vm_params:
            return

        vm_id = None
        for oper in result:
            if oper.get('vm_id'):
                vm_id = oper.get('vm_id')
                break

        if vm_id:
            cls.wait_for_sshd(vm_id)
            cls.ssh_keyscan(vm_id)
            if script:
                ret = cls.scp(vm_id, 'root', None, script, '/var/tmp/gscript')
                if not ret:
                    cls.error('Failed to scp script %s to VM %s (id: %s)' %
                              (script, hostname, vm_id))

            cls.ssh(vm_id, 'root', None, script and ['/var/tmp/gscript'])
            if not ret and (script and ['/var/tmp/gscript']):
                cls.error('Failed to execute script %s on VM %s (id: %s)' %
                          ('/var/tmp/gscript', hostname, vm_id))

    @classmethod
    def from_hostname(cls, hostname):
        """Retrieve virtual machine id associated to a hostname."""
        result = cls.list({'hostname': hostname})
        if result:
            return result[0]['id']
        # No "else" clause - if no VM was found matching this hostname, we
        # just fall through the default (which effectively returns None).

    @classmethod
    def usable_id(cls, id):
        """ Retrieve id from input which can be hostname or id."""
        try:
            # id is maybe a hostname
            qry_id = cls.from_hostname(id)
            if not qry_id:
                qry_id = int(id)
        except Exception:
            qry_id = None

        if not qry_id:
            msg = 'unknown identifier %s' % id
            cls.error(msg)

        return qry_id

    @classmethod
    def vm_ip(cls, vm_id):
        """Return the first usable ip address for this vm.
        Returns a (version, ip) tuple."""
        vm_info = cls.info(vm_id)

        for iface in vm_info['ifaces']:
            for ip in iface['ips']:
                return ip['version'], ip['ip']

    @classmethod
    def wait_for_sshd(cls, vm_id):
        """Insist on having the vm booted and sshd
        listening"""
        cls.echo('Waiting for the vm to come online')
        version, ip_addr = cls.vm_ip(vm_id)
        give_up = time.time() + 120
        while time.time() < give_up:
            try:
                inet = socket.AF_INET
                if version == 6:
                    inet = socket.AF_INET6
                sd = socket.socket(inet, socket.SOCK_STREAM,
                                   socket.IPPROTO_TCP)
                sd.settimeout(5)
                sd.connect((ip_addr, 22))
                sd.recv(1024)
                return
            except Exception:
                pass
        cls.error('VM did not spin up')

    @classmethod
    def ssh_keyscan(cls, vm_id):
        """Wipe this old key and learn the new one from a freshly
        created vm. This is a security risk for this VM, however
        we dont have another way to learn the key yet, so do this
        for the user."""
        cls.echo('Wiping old key and learning the new one')
        version, ip_addr = cls.vm_ip(vm_id)
        cls.execute('ssh-keygen -R "%s"' % ip_addr)
        cls.execute('ssh-keyscan "%s" >> ~/.ssh/known_hosts' % ip_addr)

    @classmethod
    def scp(cls, vm_id, login, identity, local_file, remote_file):
        """Copy file to remote VM."""
        cmd = ['scp']
        if identity:
            cmd.extend(('-i', identity,))

        version, ip_addr = cls.vm_ip(vm_id)
        if version == 6:
            ip_addr = '[%s]' % ip_addr

        cmd.extend((local_file, '%s@%s:%s' %
                   (login, ip_addr, remote_file),))
        cls.echo('Running %s' % ' '.join(cmd))
        return cls.execute(cmd, False)

    @classmethod
    def ssh(cls, vm_id, login, identity, args=None):
        """Spawn an ssh session to virtual machine."""
        cmd = ['ssh']
        if identity:
            cmd.extend(('-i', identity,))

        version, ip_addr = cls.vm_ip(vm_id)
        if version == 6:
            cmd.append('-6')

        if not ip_addr:
            cls.echo('No IP address found for vm %s, aborting.' % vm_id)
            return

        cmd.append('%s@%s' % (login, ip_addr,))

        if args:
            cmd.extend(args)

        cls.echo('Requesting access using: %s ...' % ' '.join(cmd))
        return cls.execute(cmd, False)

    @classmethod
    def console(cls, id):
        """Open a console to virtual machine."""
        vm_info = cls.info(id)
        if not vm_info['console']:
            # first activate console
            cls.update(id, memory=None, cores=None, console=True,
                       password=None, background=False, max_memory=None)
        # now we can connect
        # retrieve ip of vm
        vm_info = cls.info(id)
        version, ip_addr = cls.vm_ip(id)

        console_url = vm_info.get('console_url', 'console.gandi.net')
        access = 'ssh %s@%s' % (ip_addr, console_url)
        cls.execute(access)


class Image(GandiModule):

    """ Module to handle CLI commands.

    $ gandi vm images

    """

    @classmethod
    def list(cls, datacenter=None, label=None):
        """List available images for vm creation."""
        options = {}
        if datacenter:
            datacenter_id = int(Datacenter.usable_id(datacenter))
            options['datacenter_id'] = datacenter_id

        # implement a filter by label as API doesn't handle it
        images = cls.safe_call('hosting.image.list', options)
        if not label:
            return images
        return [img for img in images
                if label.lower() in img['label'].lower()]

    @classmethod
    def from_label(cls, label, datacenter=None):
        """Retrieve disk image id associated to a label."""
        result = cls.list(datacenter=datacenter)
        image_labels = dict([(image['label'], image['disk_id'])
                            for image in result])

        return image_labels.get(label)

    @classmethod
    def from_sysdisk(cls, label):
        """Retrieve disk id from available system disks"""
        disks = cls.safe_call('hosting.disk.list', {'name': label})
        if len(disks):
            return disks[0]['id']

    @classmethod
    def usable_id(cls, id, datacenter=None):
        """ Retrieve id from input which can be label or id."""
        try:
            qry_id = int(id)
        except:
            # if id is a string, prefer a system disk then a label
            qry_id = cls.from_sysdisk(id) or cls.from_label(id, datacenter)

        if not qry_id:
            msg = 'unknown identifier %s' % id
            cls.error(msg)

        return qry_id


class Kernel(GandiModule):

    """ Module to handle Gandi Kernels. """

    @classmethod
    def list(cls, datacenter, flavor=None, match=''):
        """ List available kernels for datacenter."""
        dc_id = Datacenter.usable_id(datacenter)
        kmap = cls.safe_call('hosting.disk.list_kernels', dc_id)

        if match:
            for flav in kmap:
                kmap[flav] = [x for x in kmap[flav] if match in x]

        if flavor:
            if flavor not in kmap:
                cls.error('flavor %s not supported here' % flavor)
            return kmap[flavor]

        return kmap
