#-*- coding: utf8 -*-

from . import *

forms = {
    SECOND: ("a few seconds", "seconds"),
    MINUTE: ("a minute", "minutes"),
    HOUR: ("an hour", "hours"),
    DAY: ("a day", "days"),
    MONTH: ("a month", "months"),
    YEAR: ("a year", "years")
}


class Locale(BaseLocale):
    def relative(self, target, number):
        if number in (0, 1):
            return forms[target][0]
        else:
            return "%s %s" % (number, forms[target][1])

    def past(self, time):
        return "%s ago" % time

    def future(self, time):
        return "in %s" % time
