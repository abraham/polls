#-*- coding: utf8 -*-

from . import *

forms = {
    SECOND: ("câteva secunde",),
    MINUTE: ("un minut", "minute"),
    HOUR: ("o oră", "ore"),
    DAY: ("o zi", "zile"),
    MONTH: ("o lună", "luni"),
    YEAR: ("un an", "ani")
}


class Locale(BaseLocale):
    def relative(self, target, number):
        if number == 1:
            return forms[target][0]
        else:
            return "%s %s" % (number, forms[target][1])

    def past(self, time):
        return "%s în urmă" % time

    def future(self, time):
        return "peste %s" % time