import json
import mailbox
import os

from optparse import OptionParser

from firetower import config
from firetower.redis_util import Redis

def main():
    parser = OptionParser(usage='usage: firetower options args')
    parser.add_option(
        '-c', '--conf', action='store', dest='conf_path',
         help='Path to YAML configuration file.')
    (options, args) = parser.parse_args()
    conf = config.Config(options.conf_path)

    home = os.getenv('HOME')
    maildir_path = '%s/Maildir' % (home,)
    print 'This is the Maildir path: ', maildir_path
    assert os.path.exists(maildir_path)
    inbox = mailbox.Maildir(maildir_path, factory=None)

    queue = Redis(host=conf.redis_host, port=conf.redis_port)

    for message in inbox:
        ft_dict = {}
        ft_dict['hostname'] = message['Received'].split(' ')[1] or '????'
        ft_dict['sig'] = message.get_payload() or '????'
        ft_dict['date'] = message.get_date()
        ft_dict['programname'] = 'Maildir Util'

        queue.push(conf.queue_key, json.dumps(ft_dict))
        print ft_dict

if __name__ == '__main__':
    main()