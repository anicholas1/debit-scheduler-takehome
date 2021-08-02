import json
from werkzeug.wrappers import Request, Response
from werkzeug.routing import Map, Rule
from werkzeug.exceptions import HTTPException, NotFound

from calendar import weekday, monthrange, monthcalendar
from datetime import datetime, timedelta


DEBIT_PERIODS = {'biweekly': 14,
                 'weekly': 7}

DEBIT_WEEKDAY = {'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3, 'friday': 4, 'saturday': 5, 'sunday': 6}


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
        """

        request:   {
                            "loan": {
                                "monthly_payment_amount": 750,
                                "payment_due_day": 28,
                                "schedule_type": "biweekly",
                                "debit_start_date": "2021-05-07",
                                "debit_day_of_week": "friday"
                            }
                        }

        response: {
                    "debit": {
                        "amount": 375,
                        "date": "2021-05-21"
                    }
                  }
        """
        body = request.get_json().get('loan')

        # Get all of the data since we don't have a serializer yet
        current_date = datetime.now().date()
        next_date = None
        year = current_date.year
        month = current_date.month
        day = current_date.day
        schedule_type = body.get('schedule_type')
        monthly_pay = body.get('monthly_payment_amount')
        amount = 0

        # Get the business day integer so we can count how many are in the month using calendar
        business_day = DEBIT_WEEKDAY.get(body.get('debit_day_of_week'))
        start_date = datetime.strptime(body.get('debit_start_date'), "%Y-%m-%d").date()

        num_debit_days = 0
        possible_debit_days = []
        debit_days = []
        # Get all possible debit days first
        for w in monthcalendar(year, month):
            if w[business_day] != 0:
                possible_debit_days.append(w[business_day])
                num_debit_days += 1

        prev_debit_days = []
        for w in monthcalendar(year, month - 1):
            if w[business_day] != 0:
                prev_debit_days.append(w[business_day])
                num_debit_days += 1
        if len(prev_debit_days) == 5 and start_date.month != month:
            possible_debit_days.pop(0)

        # TODO also factor in start_date! What if it doesn't start till the 12th but its the 5th
        if schedule_type == 'biweekly':
            if len(possible_debit_days) > 4:
                amount = monthly_pay / 3
                # 3 possible debit days since we have 5 business days this month. Assuming starting from the beginning
                # of the month
                debit_days.append(possible_debit_days[0])
                debit_days.append(possible_debit_days[2])
                debit_days.append(possible_debit_days[4])
            else:
                # only 2 possible debit days assuming we are starting from the beginning of the month
                amount = monthly_pay / 2
                debit_days.append(possible_debit_days[0])
                debit_days.append(possible_debit_days[2])

            # Find the next debit date based on current date using our debit days found earlier
            # Also make sure the next debit day is after the start day
            # TODO make sure the previous month didn't have a payment at the end of the month.
            #  This would lead to skipping the first week of June

            for d in debit_days:
                if start_date.month == month:
                    if d > day and d >= start_date.day:
                        next_date = datetime(year, month, d).date()
                        break
                else:
                    if d > day:
                        next_date = datetime(year, month, d).date()
                        break

            if next_date is None:
                # Current date is past last pay date of the month based on the initial start date
                # so we need to go to the next month. We will iterate over just the first week
                for w in monthcalendar(year, month + 1):
                    next_date = datetime(year, month+1, w[business_day]).date()
                    break

        response = {'debit':
                            {
                                'amount': amount,
                                'date': str(next_date)
                            }
                    }

        return Response(json.dumps(response), mimetype='application/json')

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
