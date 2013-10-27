SECOND = 0
MINUTE = 1
HOUR = 2
DAY = 3
MONTH = 4
YEAR = 5


class BaseLocale():
    def relative(self, target, number):
        pass

    def past(self, time):
        pass

    def future(self, time):
        pass