#-*- coding: utf8 -*-

import datetime
import i18n
import i18n.en


class TimeDelta(object):
    __slots__ = ("ago", "days", "hours", "minutes", "seconds")

    def __init__(self, datetime_from, datetime_to):
        delta = datetime_from - datetime_to
        minutes, seconds = divmod(delta.days * 86400 + delta.seconds, 60)
        hours, minutes = divmod(minutes, 60)
        days, hours = divmod(hours, 24)
        self.days, self.hours, self.minutes, self.seconds = days, hours, minutes, seconds

    def __str__(self):
        return "Delta(%s day(s), %s hour(s), %s minute(s), %s second(s))" % (
            self.days, self.hours, self.minutes, self.seconds)


_locales = {}


class LocaleContext(object):
    __slots__ = ("locale",)

    def __init__(self, locale="en"):
        self.set_locale(locale)

    def set_locale(self, locale):
        try:
            self.locale = _locales[locale]
        except KeyError:
            try:
                locale = getattr(__import__("i18n.%s" % locale, globals=globals()), locale).Locale()
                if not isinstance(locale, i18n.BaseLocale):
                    raise ValueError()
                self.locale = locale
            except Exception, ex:
                raise ValueError("locale")

    def from_now(self, time, precision=1, fromUTC=False):
        if isinstance(time, datetime.datetime):
            value = time
        else:
            value = (datetime.datetime.utcfromtimestamp if fromUTC else datetime.datetime.fromtimestamp)(float(time))

        now = datetime.datetime.now()
        ago = now > value
        delta = TimeDelta(now, value) if ago else TimeDelta(value, now)

        parts = []
        if precision and delta.days > 0:
            precision -= 1
            parts.append(self.locale.relative(i18n.DAY, delta.days))
        if precision and delta.hours > 0:
            precision -= 1
            parts.append(self.locale.relative(i18n.HOUR, delta.hours))
        if precision and delta.minutes > 0:
            precision -= 1
            parts.append(self.locale.relative(i18n.MINUTE, delta.minutes))
        if precision:
            parts.append(self.locale.relative(i18n.SECOND, delta.seconds))

        return (self.locale.past if ago else self.locale.future)(", ".join(parts))


_locale = LocaleContext()


def set_locale(locale):
    _locale.set_locale(locale)


def from_now(datetime_or_timestamp, precision=1, fromUTC=False):
    return _locale.from_now(datetime_or_timestamp, precision=precision, fromUTC=fromUTC)


if "__main__" == __name__:
    print LocaleContext("ru").from_now(1377069799)
    print LocaleContext("en").from_now(1377069799)
    print LocaleContext("ro").from_now(1377069799)
    print from_now(1377069799)

