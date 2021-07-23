import calendar
from datetime import datetime, timedelta, date
from dateutil import parser
from dateutil.relativedelta import relativedelta
import json
import math
from werkzeug.wrappers import Request, Response
from werkzeug.routing import Map, Rule
from werkzeug.exceptions import HTTPException, NotFound


class App(object):

    def __init__(self):
        self.url_map = Map(
            [
                Rule("/", endpoint=""),
                Rule("/get_next_debit", endpoint="get_next_debit")
            ]
        )


    def dispatch_request(self, request):
        adapter = self.url_map.bind_to_environ(request.environ)
        try:
            endpoint, values = adapter.match()
            return getattr(self, f"on_{endpoint}")(request, **values)
        except NotFound:
            return self.error_404()
        except HTTPException as e:
            return e


    def on_get_next_debit(self, request):
        body = request.get_json()

        ##############
        # START HERE #
        ##############

        response = {'debit': self.get_next_debit(body['loan'])}

        return Response(json.dumps(response), mimetype='application/json')


    def get_date_range(self, start_date, target_date, day_of_week):
        """
        Get the date ranges based on start and end dates and day of week.
        :return: An array of datetime.date objects
        """
        c = calendar.Calendar()
        date_range = []
        date_iterator = start_date
        while date_iterator <= target_date + relativedelta(months=1):
            date_range += [x for x in c.itermonthdates(date_iterator.year, date_iterator.month)
                           if x >= start_date
                           and x.month == date_iterator.month
                           and x.weekday() == day_of_week
                           ]
            date_iterator += relativedelta(months=1)
        return date_range


    def get_next_debit(self, loan):
        """
        Process and returns next debit date for loan.
        :param loan: dictionary containing information about the loan.
        :return: dictionary containing information about the debit.
        """
        # Date we start debiting should occur after the current day.
        target_date = datetime.utcnow().date() + timedelta(days=1)
        # Check if it lands on a weekend and move it to the following Monday.
        if target_date.weekday() > 4:
            target_date = target_date + timedelta((0-target_date.weekday()) % 7)
        debit_start_date = parser.parse(loan['debit_start_date']).date()
        if debit_start_date > target_date:
            target_date = debit_start_date

        debit_day_of_week = self.get_dow_num(loan['debit_day_of_week'])
        date_range = self.get_date_range(debit_start_date, target_date, debit_day_of_week)

        debit = {}

        if loan['schedule_type'] == 'biweekly':
            biweekly_range = date_range[::2]
            target_range = [x for x in biweekly_range if x >= target_date]
            debit_date = target_range[0]
            month_range = [x for x in biweekly_range if x.month == debit_date.month]
            debit['amount'] = math.ceil(loan['monthly_payment_amount'] / len(month_range))
            debit['date'] = debit_date.strftime('%Y-%m-%d')
        else:
            # Assume monthly
            target_range = [x for x in date_range if x >= target_date and x.day != loan['payment_due_day']]
            debit_date = target_range[0]
            debit['amount'] = loan['monthly_payment_amount']
            debit['date'] = debit_date.strftime('%Y-%m-%d')

        return debit


    def get_dow_num(self, day_of_week):
        """
        Maps day_of_week string to corresponding datetime weekday.
        """
        return {
            'monday': 0,
            'tuesday': 1,
            'wednesday': 2,
            'thursday': 3,
            'friday': 4,
            'saturday': 5,
            'sunday': 6,
        }.get(day_of_week)


    def wsgi_app(self, environ, start_response):
        request = Request(environ)
        response = self.dispatch_request(request)
        return response(environ, start_response)


    def __call__(self, environ, start_response):
        return self.wsgi_app(environ, start_response)


def create_app():
    app = App()
    return app


if __name__ == '__main__':
    from werkzeug.serving import run_simple

    app = create_app()
    run_simple('0.0.0.0', 5000, app, use_debugger=True, use_reloader=True)
