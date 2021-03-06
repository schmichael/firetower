import difflib
import json

from logbook import Logger

log = Logger('Firetower-classifier')

CLASSIFIER_TYPES = (
        'none',
        'ratio',
        'quick_ratio',
        'real_quick_ratio')

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


    def _halve_ratio_dist(self, ratio):
        """Dynamically close gap between any ratio and 1.00.
        
        Args:
            ratio: float, ratio in question.
        Return:
            float, modified to be closer to 1.00.
        """
        return ratio + (1 - ratio)/2

    def str_len_ratio(self, cat_str, sig_str, str_len_thresh=0.8):
        """Comare lengths to see if we should go with more complex analysis.

        Args:
            cat_str: str, the category we're going to compare against.
            sig_str: str, the string we're pulling from incoming event.
            str_len_thresh: float, passing size ratio and above.
        Returns:
            bool if the lengths are within length tolerence.
        """
        cat_str_len = len(cat_str)
        sig_str_len = len(sig_str)
        ratio = 0.0
        if cat_str_len < sig_str_len:
            ratio = float(cat_str_len)/sig_str_len
        else:
            ratio = float(sig_str_len)/cat_str_len

        if ratio > str_len_thresh:
            return True
        else:
            return False

    def str_ratio(self, exemplar_str, sig_str,
            small_sig_size=100, medium_sig_size=2000):
        """Return the ratio of similarity between two strings; ignore spaces.

        Args:
            exemplar_str: str, basis of comparison within an existing category.
            sig_str: str, signature string we're trying to compare.
            small_sig_size: int, largest sig size before we use change
                    comparison methodologies.
            medium_sig_size: int, largest sig size before we downgrade
                    comparison methods fully.
        Returns:
            tuple of float, ratio of similarity and int which maps
            to type of ratio in CLASSIFIER_TYPES:
                enum of {none, ratio, quick_ratio, real_quick_ratio}.
        """
        if self.str_len_ratio(exemplar_str, sig_str):
            sig_len = len(sig_str)
            seq = difflib.SequenceMatcher(None, exemplar_str, sig_str)
            if sig_len < small_sig_size:
                log.debug('Small signature found, using ratio()')
                return (seq.ratio(), 1)
            elif sig_len < medium_sig_size and sig_len >= small_sig_size:
                log.debug('Medium signature found, using quick_ratio()')
                return (seq.quick_ratio(), 2)
            else:
                log.debug('Large signature found, using real_quick_ratio()')
                return (seq.real_quick_ratio(), 3)
        else:
            log.debug('Ratio was too far off')
            return (0.0, 0)

    def is_similar(self, golden, sig_str, thresh, is_custom):
        """Returns True if similarity is larger than thresh.

        Args:
            golden: str, known category's signature.
            sig_str: str, unknown payload's signature.
            thresh: float, threshold to decide if we have a match.
            is_custom: boolean, does category have a custom threshold.
        Returns:
            bool, True if similar.
        """
        ratio, class_type = self.str_ratio(golden, sig_str)
        # Make the default ratio closer to 1.00 the less accurate the
        # classification algorithm we use. Do this multiple times if
        # we use less accuracy in the algorithm.
        if class_type and not is_custom:
            # Probably too clever: not super happy with this implementation.
            for _half in range(class_type):
                thresh = self._halve_ratio_dist(thresh)
                log.debug('Used this default threshold %.4f' % thresh)
        if ratio > thresh:
            return True

        return False

    def check_message(self, cat, error, default_thresh):
        """Compare error with messages from a category.

        Args:
            cat: category object to compare the error against
            error: dict, error message we're processing.
            thresh: float, the ratio of similarity needed to match.
        """
        sig = error['sig']

        custom_thresh = cat.threshold
        is_custom = False
        thresh = custom_thresh if custom_thresh is not None else default_thresh
        if thresh != default_thresh:
            is_custom = True

        exemplar_str = None
        last_data = cat.events.range(-1, -1)
        if not last_data:
            exemplar_str = cat.signature
        else:
            exemplar_str = json.loads(last_data[0])['sig']

        if self.is_similar(sig, exemplar_str, thresh, is_custom=is_custom):
            return True
