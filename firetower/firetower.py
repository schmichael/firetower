import datetime
import json
import time

from logbook import Logger
from logbook import TimedRotatingFileHandler
from optparse import OptionParser

import config
import classifier
import category
import redis_util


class Main(object):
    """Main loop."""

    def __init__(self, conf):
        self.conf = conf
        handler = TimedRotatingFileHandler(
            conf.log_file, date_format='%Y-%m-%d')
        handler.push_application()
        self.logger = Logger('Firetower-server')
        self.queue = redis_util.get_redis_conn(
            host=conf.redis_host, port=conf.redis_port, redis_db=conf.redis_db
        )
        self.classifier = classifier.Levenshtein()
        self.last_archive = None

    def get_error(self):
        """Get the next error to be categorised"""
        return self.queue.rpop(self.conf.queue_key)

    def run_archiving(self):
        """Run the timeseries archiving for all categories
        """
        now = datetime.datetime.utcnow()
        if self.last_archive is None:
            self.last_archive = datetime.datetime.utcnow()
            return

        delta = datetime.timedelta(seconds=self.conf.archive_time)
        if self.last_archive < (now - delta):
            self.logger.debug('Archiving counts older than %s seconds' % (self.conf.archive_time,))
            for c in category.Category.get_all_categories(self.queue):
                self.logger.debug('Archiving for %s category' % (c.cat_id))
                c.timeseries.archive_cat_counts(self.last_archive)
            self.last_archive = now

    def run(self):
        """Drop into a loop pulling errors and categorizing them"""
        while 1:
            err = self.get_error()
            self.run_archiving()
            if err:
                parsed = json.loads(err)
                category.Category.classify(
                    self.queue, self.classifier, parsed, self.conf.class_thresh
                )
            else:
                time.sleep(1)


def main():
    parser = OptionParser(usage='usage: firetower options args')
    parser.add_option(
            '-c', '--conf', action='store', dest='conf_path',
            help='Path to YAML configuration file.')

    (options, args) = parser.parse_args()

    conf = config.Config(options.conf_path)
    main = Main(conf)
    main.run()
