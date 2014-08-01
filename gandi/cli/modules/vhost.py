from click import UsageError

from .paas import Paas
from gandi.cli.core.base import GandiModule
from gandi.cli.core.utils import DuplicateResults


class Vhost(GandiModule):

    @classmethod
    def list(cls, options=None):
        """ list paas vhosts (in the future it should handle iaas vhosts) """
        options = options or {}
        return cls.call('paas.vhost.list', options)

    @classmethod
    def info(cls, name):
        """ display information about a vhost """
        return cls.call('paas.vhost.info', name)

    @classmethod
    def create(cls, paas, vhost, background):
        """ create a new vhost """
        if not background and not cls.intty():
            background = True

        paas_id = Paas.usable_id(paas)
        params = {'paas_id': paas_id, 'vhost': vhost}
        try:
            result = cls.call('paas.vhost.create', params)
        except UsageError as err:
            if err.code == 580142:
                params['--dry-run'] = True
                result = cls.call('paas.vhost.create', params)
                for msg in result:
                    # TODO use trads with %s
                    cls.echo(msg['reason'])
                    cls.echo('\t' + '  '.join(msg['attr']))
                return
            raise

        if background:
            return result

        cls.echo("We're creating a new vhost.")
        cls.display_progress(result)
        cls.echo('Your vhost %s have been created.' % vhost)
        return result

    @classmethod
    def delete(cls, resources, background=False):
        """ delete this vhost """

        if not isinstance(resources, (list, tuple)):
            resources = [resources]

        opers = []
        for item in resources:
            oper = cls.call('paas.vhost.delete', item)
            opers.append(oper)

        if background:
            return opers

        cls.echo('Delete your vhost.')
        cls.display_progress(opers)
