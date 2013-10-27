#-*- coding: utf8 -*-

from . import *

forms = {
    SECOND: ("несколько секунд",),
    MINUTE: ("минуту", "минута", "минуты", "минут"),
    HOUR: ("час", "час", "часа", "часов"),
    DAY: ("день", "день", "дня", "дней"),
    MONTH: ("месяц", "месяц", "месяца", "месяцев"),
    YEAR: ("год", "год", "года", "лет")
}


class Locale(BaseLocale):
    def plural(self, n, forms):
        if n % 10 == 1 and n % 100 != 11:
            return forms[1]
        elif 4 >= n % 10 >= 2 and (n % 100 < 10 or n % 100 >= 20):
            return forms[2]
        else:
            return forms[3]

    def relative(self, target, number):
        if number == 1 or target == SECOND:
            return forms[target][0]
        else:
            return "%s %s" % (number, self.plural(number, forms[target]))

    def past(self, time):
        return "%s назад" % time

    def future(self, time):
        return "через %s" % time