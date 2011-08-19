import datetime
import difflib
import json

def longest_common_substr(s1, s2):
    """
    Args:
        s1: str, first string to compare.
        s2: str, second string to compare.

    Influenced by:
    http://en.wikibooks.org/wiki/Algorithm_implementation/Strings/ \
    Longest_common_substring#Python
    """
    if len(s1) < len(s2):
        s1, s2 = s2, s1

    M = [[0]*(1+len(s1)) for i in xrange(1+len(s1))]
    longest, x_longest = 0, 0
    for x in xrange(1, 1+len(s1)):
        for y in xrange(1, 1+len(s2)):
            if s1[x-1] == s2[y-1]:
                M[x][y] = M[x-1][y-1] + 1
                if M[x][y] > longest:
                    longest = M[x][y]
                    x_longest = x
            else:
                M[x][y] = 0
    return s1[x_longest-longest: x_longest]


class Classifier(object):
    pass


class NaiveBayes(Classifier):
    pass


class Levenshtein(Classifier):

    def __init__(self, redis):
        """init.

        Args:
            conf: a conf.Conf obj.
        """
        self.redis = redis

    def str_ratio(self, golden, test_str):
        """Return the ratio of similarity between two strings; ignore spaces."""
        return difflib.SequenceMatcher(None, golden, test_str).ratio()

    def is_similar(self, golden, test_str, thresh):
        """Returns True if similarity is larger than thresh."""

        ratio = self.str_ratio(golden, test_str)
        if ratio > thresh:
            print "%s: %s matches %s with a %.1f ratio" % (
                    str(datetime.datetime.now()), test_str, golden, ratio)
            return True

        return False

    def write_errors(self, cat, error):
        """Increment counters, save data.

        Args:
            cat: str, category name.
            error: dict, new payload to save.
        """
        cat_counter = 'counter_%s' % (cat,)
        cat_data = 'data_%s' % (cat,)
        self.redis.incr_counter(cat_counter)
        self.redis.save_error(cat_data, error)

    def check_message(self, cat, error):
        """Compare error with messages from a category.

        Args:
            cat: str, keyname of a category (maybe unknown_errors)
            error: dict, error message we're processing
        """
        sig = error['sig']

        cat_errors = self.redis.get_latest_data(cat)
        if not cat_errors:
            return None
        for cat_error in cat_errors:
            if not cat_error:
                continue
            decode_error = json.loads(cat_error)
            cat_sig = decode_error['sig']
            if self.is_similar(cat_sig, sig, 0.7):
                self.write_errors(cat, error)
                return True

    def classify(self, error):
        """Determine which category, if any, a signature belongs to.

        If it doesn't find a match, then it'll save the error into an
        'unknown' list of errors, which subsequent errors are checked against.
        When a match is found between a new errors and one of the unknown errors
        a new category is created.

        Args:
            error: dict of json payload with a 'sig' key.
        """
        categories = self.redis.get_categories()
        # Let's see if our message matches a category
        for cat in categories:
            if self.check_message(cat, error):
                break
        else:
            cat_sig = error['sig']
            self.redis.add_category(cat_sig)
            self.write_errors(cat_sig, error)
